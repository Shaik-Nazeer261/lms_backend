from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.conf import settings
from django.core.mail import send_mail
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions, generics, serializers, viewsets
from rest_framework.decorators import action
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError,PermissionDenied
from .models import *
from .serializers import *
from rest_framework.permissions import IsAuthenticated, IsAdminUser,AllowAny
import threading
import time
from django.db.models import Max
from django.db import transaction
from django.core.files.storage import default_storage
from rest_framework.parsers import MultiPartParser, FormParser ,JSONParser
from django.db import connection
from .permissions import IsAdminOrInstructor, IsAdminOrStudent, IsAdminUserAlwaysAllow
from django.contrib.auth.hashers import make_password
User = get_user_model()
from django.db.models import Q
from .utils.certificate_pdf import generate_certificate
from django.db.models import Count







from rest_framework_simplejwt.views import TokenObtainPairView

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer




class AddTeacherView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role != 'admin':
            return Response({"error": "Only admins can add teachers."}, status=403)

        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Teacher added and mail sent successfully'}, status=201)
        return Response(serializer.errors, status=400)



class VerifyTeacherView(APIView):
    def get(self,request,uidb64,token):
        try:
            uid=urlsafe_base64_decode(uidb64).decode()
            user=CustomUser.objects.get(pk=uid)

            if default_token_generator.check_token(user,token):
                user.is_active=True
                user.save()
                instructor=Instructor.objects.create(user=user)
                instructor.save()
                return Response({'message':'Account verified successfully'},status=status.HTTP_200_OK)
            else:
                return Response({'error':'Token is invalid or expired'},status=status.HTTP_400_BAD_REQUEST)
        except (TypeError,ValueError,OverflowError,CustomUser.DoesNotExist):
            return Response({'error':'Token is invalid or expired'},status=status.HTTP_400_BAD_REQUEST)
        

class ForgotPasswordView(APIView):
    def post(self,request):
        email=request.data.get('email')

        try:
            user=CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExit:
            return Response({'error':'User with this email does not exist'},status=status.HTTP_400_BAD_REQUEST)
        if not user.is_active:
            return Response({'error':'User is not active'},status=status.HTTP_400_BAD_REQUEST)
        
        token=default_token_generator.make_token(user)
        uid=urlsafe_base64_encode(force_bytes(user.pk))

        reset_link = f"{settings.FRONTEND_URL}/student/reset-password/{uid}/{token}/"
        send_mail(
            subject='Reset Your Password',
            message=f'Hi {user.first_name},\n\nYou requested a password reset.\nPlease use the link below to reset your password:\n{reset_link}\n\nIf you did not request this, please ignore this email.',
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[user.email],
            fail_silently=False,
        )

        return Response({'message':'password reset link sent to your email'},status=status.HTTP_200_OK)
    

class ResetPasswordView(APIView):
    def post(self,request,uidb64,token):
        try:
            uid=urlsafe_base64_decode(uidb64).decode()
            user=CustomUser.objects.get(pk=uid)
        except (TypeError,ValueError,OverflowError,CustomUser.DoesNotExist):
            return Response({'error':'Token is invalid or expired'},status=status.HTTP_400_BAD_REQUEST)
        
        if not default_token_generator.check_token(user,token):
            return Response({'error':'token is invalid or expired'},status=status.HTTP_400_BAD_REQUEST)
        
        new_password=request.data.get('new_password')
        if not new_password:
            return Response({'error':'new password is required'},status=status.HTTP_400_BAD_REQUEST)
        
        user.set_password(new_password)
        user.save()

        return Response({'message':'password reset succesfully'},status=status.HTTP_200_OK)


class StudentRegisterView(APIView):
    def post(self,request):
        serializer = StudentRegisterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'message':'Student registered successfully'}, status=201)
        return Response(serializer.errors, status=400)
    

class InstructorProfileView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        instructor = get_object_or_404(Instructor, user=request.user)
        serializer = InstructorSerializer(instructor)

        # Fields to consider for completion
        profile_fields = [
            instructor.profile_picture,
            instructor.headline,
            instructor.biography,
            instructor.phone_number,
            instructor.personal_website,
            instructor.facebook_url,
            instructor.instagram_url,
            instructor.linkedin_url,
            instructor.twitter_url,
            instructor.whatsapp_number,
            instructor.youtube_url,
            instructor.user.first_name,
            instructor.user.last_name,
        ]

        total_fields = len(profile_fields)
        filled_fields = sum(1 for field in profile_fields if field)

        completion_percentage = int((filled_fields / total_fields) * 100)

        response_data = serializer.data
        response_data["profile_completion"] = completion_percentage

        return Response(response_data, status=200)

    def put(self, request):
        instructor = get_object_or_404(Instructor, user=request.user)
        user = instructor.user

        email = request.data.get("email", user.email)
        if email != user.email and CustomUser.objects.filter(email=email).exclude(id=user.id).exists():
            return Response({"error": "This email is already in use."}, status=400)

        password = request.data.get("password")

        # Update user fields
        user.username = request.data.get("username", user.username)
        user.first_name = request.data.get("first_name", user.first_name)
        user.last_name = request.data.get("last_name", user.last_name)

        # Update instructor fields only if the field is non-empty or explicitly null
        social_fields = [
            "phone_number", "personal_website", "facebook_url", "instagram_url",
            "linkedin_url", "twitter_url", "whatsapp_number", "youtube_url"
        ]
        for field in social_fields:
            value = request.data.get(field, "KEEP_OLD_VALUE")
            if value != "KEEP_OLD_VALUE":
                setattr(instructor, field, value if value else None)

        # Save profile picture and other fields if passed
        serializer = InstructorSerializer(instructor, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            user.email = email
            if password:
                user.password = make_password(password)
            user.save()
            return Response(serializer.data, status=200)

        return Response(serializer.errors, status=400)

    

class StudentProfileView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        student = get_object_or_404(Student, user=request.user)
        serializer = StudentSerializer(student)
        return Response(serializer.data, status=200)

    def put(self, request):
        student = get_object_or_404(Student, user=request.user)
        user = student.user  # Linked CustomUser instance
        
        email = request.data.get("email", user.email)
        if email != user.email and CustomUser.objects.filter(email=email).exclude(id=user.id).exists():
            return Response({"error": "This email is already in use."}, status=400)

        password = request.data.get("password", None)
        user.username = request.data.get("username", user.username)
        user.first_name = request.data.get("first_name", user.first_name)
        user.last_name = request.data.get("last_name", user.last_name)


        # Update Student fields
        serializer = StudentSerializer(student, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()

            #  Update `CustomUser` fields
            user.email = email
            if password:  
                user.password = make_password(password)  # Hash password before saving
            user.save()

            return Response(serializer.data, status=200)
        
        return Response(serializer.errors, status=400)



    

class CourseCreateView(APIView):
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role != 'instructor':
            return Response({"error": "Only instructors can create courses."}, status=403)

        serializer = CourseSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            course = serializer.save(instructor=request.user.instructor)
            return Response({"message": "Course created successfully", "course_id": course.id}, status=201)
        return Response(serializer.errors, status=400)
    



class CourseUpdateView(generics.UpdateAPIView):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)  # Support file updates

    def get_object(self):
        course_id = self.kwargs.get('course_id')
        course = get_object_or_404(Course, id=course_id)

        if self.request.user != course.instructor.user:
            raise ValidationError({"error": "You can only update courses that you created."})

        return course

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        partial = kwargs.pop('partial', True)  # Allow partial update by default

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        try:
            self.perform_update(serializer)
        except IntegrityError:
            return Response({"error": "An integrity error occurred during update."},
                            status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "message": "Course updated successfully.",
            "progress": serializer.data.get("creation_progress", None),
            "course_id": instance.id
        }, status=status.HTTP_200_OK)

    def perform_update(self, serializer):
        serializer.save()   



class CourseDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, course_id):
        course = get_object_or_404(Course, id=course_id)

        # Correct ownership checking
        if request.user != course.instructor.user:
            return Response({"error": "You can only delete your own courses."}, status=status.HTTP_403_FORBIDDEN)

        course.is_deleted = True  # Soft delete
        course.save()

        # Start a background thread (daemon thread)
        thread = threading.Thread(target=self.permanent_delete, args=(course_id,))
        thread.daemon = True
        thread.start()

        return Response({"message": " Course marked as deleted. It will be permanently deleted after 10 seconds if not restored."}, status=status.HTTP_200_OK)

    def permanent_delete(self, course_id):
        """Wait 10 seconds before permanently deleting if not restored."""
        time.sleep(10)
        course = Course.objects.filter(id=course_id, is_deleted=True).first()
        if course:
            course.delete()  #  Hard delete

class CourseRestoreView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, course_id):
        course = get_object_or_404(Course, id=course_id, is_deleted=True)

        if request.user != course.instructor.user:
            return Response({"error": "You can only restore your own courses."}, status=status.HTTP_403_FORBIDDEN)

        course.is_deleted = False
        course.save()
        return Response({"message": "Course restored successfully."}, status=status.HTTP_200_OK)



class LessonCreateView(generics.CreateAPIView):
    serializer_class = LessonSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        course_id = self.kwargs.get('course_id')
        course = get_object_or_404(Course, id=course_id)

        if self.request.user != course.instructor.user:  #  Correct comparison
            raise ValidationError({"error": "You can only add lessons to your own courses."})

        serializer.save(course=course)

class LessonDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, course_id, lesson_id):
        lesson = get_object_or_404(Lesson, id=lesson_id, course_id=course_id)

        if request.user != lesson.course.instructor.user:
            return Response({"error": "You can only delete lessons from your own courses."}, status=status.HTTP_403_FORBIDDEN)

        lesson.is_deleted = True
        lesson.save()

        thread = threading.Thread(target=self.permanent_delete, args=(lesson_id,))
        thread.daemon = True  #  safer
        thread.start()

        return Response({"message": "Lesson deleted. You can undo within 10 seconds."}, status=status.HTTP_200_OK)

    def permanent_delete(self, lesson_id):
        time.sleep(10)
        lesson = Lesson.objects.filter(id=lesson_id, is_deleted=True).first()
        if lesson:
            lesson.delete()


class LessonRestoreView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, course_id, lesson_id):
        lesson = get_object_or_404(Lesson, id=lesson_id, course_id=course_id, is_deleted=True)

        if request.user != lesson.course.instructor.user:
            return Response({"error": "You can only restore lessons in your own courses."}, status=status.HTTP_403_FORBIDDEN)

        lesson.is_deleted = False
        lesson.save()
        return Response({"message": "Lesson restored successfully."}, status=status.HTTP_200_OK)

class LessonUpdateView(generics.UpdateAPIView):
    queryset = Lesson.objects.all()
    serializer_class = LessonSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        """Get lesson ensuring the logged-in instructor owns it."""
        lesson_id = self.kwargs.get('lesson_id')
        lesson = Lesson.objects.get(id=lesson_id)

        if self.request.user != lesson.course.instructor.user:
            raise ValidationError({"error": "You can only update lessons from your own courses."})

        return lesson
    
class ConceptCreateView(generics.CreateAPIView):
    serializer_class = ConceptSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        lesson_id = self.kwargs.get('lesson_id')
        lesson = get_object_or_404(Lesson, id=lesson_id)

        if self.request.user != lesson.course.instructor.user:  #  Corrected
            raise ValidationError({"error": "You can only add concepts to your own lessons."})

        last_concept = Concept.objects.filter(lesson=lesson).order_by('-order').first()
        new_order = last_concept.order + 1 if last_concept else 0

        serializer.save(lesson=lesson, order=new_order)


class ConceptDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, lesson_id, concept_id):
        concept = get_object_or_404(Concept, id=concept_id, lesson_id=lesson_id)

        if request.user != concept.lesson.course.instructor.user:
            return Response({"error": "You can only delete concepts from your own lessons."}, status=status.HTTP_403_FORBIDDEN)

        concept.is_deleted = True
        concept.save()

        thread = threading.Thread(target=self.permanent_delete, args=(concept_id,))
        thread.daemon = True  #  daemon mode
        thread.start()

        return Response({"message": "Concept deleted. You can undo within 10 seconds."}, status=status.HTTP_200_OK)

    def permanent_delete(self, concept_id):
        time.sleep(10)
        concept = Concept.objects.filter(id=concept_id, is_deleted=True).first()
        if concept:
            concept.delete()

class ConceptRestoreView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, lesson_id, concept_id):
        concept = get_object_or_404(Concept, id=concept_id, lesson_id=lesson_id, is_deleted=True)

        if request.user != concept.lesson.course.instructor.user:
            return Response({"error": "You can only restore concepts in your own lessons."}, status=status.HTTP_403_FORBIDDEN)

        concept.is_deleted = False
        concept.save()
        return Response({"message": "Concept restored successfully."}, status=status.HTTP_200_OK)

class ConceptUpdateView(generics.UpdateAPIView):
    queryset = Concept.objects.all()
    serializer_class = ConceptSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        concept_id = self.kwargs.get('concept_id')
        concept = Concept.objects.get(id=concept_id)

        if self.request.user != concept.lesson.course.instructor.user:
            raise ValidationError({"error": "You can only update concepts from your own lessons."})

        return concept


class LessonContentCreateView(generics.CreateAPIView):
    serializer_class = LessonContentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_context(self):
        return {"request": self.request}

    def perform_create(self, serializer):
        concept_id = self.kwargs.get('concept_id')
        concept = get_object_or_404(Concept, id=concept_id)

        if self.request.user != concept.lesson.course.instructor.user:  #  Corrected
            raise ValidationError({"error": "You can only add content to your own lessons."})

        try:
            with transaction.atomic():
                last_order = (
                    LessonContent.objects
                    .select_for_update()
                    .filter(concept=concept)
                    .aggregate(Max('order'))['order__max'] or 0
                )
                new_order = last_order + 1

                print(f" Assigning order={new_order} for concept {concept_id}")
                print(" Existing contents for this concept:")
                for content in LessonContent.objects.filter(concept=concept).order_by('order'):
                    print(f"    ➤ Content ID {content.id} — Order {content.order}")

                serializer.save(concept=concept, order=new_order)
                print(" Content and related questions saved successfully.")

        except IntegrityError as e:
            print(f" IntegrityError while creating content for concept {concept_id}: {e}")
            raise ValidationError({"error": "Duplicate order or question conflict. Please try again later."})
        
class LessonContentUpdateView(generics.UpdateAPIView):
    queryset = LessonContent.objects.all()
    serializer_class = LessonContentUpdateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        concept_id = self.kwargs.get('concept_id')
        content_id = self.kwargs.get('content_id')
        return get_object_or_404(LessonContent, id=content_id, concept_id=concept_id)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()

        if request.user != instance.concept.lesson.course.instructor.user:  # ✅ Corrected
            return Response({"error": "You can only update content in your own lessons."}, status=403)

        partial = kwargs.pop('partial', False)
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response(serializer.data)

    def perform_update(self, serializer):
        try:
            serializer.save()
        except IntegrityError:
            raise ValidationError({"error": "Duplicate order detected. Please try again."})

class LessonContentDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, concept_id, content_id):
        content = get_object_or_404(LessonContent, id=content_id, concept_id=concept_id)

        if request.user!= content.concept.lesson.course.instructor.user:
            return Response({"error": "You can only delete content from your own lessons."}, status=403)

        content.delete()  # 🔥 HARD DELETE from database
        return Response({"message": "Content permanently deleted."}, status=status.HTTP_204_NO_CONTENT)


        
class UploadImageView(APIView):
    parser_classes = [MultiPartParser]
    permission_classes = [permissions.IsAuthenticated]


    def post(self, request):
        image = request.FILES.get('image')
        if not image:
            return Response({"error": "No image uploaded."}, status=400)

        filename = default_storage.save(f"lessons/images/{image.name}", image)
        image_url = default_storage.url(filename)
        return Response({"url": image_url})
    
class VideoQuestionListCreateView(generics.ListCreateAPIView):
    serializer_class = VideoQuestionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        content_id = self.kwargs["content_id"]
        get_object_or_404(LessonContent, id=content_id)  # ✅ Confirm content exists
        return VideoQuestion.objects.filter(content_id=content_id)

    def perform_create(self, serializer):
        content = get_object_or_404(LessonContent, id=self.kwargs["content_id"])
        serializer.save(content=content)

class VideoQuestionDeleteView(generics.DestroyAPIView):
    queryset = VideoQuestion.objects.all()
    permission_classes = [IsAuthenticated]
    lookup_field = "id"

class VideoQuestionUpdateView(generics.UpdateAPIView):
    queryset = VideoQuestion.objects.all()
    serializer_class = VideoQuestionSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"

class AssignmentCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = AssignmentCreateSerializer(data=request.data)
        if serializer.is_valid():
            course = serializer.validated_data['course']
            instructor = course.instructor  # Get the Instructor instance

            # Ensure the request user is the instructor's user
            if instructor.user != request.user:
                return Response({"error": "You are not authorized to add assignments to this course."}, status=403)

            assignments_data = serializer.validated_data['assignments']
            assignments = [
                Assignment(
                    instructor=instructor,
                    course=course,
                    question=item['question'],
                    options=item.get('options', []),
                    answer=item['answer']
                )
                for item in assignments_data
            ]

            Assignment.objects.bulk_create(assignments)
            return Response({"message": "Assignments created successfully."}, status=201)

        return Response(serializer.errors, status=400)

    

class AssignmentDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, course_id, assignment_id):
        """Allow an instructor to delete an assignment from their course."""

        assignment = get_object_or_404(Assignment, id=assignment_id, course_id=course_id)

        # ✅ Ensure user is instructor and owns the course
        if request.user != assignment.instructor.user:
            return Response(
                {"error": "You are not authorized to delete this assignment."},
                status=status.HTTP_403_FORBIDDEN
            )

        assignment.delete()
        return Response(
            {"message": "Assignment deleted successfully."},
            status=status.HTTP_204_NO_CONTENT
        )
    
class DeleteAllAssignmentsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, course_id):
        """Delete all assignments for a specific course if the user is the instructor."""
        
        # Force close the database connection to avoid locking issues
        connection.close()

        # Get the course and check if the user is the instructor
        course = get_object_or_404(Course, id=course_id)
        if course.instructor.user != request.user:
            return Response({"error": "You are not authorized to delete assignments for this course."},
                            status=status.HTTP_403_FORBIDDEN)

        # Delete all assignments for this course
        deleted_count, _ = Assignment.objects.filter(course=course).delete()

        if deleted_count == 0:
            return Response({"message": "No assignments found for this course."},
                            status=status.HTTP_204_NO_CONTENT)

        return Response({"message": f"{deleted_count} assignments deleted successfully."},
                        status=status.HTTP_200_OK)


class UploadAssignmentFileView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, course_id, *args, **kwargs):
        #  Force close the database connection to unlock it
        connection.close()

        instructor = get_object_or_404(Instructor, user=request.user)
        course = get_object_or_404(Course, id=course_id)

        if course.instructor != instructor:
            return Response({"error": "You are not authorized to add assignments to this course."}, 
                            status=status.HTTP_403_FORBIDDEN)

        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response({"error": "No file uploaded."}, status=status.HTTP_400_BAD_REQUEST)

        file_extension = uploaded_file.name.split('.')[-1].lower()
        if file_extension == "pdf":
            extracted_data = self.extract_text_from_pdf(uploaded_file)
        elif file_extension in ["docx", "doc"]:
            extracted_data = self.extract_text_from_word(uploaded_file)
        else:
            return Response({"error": "Unsupported file format. Upload PDF or Word files."}, 
                            status=status.HTTP_400_BAD_REQUEST)

        if not extracted_data:
            return Response({"error": "No valid questions and answers found in the document."}, 
                            status=status.HTTP_400_BAD_REQUEST)
        
         #  Store extracted questions & answers in the database
        assignments = [
            Assignment(
                instructor=instructor,
                course=course,
                question=question,
                options=options,
                answer=answer
            )
            for question, options, answer in extracted_data
        ]

        Assignment.objects.bulk_create(assignments)

        return Response({"message": "Assignments uploaded and stored successfully.",
                         "extracted_data": extracted_data 
                         }, status=status.HTTP_201_CREATED)

      
    def extract_text_from_pdf(self, pdf_file):
        """Extract text from a PDF and return (question, answer) pairs."""
        doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
        text = "\n".join(page.get_text() for page in doc)

        print("Extracted Text from PDF:\n", text)  # Debugging step

        return self.parse_questions_and_answers(text)

    def extract_text_from_word(self, docx_file):
        """Extract text from a Word document and return (question, answer) pairs."""
        doc = docx.Document(docx_file)
        text = "\n".join([para.text.strip() for para in doc.paragraphs if para.text.strip()])

        # Extract text from tables (if questions are inside tables)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    text += "\n" + cell.text.strip()

        print("Extracted Text from Word Document (Including Tables):\n", text)  # Debugging step

        return self.parse_questions_and_answers(text)

    def parse_questions_and_answers(self, text):
        """
        Extract question, options, and answer from text formatted as:
        1. Question?
        A) Option A
        B) Option B
        C) Option C
        D) Option D
        Answer: C
        """
        qa_pairs = []

        # Match question block
        pattern = re.compile(
            r'(\d+)\.\s*(.*?)\n(A\).*?)\nAnswer\s*:\s*([A-D])',
            re.DOTALL | re.IGNORECASE
        )

        matches = pattern.findall(text)
        for match in matches:
            question_text = match[1].strip()
            options_block = match[2].strip()
            answer_label = match[3].strip().upper()

            # Parse options A) ... D)
            options = {}
            for opt_line in options_block.split('\n'):
                if opt_line.strip()[:2] in ['A)', 'B)', 'C)', 'D)']:
                    label = opt_line[:1].upper()
                    value = opt_line[2:].strip()
                    options[label] = value

            # Build option list (A, B, C, D)
            option_values = [options.get(k, "") for k in ['A', 'B', 'C', 'D']]
            correct_answer = options.get(answer_label, "")

            qa_pairs.append((question_text, option_values, correct_answer))

        print("Extracted MCQs:", qa_pairs)  # Debugging
        return qa_pairs



class CourseListView(generics.ListAPIView):
    serializer_class = CourseSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        """Return only published and non-deleted courses."""
        return Course.objects.filter(is_deleted=False, is_published=True,is_approved=True).select_related('instructor')

class InstructorCourseListView(generics.ListAPIView):
    serializer_class = CourseSerializer
    permission_classes = [IsAdminOrInstructor]

    def get_queryset(self):
        user = self.request.user

        if user.is_superuser:
            return Course.objects.filter(is_published=True)

        return Course.objects.filter(instructor__user=user, is_published=True)




class LessonListView(generics.ListAPIView):
    serializer_class = LessonSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Return only active (non-deleted) lessons of the course."""
        course_id = self.kwargs.get('course_id')
        return (
            Lesson.objects
            .filter(course_id=course_id, is_deleted=False)
            .select_related('quiz')            #  Use select_related for OneToOne
            .prefetch_related('concepts')       #  Prefetch concepts (many)
        )
    

class ConceptListView(generics.ListAPIView):
    serializer_class = ConceptSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Return only active (non-deleted) concepts within the lesson."""
        lesson_id = self.kwargs.get('lesson_id')
        return Concept.objects.filter(lesson_id=lesson_id, is_deleted=False).order_by('order')
    
class LessonContentListView(generics.ListAPIView):
    serializer_class = LessonContentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        concept_id = self.kwargs.get('concept_id')
        return LessonContent.objects.filter(concept_id=concept_id, is_deleted=False).order_by('order')
    

class LiveClassViewSet(viewsets.ModelViewSet):
    serializer_class = LiveClassSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'instructor':
            return LiveClass.objects.filter(instructor=user)
        elif user.role == 'student':
            return LiveClass.objects.filter(course__students=user, status='approved')
        elif user.is_superuser or user.role == 'admin':
            return LiveClass.objects.all()
        return LiveClass.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        if user.role != 'instructor':
            raise serializers.ValidationError({"error": "Only instructors can create live classes."})

        course_id = self.request.data.get("course")
        course = get_object_or_404(Course, id=course_id)

        if course.instructor != user:
            raise serializers.ValidationError({"error": "You can only create live classes for your own course."})

        serializer.save(instructor=user, course=course)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        """Admin approves a live class."""
        live_class = self.get_object()
        live_class.status = 'approved'
        live_class.save()

        #  Send email to students
        students = live_class.course.students.all()
        for student in students:
            send_mail(
                subject="New Live Class Scheduled!",
                message=f"Dear {student.username},\n\nA new live class '{live_class.title}' has been approved!\nScheduled Time: {live_class.scheduled_time}\nJoin Link: {live_class.meeting_link}\n\nThank you!",
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[student.email],
                fail_silently=False,
            )

        return Response({"message": "Live class approved and students notified."})

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def reject(self, request, pk=None):
        """Admin rejects a live class."""
        live_class = self.get_object()
        live_class.status = 'rejected'
        live_class.save()
        return Response({"message": "Live class rejected."})

class EnrollStudentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, course_id):
        user = request.user

        # Ensure user is a student
        if user.role != 'student':
            return Response({"error": "Only students can enroll in courses."}, status=403)

        course = get_object_or_404(Course, id=course_id)
        student = get_object_or_404(Student, user=user)

        # Check enrollment
        if course.students.filter(id=student.id).exists():
            return Response({"message": "Student is already enrolled."}, status=200)

        course.students.add(student)

        # Send confirmation email
        self.send_enrollment_confirmation(student, course)

        return Response({"message": "Enrolled successfully."}, status=201)

    def send_enrollment_confirmation(self, student, course):
        subject = f"Enrollment Confirmation - {course.title}"
        message = f"""
        Hello {student.user.username},

        Congratulations! You have been successfully enrolled in the course: "{course.title}".

        Course Details:
        - Title: {course.title}
        - Category: {course.category}
        - Instructor: {course.instructor.user.username}

        We are excited to have you on board! Start learning and enjoy your journey with us.

        Best Regards,
        Your Team
        """

        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = [student.user.email]

        try:
            send_mail(subject, message, from_email, recipient_list, fail_silently=False)
            print(f"✅ Confirmation email sent to {student.user.email}")
        except Exception as e:
            print(f"❌ Failed to send email: {e}")


class AutoCompleteContentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, course_id, content_id):
        if request.data.get("component_type") != 'video':
            return Response({"message": "Only video completion is tracked for course progress."}, status=status.HTTP_200_OK)

        student = get_object_or_404(Student, user=request.user)
        content = get_object_or_404(LessonContent, id=content_id)

        if not content.video:
            return Response({"error": "This content is not a video."}, status=status.HTTP_400_BAD_REQUEST)

        # Mark video as completed
        completion, _ = ContentCompletion.objects.get_or_create(student=student, content=content)
        completion.video_completed = True
        completion.save()

        # Update course progress
        progress, _ = StudentProgress.objects.get_or_create(student=student, course_id=course_id)
        if content not in progress.completed_contents.all():
            progress.completed_contents.add(content)

        total_videos = LessonContent.objects.filter(
            concept__lesson__course_id=course_id,
            video__isnull=False
        ).exclude(video='').count()

        completed_videos = progress.completed_contents.filter(
            video__isnull=False
        ).exclude(video='').count()

        progress.progress_percentage = (completed_videos / total_videos) * 100 if total_videos > 0 else 0
        progress.save()

        # Assignment check
        submissions = AssignmentSubmission.objects.filter(student=student, assignment__course_id=course_id)
        total = submissions.count()
        correct = submissions.filter(is_correct=True).count()
        assignment_passed = (correct / total) * 100 >= 75 if total else False

        return Response({
            "message": "Video marked complete.",
            "progress": round(progress.progress_percentage, 2),
            "certificate_eligible": progress.progress_percentage == 100.0 and assignment_passed
        }, status=status.HTTP_200_OK)


class CourseProgressView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, course_id):
        student = get_object_or_404(Student, user=request.user)
        course = get_object_or_404(Course, id=course_id)
        progress = StudentProgress.objects.filter(student=student, course=course).first()

        completed_content_ids = []
        lecture_completion = 0
        assignment_passed = False

        if progress:
            # ✅ Just take all completed content IDs
            completed_content_ids = list(progress.completed_contents.values_list('id', flat=True))

            # ✅ Total lecture contents in the course
            total_lectures = LessonContent.objects.filter(
                concept__lesson__course=course
            ).count()

            # ✅ Count of completed lecture contents
            completed_count = LessonContent.objects.filter(
                id__in=completed_content_ids,
                concept__lesson__course=course
            ).count()

            lecture_completion = round((completed_count / total_lectures) * 100, 2) if total_lectures else 0

        # ✅ Check assignment pass status
        assignment_passed = AssignmentSubmission.objects.filter(
            student=student,
            assignment__course=course,
            pass_status="Pass"
        ).exists()

        # ✅ Final course progress logic
        overall_progress = 100 if lecture_completion == 100 and assignment_passed else lecture_completion

        return Response({
            "progress_percentage": overall_progress,
            "lecture_completion": lecture_completion,
            "assignment_passed": assignment_passed,
            "completed_content_ids": completed_content_ids
        }, status=status.HTTP_200_OK)

    

class AssignmentListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        #  If the user is an instructor, allow them to fetch assignments for their course
        if hasattr(request.user, "instructor"):
            course = get_object_or_404(Course, id=course_id, instructor=request.user.instructor)
            assignments = Assignment.objects.filter(course=course)
            serializer = AssignmentSerializer(assignments, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        #  If the user is a student, check if they are enrolled in the course
        elif hasattr(request.user, "student"):
            student = get_object_or_404(Student, user=request.user)
            if not student.enrolled_courses.filter(id=course_id).exists():
                return Response({"error": "You are not enrolled in this course."}, status=status.HTTP_403_FORBIDDEN)

            # Fetch assignments for the course the student is enrolled in
            assignments = Assignment.objects.filter(course_id=course_id)
            serializer = AssignmentSerializer(assignments, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        #  If the user is neither a student nor an instructor, deny access
        return Response({"error": "Unauthorized access."}, status=status.HTTP_403_FORBIDDEN)

class SubmitAssignmentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, course_id):
        student = get_object_or_404(Student, user=request.user)
        course = get_object_or_404(Course, id=course_id)

        if not course.students.filter(id=student.id).exists():
            return Response({"error": "You are not enrolled in this course."}, status=403)

        submitted_answers = request.data.get('answers', {})
        all_assignments = Assignment.objects.filter(course=course)
        total_questions = all_assignments.count()
        correct_answers = 0
        evaluation_details = []

        for assignment in all_assignments:
            submitted_answer = submitted_answers.get(str(assignment.id), "").strip()
            correct_answer = assignment.answer.strip().lower()
            is_correct = submitted_answer.lower() == correct_answer if submitted_answer else False

            if is_correct:
                correct_answers += 1

            AssignmentSubmission.objects.update_or_create(
                student=student,
                assignment=assignment,
                defaults={
                    "submitted_answer": submitted_answer,
                    "is_correct": is_correct,
                    "score": 100 if is_correct else 0,
                    "pass_status": "Pass" if is_correct else "Fail",
                },
            )

            evaluation_details.append({
                "assignment_question": assignment.question,
                "submitted_answer": submitted_answer if submitted_answer else "Not Attempted",
                "correct_answer": assignment.answer,
                "is_correct": is_correct
            })

        overall_score = (correct_answers / total_questions) * 100 if total_questions > 0 else 0
        pass_status = "Pass" if overall_score >= 75 else "Fail"

       

        return Response({
            "total_questions": total_questions,
            "correct_answers": correct_answers,
            "score": overall_score,
            "pass_status": pass_status,
            "evaluation": evaluation_details,
           
        }, status=200)
        

class StudentAssignmentResultView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        student = get_object_or_404(Student, user=request.user)
        course = get_object_or_404(Course, id=course_id)

        # Check if student is enrolled
        if not course.students.filter(id=student.id).exists():
            return Response({"error": "You are not enrolled in this course."}, status=403)

        # Get all submitted assignment results for this student in the course
        assignment_results = AssignmentSubmission.objects.filter(student=student, assignment__course=course)

        # If no submissions exist, return empty response
        if not assignment_results.exists():
            return Response({"message": "No assignments attempted yet.", "score": 0, "pass_status": "Fail"}, status=200)

        # Calculate the total score
        total_assignments = assignment_results.count()
        correct_answers = assignment_results.filter(is_correct=True).count()
        total_score = sum(result.score for result in assignment_results)

        # Compute overall percentage
        overall_score = (correct_answers / total_assignments) * 100 if total_assignments > 0 else 0
        pass_status = "Pass" if overall_score >= 75 else "Fail"

        # Serialize assignment results
        serializer = AssignmentResultSerializer(assignment_results, many=True)

        return Response({
            "total_questions": total_assignments,
            "correct_answers": correct_answers,
            "score": overall_score,
            "pass_status": pass_status,
            "evaluation": serializer.data
        }, status=200)






class EnrolledStudentsListView(generics.ListAPIView):
    serializer_class = StudentSerializer  # Corrected
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        course_id = self.kwargs.get('course_id')
        course = get_object_or_404(Course, id=course_id)
        return course.students.all()  # returns Student instances
    

class CourseChatView(APIView):
    permission_classes = [IsAuthenticated]

    def is_authorized(self, user, course):
        """Allow access to instructor who owns the course or enrolled student"""
        if hasattr(user, 'instructor') and user.instructor == course.instructor:
            return True
        if hasattr(user, 'student') and course.students.filter(id=user.student.id).exists():
            return True
        return False

    def get(self, request, course_id):
        course = get_object_or_404(Course, id=course_id)

        if not self.is_authorized(request.user, course):
            return Response({"error": "Access denied."}, status=403)

        messages = CourseChatMessage.objects.filter(course=course).order_by("timestamp")
        serializer = CourseChatMessageSerializer(messages, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request, course_id):
        course = get_object_or_404(Course, id=course_id)

        if not self.is_authorized(request.user, course):
            return Response({"error": "Access denied."}, status=403)

        message_text = request.data.get("message")
        reply_to_id = request.data.get("reply_to")  # Optional
        attachment = request.FILES.get("attachment")

        if not message_text or message_text.strip() == "":
            return Response({"error": "Message is required."}, status=400)

        reply_to_msg = None
        if reply_to_id:
            reply_to_msg = CourseChatMessage.objects.filter(id=reply_to_id, course=course).first()

        chat_message = CourseChatMessage.objects.create(
            course=course,
            sender=request.user,
            message=message_text.strip(),
            reply_to=reply_to_msg,
            attachment=attachment
        )

        serializer = CourseChatMessageSerializer(chat_message, context={'request': request})
        return Response(serializer.data, status=201)

    def put(self, request, course_id):
        course = get_object_or_404(Course, id=course_id)

        msg_id = request.data.get('id')
        new_msg = request.data.get('message')

        if not self.is_authorized(request.user, course):
            return Response({"error": "Access denied."}, status=403)

        if not new_msg or new_msg.strip() == "":
            return Response({"error": "Edited message cannot be empty."}, status=400)

        msg = get_object_or_404(CourseChatMessage, id=msg_id, sender=request.user, course_id=course_id, is_deleted=False)
        msg.message = new_msg.strip()
        msg.is_edited = True
        msg.save()
        return Response({"message": "Message edited successfully."})

    def delete(self, request, course_id):
        course = get_object_or_404(Course, id=course_id)

        if not self.is_authorized(request.user, course):
            return Response({"error": "Access denied."}, status=403)

        msg_id = request.data.get('id')
        msg = get_object_or_404(CourseChatMessage, id=msg_id, sender=request.user, course_id=course_id)

        if msg.is_deleted:
            return Response({"error": "Message already deleted."}, status=400)

        msg.is_deleted = True
        msg.save()
        return Response({"message": "Message deleted successfully."})

class PrivateMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id, user_id):  # user_id = instructor.id
        current_user = request.user
        other_user = get_object_or_404(User, id=user_id)

        # Include messages sent by either side
        messages = PrivateMessage.objects.filter(
            course_id=course_id
        ).filter(
            Q(sender=current_user, receiver=other_user) |
            Q(sender=other_user, receiver=current_user)
        ).order_by("timestamp")

        serializer = PrivateMessageSerializer(messages, many=True, context={'request': request})
        return Response(serializer.data)

        


    def post(self, request, course_id, user_id):
        course = get_object_or_404(Course, id=course_id)
        receiver = get_object_or_404(User, id=user_id)

        if request.user != course.instructor.user and not course.students.filter(user=request.user).exists():
            return Response({"error": "Access denied."}, status=403)

        serializer = PrivateMessageSerializer(data=request.data)
        if serializer.is_valid():
            reply_to_id = request.data.get("reply_to")  # Get reply ID from request
            reply_to = None
            if reply_to_id:
                reply_to = PrivateMessage.objects.filter(id=reply_to_id).first()

            serializer.save(sender=request.user, receiver=receiver, course=course, reply_to=reply_to)
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class PrivateChatStudentListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        course_id = request.query_params.get('course_id')  # get course from query param

        if user.role != 'instructor':
            return Response({"error": "Only instructors can access this."}, status=403)

        if not course_id:
            return Response({"error": "course_id is required."}, status=400)

        course = get_object_or_404(Course, id=course_id)

        if course.instructor.user != user:
            return Response({"error": "You can only view messages for your own courses."}, status=403)

        student_ids = PrivateMessage.objects.filter(
            receiver=user,
            course=course
        ).values_list('sender', flat=True).distinct()

        students = Student.objects.filter(user__id__in=student_ids)
        serializer = StudentSerializer(students, many=True)
        return Response(serializer.data)

    
class PrivateChatThreadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser,JSONParser,)

    def get(self, request, user_id):
        current_user = request.user
        other_user = get_object_or_404(User, id=user_id)
        course_id = request.query_params.get("course_id")

        if not course_id:
            return Response({"error": "course_id is required"}, status=400)

        messages = PrivateMessage.objects.filter(
            course_id=course_id
        ).filter(
            (models.Q(sender=current_user) & models.Q(receiver=other_user)) |
            (models.Q(sender=other_user) & models.Q(receiver=current_user))
        ).order_by('timestamp')

        messages.filter(receiver=current_user, is_read=False).update(is_read=True)

        serializer = PrivateMessageSerializer(messages, many=True, context={'request': request})
        return Response(serializer.data)

    
    def post(self, request, user_id):
        sender = request.user
        receiver = get_object_or_404(User, id=user_id)
        message = request.data.get("message", "")
        attachment = request.FILES.get("attachment")
        course_id = request.data.get("course_id")
        reply_to_id = request.data.get("reply_to")

        if not message.strip() and not attachment:
            return Response({"error": "Message or attachment is required."}, status=400)

        course = get_object_or_404(Course, id=course_id)
        reply_to = PrivateMessage.objects.filter(id=reply_to_id).first() if reply_to_id else None

        # 🔐 Check access: sender and receiver must be part of the course
        if not (
            (course.instructor.user == sender or course.students.filter(user=sender).exists()) and
            (course.instructor.user == receiver or course.students.filter(user=receiver).exists())
        ):
            return Response({"error": "Access denied. Users must belong to the course."}, status=403)

        msg = PrivateMessage.objects.create(
            sender=sender,
            receiver=receiver,
            message=message.strip(),
            attachment=attachment,
            course=course,
            reply_to=reply_to
        )

        return Response({
            'id': msg.id,
            'sender_username': msg.sender.username,
            'receiver_username': msg.receiver.username,
            'message': msg.message,
            'attachment': msg.attachment.url if msg.attachment else None,
            'timestamp': msg.timestamp,
        }, status=201)
    
class EditPrivateMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, message_id):
        message = get_object_or_404(PrivateMessage, id=message_id)

        if request.user != message.sender:
            return Response({"error": "You can only edit your own messages."}, status=403)
        


        new_message = request.data.get("message")
        if new_message is None or new_message.strip() == "":
            return Response({"error": "Message cannot be empty."}, status=400)

        message.message = new_message.strip()
        message.is_edited = True
        message.save()
        return Response({"message": "Message updated successfully."})
    

class DeletePrivateMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, message_id):
        message = get_object_or_404(PrivateMessage, id=message_id)

        if request.user != message.sender:
            return Response({"error": "You can only delete your own messages."}, status=403)

        
        message.delete()  # ✅ Just mark as deleted, don't remove from DB
        return Response({"message": "Message deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
    


class PrivateChatInstructorListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.role != 'student':
            return Response({"error": "Only students can access this."}, status=403)

        instructor_course_pairs = PrivateMessage.objects.filter(
            Q(sender=user) | Q(receiver=user)
        ).values('course_id', 'course__instructor__user__id').distinct()

        results = []
        seen_pairs = set()

        for pair in instructor_course_pairs:
            course_id = pair['course_id']
            instructor_user_id = pair['course__instructor__user__id']

            if (instructor_user_id, course_id) in seen_pairs:
                continue
            seen_pairs.add((instructor_user_id, course_id))

            instructor = get_object_or_404(Instructor, user__id=instructor_user_id)

            # 🛠 Get last message
            last_msg = PrivateMessage.objects.filter(
                Q(
                    course_id=course_id,
                    sender=user,
                    receiver__id=instructor_user_id
                ) |
                Q(
                    course_id=course_id,
                    sender__id=instructor_user_id,
                    receiver=user
                )
            ).order_by('-timestamp').first()

            # 🛠 Count unread messages
            unread_count = PrivateMessage.objects.filter(
                course_id=course_id,
                sender__id=instructor_user_id,
                receiver=user,
                is_read=False
            ).count()

            results.append({
                "instructor_id": instructor_user_id,
                "instructor_name": instructor.user.username,
                "profile": instructor.profile_picture.url if instructor.profile_picture else None,
                "course_id": course_id,
                "last_message": last_msg.message if last_msg else "",
                "last_message_time": last_msg.timestamp if last_msg else None,  # ⏰ Add timestamp here
                "unread_count": unread_count
            })

        return Response(results)



class MarkMessagesAsSeenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        course_id = request.data.get("course_id")
        sender_id = request.data.get("sender_id")

        if not course_id or not sender_id:
            return Response({"error": "course_id and sender_id required."}, status=400)

        # Only mark messages sent TO the current user, for the given course and sender
        PrivateMessage.objects.filter(
            course_id=course_id,
            sender_id=sender_id,
            receiver=user,
            is_read=False
        ).update(is_read=True)

        return Response({"status": "Messages marked as seen."})


class CertificateTemplateViewSet(viewsets.ModelViewSet):
    serializer_class = CertificateTemplateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        instructor = getattr(self.request.user, 'instructor', None)
        if instructor:
            return CertificateTemplate.objects.filter(
                models.Q(instructor=instructor) | models.Q(type="default")
            )
        return CertificateTemplate.objects.filter(type="default")

    def perform_create(self, serializer):
        instructor = getattr(self.request.user, 'instructor', None)
        if instructor:
            serializer.save(instructor=instructor)
        else:
            raise PermissionDenied("Only instructors can upload certificate templates.")

    def perform_update(self, serializer):
        obj = self.get_object()
        user_instructor = getattr(self.request.user, 'instructor', None)
        if obj.type == "default":
            raise PermissionDenied("Default templates cannot be modified.")
        if obj.instructor.id != user_instructor.id:
            raise PermissionDenied("You can only update your own certificate templates.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.type == "default":
            raise PermissionDenied("Default templates cannot be deleted.")
        if instance.instructor.id != self.request.user.instructor.id:
            raise PermissionDenied("You can only delete your own certificate templates.")
        instance.delete()


class SetCertificateTemplateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, course_id):
        course = get_object_or_404(Course, id=course_id)

        # ✅ Check instructor ownership
        if hasattr(request.user, "instructor") and request.user.instructor != course.instructor:
            return Response({"error": "You can only modify your own courses."}, status=403)

        template_id = request.data.get("template_id")

        if not template_id:
            return Response({"error": "Please provide a valid template_id."}, status=400)

        template = get_object_or_404(CertificateTemplate, id=template_id)
        course.certificate_template = template
        course.save()

        return Response({"message": "Template assigned successfully."}, status=200)

class CheckAndIssueCertificateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, course_id):
        student = get_object_or_404(Student, user=request.user)
        course = get_object_or_404(Course, id=course_id)

        if Certificate.objects.filter(student=student, course=course).exists():
            return Response({"message": "Certificate already issued."}, status=200)

        progress = StudentProgress.objects.filter(student=student, course=course).first()
        if not progress or progress.progress_percentage < 100:
            return Response({"error": "You must complete 100% of the course."}, status=400)

        submissions = AssignmentSubmission.objects.filter(student=student, assignment__course=course)
        if not submissions.exists():
            return Response({"error": "You must attempt the assignments to receive a certificate."}, status=400)

        average_score = sum(s.score for s in submissions) / len(submissions)
        if average_score < 75:
            return Response({"error": "Your average assignment score must be at least 75% to receive a certificate."}, status=400)

        if not course.certificate_template:
            return Response({"error": "No certificate template assigned to this course."}, status=400)
        certificate_id = str(uuid.uuid4())
        pdf = generate_certificate(student, course, course.certificate_template, certificate_id)

        certificate = Certificate.objects.create(
            student=student,
            course=course,
            certificate_id=certificate_id,
            pdf_file=pdf
        )

        return Response({
            "message": "🎉 Certificate issued successfully!",
            "certificate_url": certificate.pdf_file.url
        }, status=201)


class CertificateDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        student = get_object_or_404(Student, user=request.user)
        course = get_object_or_404(Course, id=course_id)

        certificate = Certificate.objects.filter(student=student, course=course).first()
        if certificate:
            return Response({
                "certificate_url": certificate.pdf_file.url,
                "certificate_id": str(certificate.certificate_id),
                "issue_date": certificate.issue_date
            })
        return Response({"error": "Certificate not found for this course."}, status=404)
    

class VerifyCertificateView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, certificate_id):
        certificate = Certificate.objects.filter(certificate_id=certificate_id).first()
        if not certificate:
            return Response({"valid": False, "message": "Certificate not found."}, status=404)

        return Response({
            "valid": True,
            "student": certificate.student.user.username,
            "course": certificate.course.title,
            "issued_on": certificate.issue_date.strftime('%Y-%m-%d'),
        })

class SaveNoteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, concept_id):
        student = get_object_or_404(Student, user=request.user)
        concept = get_object_or_404(Concept, id=concept_id)

        note_text = request.data.get("note", "")

        note_obj, created = StudentNote.objects.update_or_create(
            student=student,
            concept=concept,
            defaults={'note': note_text}
        )

        serializer = StudentNoteSerializer(note_obj)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class GetNoteView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, concept_id):
        student = get_object_or_404(Student, user=request.user)
        note = StudentNote.objects.filter(student=student, concept_id=concept_id).first()

        if not note:
            return Response({"note": ""}, status=200)
        
        serializer = StudentNoteSerializer(note)
        return Response(serializer.data, status=200)



class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

    @action(detail=True, methods=['get'])
    def courses(self, request, pk=None):
        category = self.get_object()
        courses = category.courses.all()
        serializer = CourseSerializer(courses, many=True)
        return Response(serializer.data)

class SubCategoryViewSet(viewsets.ModelViewSet):
    queryset = SubCategory.objects.all()
    serializer_class = SubCategorySerializer

class CategoryCourseCountView(APIView):
    def get(self, request):
        data = Category.objects.annotate(
            course_count=Count('courses', filter=Q(courses__is_approved=True))
        ).values('id', 'name', 'course_count')
        return Response(data)


class CategoryWithSubcategoryView(APIView):
    def get(self, request):
        categories = Category.objects.all()
        serializer = CategoryWithSubSerializer(categories, many=True)
        return Response(serializer.data)


class SubmitCourseFeedback(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, course_id):
        student = get_object_or_404(Student, user=request.user)
        course = get_object_or_404(Course, id=course_id)

        # Prevent duplicate feedback
        if CourseFeedback.objects.filter(student=student, course=course).exists():
            return Response({"error": "Feedback already submitted for this course."}, status=400)

        serializer = CourseFeedbackSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(student=student, course=course)
            return Response({"message": "Feedback submitted successfully."}, status=201)
        return Response(serializer.errors, status=400)

class CourseFeedbackList(APIView):
    permission_classes = [AllowAny]

    def get(self, request, course_id):
        course = get_object_or_404(Course, id=course_id)
        feedbacks = CourseFeedback.objects.filter(course=course)
        serializer = CourseFeedbackSerializer(feedbacks, many=True)
        return Response(serializer.data)

class AddToWishlistView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, course_id):
        student = get_object_or_404(Student, user=request.user)
        course = get_object_or_404(Course, id=course_id)

        # Check if already added
        if Wishlist.objects.filter(student=student, course=course).exists():
            return Response({"message": "Already in wishlist."}, status=200)

        Wishlist.objects.create(student=student, course=course)
        return Response({"message": "Course added to wishlist."}, status=201)

class RemoveFromWishlistView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, course_id):
        student = get_object_or_404(Student, user=request.user)
        wishlist_entry = Wishlist.objects.filter(student=student, course__id=course_id).first()

        if not wishlist_entry:
            return Response({"error": "Course not found in wishlist."}, status=404)

        wishlist_entry.delete()
        return Response({"message": "Course removed from wishlist."}, status=204)

class WishlistListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        student = get_object_or_404(Student, user=request.user)
        wishlist = Wishlist.objects.filter(student=student)
        serializer = WishlistSerializer(wishlist, many=True)
        return Response(serializer.data)


class JobPostCreateView(APIView):
    def get(self, request):
        job_id = request.GET.get('id')
        
        if job_id:
            try:
                job_post = Job.objects.get(pk=job_id)
                serializer = JobPostSerializer(job_post)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except Job.DoesNotExist:
                return Response({'error': 'Job post not found'}, status=status.HTTP_404_NOT_FOUND)
        
        job_posts = Job.objects.all()
        serializer = JobPostSerializer(job_posts, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = JobPostSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
# from django.views.decorators.csrf import csrf_exempt
# from django.utils.decorators import method_decorator

# @method_decorator(csrf_exempt, name='dispatch')
class JobApplicationsView(APIView):
    # def get_permissions(self):
    #     if self.request.method == 'POST':
    #         return [AllowAny()]
    #     return [IsAuthenticated()]
    permission_classes=[AllowAny]

    def get(self, request):
        try:
            job_id = request.GET.get('job_id')
            job_post = Job.objects.get(pk=job_id)
        except Job.DoesNotExist:
            return Response({"error": "Job not found."}, status=status.HTTP_404_NOT_FOUND)

        applications = JobApplications.objects.filter(job=job_post)
        serializer = JobApplicationSerializer(applications, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        print("calling this view")
        # Get the job
        jobid = request.GET.get('job_id')  # or request.data.get('job')
        print("jobid", jobid)
        try:
            job_post = Job.objects.get(pk=jobid)
        except Job.DoesNotExist:
            return Response({"error": "Job not found."}, status=status.HTTP_404_NOT_FOUND)

        # Extract form fields
        
        print("request .data", request.data)
        
        name = request.data.get('name')
        email = request.data.get('email')
        phone = request.data.get('phone')
        education = request.data.get('education')
        experience = request.data.get('experience')
        message = request.data.get('message')

        # print("resumeeeeee",request.FILES.get('resume'))
        resume_file = request.FILES.get('resume')  # Ensure frontend sends actual file

        
        # Manually create JobApplication object
        if JobApplications.objects.filter(job=job_post, email=email).exists():
            return Response(
                {"message": "You have already applied for this job."},
                status=status.HTTP_400_BAD_REQUEST
            )
        job_application = JobApplications.objects.create(
            job=job_post,
            name=name,
            email=email,
            phone_number=phone,
            education=education,
            experience=experience,
            cover_letter=message,
            resume=resume_file,
        )

        return Response({
            "message": "Application submitted successfully.",
            "application_id": job_application.id,
        }, status=status.HTTP_201_CREATED)
    

# new code



class InstructorCourseCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        user = request.user
        if not hasattr(user, 'instructor'):
            return Response({"error": "Only instructors can create courses."}, status=403)

        course = Course.objects.create(
            title=request.data.get('title'),
            subtitle=request.data.get('subtitle'),
            topic=request.data.get('topic'),
            category=get_object_or_404(Category, id=request.data.get('category_id')),
            subcategory=get_object_or_404(SubCategory, id=request.data.get('subcategory_id')),
            instructor=user.instructor,
            language=request.data.get('language'),
            subtitle_language=request.data.get('subtitle_language'),
            course_level=request.data.get('course_level'),
            time_duration=request.data.get('time_duration'),
            is_published=False,
            creation_step='basic',
            price=request.data.get('price') or 0,
            discount=request.data.get('discount') or 0,
            coupon_code=request.data.get('coupon_code') or None
        )

        return Response({
            "course_id": course.id,
            "message": "Draft created. Proceed to next step."
        }, status=201)

    def get(self, request, course_id):
        user = request.user
        course = get_object_or_404(
            Course, 
            id=course_id, 
            instructor__user=user,
            
        )

        return Response({
            "id": course.id,
            "title": course.title,
            "subtitle": course.subtitle,
            "topic": course.topic,
            "category_id": course.category.id if course.category else None,
            "subcategory_id": course.subcategory.id if course.subcategory else None,
            "language": course.language,
            "subtitle_language": course.subtitle_language,
            "course_level": course.course_level,
            "time_duration": course.time_duration,
            "price": course.price,
            "discount": course.discount,
            "coupon_code": course.coupon_code
        })

    def put(self, request, course_id):
        user = request.user
        course = get_object_or_404(
            Course, 
            id=course_id, 
            instructor__user=user,
            
        )

        # Update fields
        course.title = request.data.get('title', course.title)
        course.subtitle = request.data.get('subtitle', course.subtitle)
        course.topic = request.data.get('topic', course.topic)
        course.language = request.data.get('language', course.language)
        course.subtitle_language = request.data.get('subtitle_language', course.subtitle_language)
        course.course_level = request.data.get('course_level', course.course_level)
        course.time_duration = request.data.get('time_duration', course.time_duration)
        course.price = request.data.get('price', course.price)
        course.discount = request.data.get('discount', course.discount)
        course.coupon_code = request.data.get('coupon_code', course.coupon_code)

        if 'category_id' in request.data:
            course.category = get_object_or_404(Category, id=request.data.get('category_id'))
        if 'subcategory_id' in request.data:
            course.subcategory = get_object_or_404(SubCategory, id=request.data.get('subcategory_id'))

        course.save()

        return Response({"message": "Course basic information updated successfully."})



class CourseAdvancedInfoUpdateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def put(self, request, course_id):
        course = get_object_or_404(Course, id=course_id, instructor__user=request.user)

        course.description = request.data.get("description", course.description)
        course.learning_objectives = request.data.getlist("objectives[]", course.learning_objectives)
        course.requirements = request.data.getlist("requirements[]", course.requirements)
        course.target_audiences = request.data.getlist("target_audiences[]", course.target_audiences)
        course.course_image = request.FILES.get("course_image", course.course_image)
        course.demo_video = request.FILES.get("demo_video", course.demo_video)
        course.creation_step = "advanced"
        course.save()

        return Response({"message": "Advanced Info updated.", "course_id": course.id})

    def get(self, request, course_id):
        course = get_object_or_404(Course, id=course_id, instructor__user=request.user)
        return Response({
            "description": course.description,
            "learning_objectives": course.learning_objectives,
            "requirements": course.requirements,
            "target_audiences": course.target_audiences,
            "course_image": course.course_image.url if course.course_image else None,
            "demo_video": course.demo_video.url if course.demo_video else None
        })

    



class CourseCurriculumCompleteView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]  # To handle FormData + file uploads

    def get(self, request, course_id):
        course = get_object_or_404(Course, id=course_id, instructor__user=request.user)

        lessons = []
        for lesson in Lesson.objects.filter(course=course, is_deleted=False):
            concepts = []
            for concept in Concept.objects.filter(lesson=lesson, is_deleted=False).order_by('order'):
                contents = []
                for content in LessonContent.objects.filter(concept=concept, is_deleted=False).order_by('order'):
                    # Get quiz questions
                    quiz_questions = QuizQuestion.objects.filter(lesson_content=content)

                    contents.append({
                        "content_type": content.content_type,
                        "video": content.video.name if content.video else None,
                        "pdf": content.pdf.name if content.pdf else None,
                        "text_content": content.text_content,
                        "captions": content.captions,
                        "attached_file": content.attached_file.name if content.attached_file else None,
                        "lecture_notes_text": content.lecture_notes_text,
                        "lecture_notes_file": content.lecture_notes_file.name if content.lecture_notes_file else None,
                        "order": content.order,
                        "quiz_title": content.quiz_questions.first().quiz.title if quiz_questions.exists() else None,
                        "quiz_questions": [
                            {
                                "question_text": q.question_text,
                                "correct_answer": q.correct_answer,
                                "options": q.options
                            } for q in quiz_questions
                        ]
                    })

                concepts.append({
                    "title": concept.title,
                    "contents": contents
                })

            lessons.append({
                "title": lesson.title,
                "concepts": concepts
            })

        assignments = Assignment.objects.filter(course=course).values(
            "question", "answer", "options"
        )

        return Response({
            "lessons": lessons,
            "assignments": list(assignments)
        })

    def put(self, request, course_id):
        course = get_object_or_404(Course, id=course_id)

        if request.user != course.instructor.user:
            return Response({"error": "Unauthorized access"}, status=403)

        # Parse JSON strings from FormData
        try:
            lessons_data = json.loads(request.data.get("lessons", "[]"))
            assignments_data = json.loads(request.data.get("assignments", "[]"))
        except json.JSONDecodeError:
            return Response({"error": "Invalid JSON format."}, status=400)

        for lesson_data in lessons_data:
            lesson_title = lesson_data.get("title")
            lesson, _ = Lesson.objects.get_or_create(course=course, title=lesson_title)

            for concept_data in lesson_data.get("concepts", []):
                concept_title = concept_data.get("title")
                concept, _ = Concept.objects.get_or_create(lesson=lesson, title=concept_title)

                # Get existing orders under this concept to avoid duplicates
                used_orders = set(LessonContent.objects.filter(concept=concept).values_list("order", flat=True))
                next_order = max(used_orders, default=0) + 1

                content_data = concept_data.get("contents", [None])[0]  # Grab the first (or None)
                if content_data:
                    order = next_order
                    next_order += 1


                    # File field keys
                    video_key = content_data.get("video")
                    pdf_key = content_data.get("pdf")
                    attached_key = content_data.get("attached_file")
                    lecture_notes_key = content_data.get("lecture_notes_file")

                    # File objects
                    video_file = request.FILES.get(video_key) if video_key else None
                    pdf_file = request.FILES.get(pdf_key) if pdf_key else None
                    attached_file = request.FILES.get(attached_key) if attached_key else None
                    lecture_notes_file = request.FILES.get(lecture_notes_key) if lecture_notes_key else None

                    # Create a single LessonContent object
                    lesson_content = LessonContent.objects.create(
                        concept=concept,
                        content_type='text',  # or determine dynamically
                        order=order,
                        video=video_file,
                        pdf=pdf_file,
                        text_content=content_data.get("text_content", ""),
                        captions=content_data.get("captions"),
                        attached_file=attached_file,
                        lecture_notes_text=content_data.get("lecture_notes_text"),
                        lecture_notes_file=lecture_notes_file,
                    )

                    # Handle quiz
                    quiz_title = content_data.get("quiz_title")
                    quiz_questions = content_data.get("quiz_questions", [])

                    if quiz_title or quiz_questions:
                        quiz, created = Quiz.objects.get_or_create(
                            lesson=lesson,
                            defaults={"title": quiz_title or f"{lesson.title} Quiz", "instructor": request.user}
                        )
                        if not created and quiz_title:
                            quiz.title = quiz_title
                            quiz.save()

                        for q in quiz_questions:
                            QuizQuestion.objects.create(
                                quiz=quiz,
                                lesson_content=lesson_content,
                                question_text=q.get("question_text"),
                                correct_answer=q.get("correct_answer"),
                                options=q.get("options", []),
                            )

        # Save Assignments
        instructor = course.instructor
        for item in assignments_data:
            question = item.get("question")
            answer = item.get("answer")
            if question and answer:
                Assignment.objects.create(
                    instructor=instructor,
                    course=course,
                    question=question,
                    options=item.get("options", []),
                    answer=answer,
                )

        return Response({"message": "Curriculum and assignments updated successfully."})

class PublishCourseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, course_id):
        course = get_object_or_404(Course, id=course_id, instructor__user=request.user)

        course.welcome_message = request.data.get("welcome_message", course.welcome_message)
        course.congratulation_message = request.data.get("congratulation_message", course.congratulation_message)
        course.creation_step = "published"
        course.save()

        return Response({"message": "Course publish info saved."})

    def get(self, request, course_id):
        course = get_object_or_404(Course, id=course_id, instructor__user=request.user)
        return Response({
            "welcome_message": course.welcome_message,
            "congratulation_message": course.congratulation_message,
            "creation_step": course.creation_step,
            "is_published": course.is_published
        })



class FinalPublishCourseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, course_id):
        course = get_object_or_404(Course, id=course_id, instructor__user=request.user)

        if course.is_published:
            return Response({"message": "Course is already published."}, status=400)

        # Mark course as fully published
        course.is_published = True
        course.creation_step = "complete"
        course.save()

        return Response({"message": "Course published successfully."})
    


class CourseReviewAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        course = get_object_or_404(Course, id=course_id, instructor__user=request.user)
        instructor = course.instructor
        lessons = Lesson.objects.filter(course=course, is_deleted=False)

        lesson_data = []
        for lesson in lessons:
            concepts = Concept.objects.filter(lesson=lesson, is_deleted=False).order_by('order')
            concept_data = []

            for concept in concepts:
                contents = LessonContent.objects.filter(concept=concept, is_deleted=False).order_by('order')
                content_data = []

                for content in contents:
                    # Fetch quiz questions directly related to the content
                    quiz_questions = QuizQuestion.objects.filter(lesson_content=content)

                    quiz_data = {
                        "questions": [
                            {
                                "question_text": q.question_text,
                                "correct_answer": q.correct_answer,
                                "options": q.options,
                            }
                            for q in quiz_questions
                        ]
                    } if quiz_questions.exists() else None

                    content_data.append({
                        "id": content.id,
                        "content_type": content.content_type,
                        "video": content.video.url if content.video else None,
                        "pdf": content.pdf.url if content.pdf else None,
                        "text_content": content.text_content,
                        "captions": content.captions,
                        "attached_file": content.attached_file.url if content.attached_file else None,
                        "lecture_notes_text": content.lecture_notes_text,
                        "lecture_notes_file": content.lecture_notes_file.url if content.lecture_notes_file else None,
                        "order": content.order,
                        "quiz": quiz_data
                    })

                concept_data.append({
                    "id": concept.id,
                    "title": concept.title,
                    "description": concept.description,
                    "order": concept.order,
                    "contents": content_data,
                })

            lesson_data.append({
                "id": lesson.id,
                "title": lesson.title,
                "concepts": concept_data,
                # Optional: include lesson-level quiz
                "quiz": {
                    "id": lesson.quiz.id,
                    "title": lesson.quiz.title,
                    "questions": [
                        {
                            "question_text": q.question_text,
                            "correct_answer": q.correct_answer,
                            "options": q.options,
                        } for q in lesson.quiz.questions.all()
                    ]
                } if hasattr(lesson, "quiz") else None
            })

        # ✅ Assignments for the course
        assignments = Assignment.objects.filter(course=course).values(
            "id", "question", "options", "answer"
        )

        # ✅ Assigned certificate template
        certificate = getattr(course, "certificate_template", None)
        certificate_data = {
            "id": certificate.id,
            "name": certificate.name,
            "preview_image": certificate.preview_image.url if certificate.preview_image else None,
            "html_template": certificate.html_template,
        } if certificate else None

        # ✅ Final combined course data
        course_data = {
            "id": course.id,
            "title": course.title,
            "subtitle": course.subtitle,
            "description": course.description,
            "language": course.language,
            "course_level": course.course_level,
            "demo_video": course.demo_video.url if course.demo_video else None,
            "creation_step": course.creation_step,
            "is_published": course.is_published,
            "created_at": course.created_at,
            "instructor": {
                "id": instructor.id,
                "user_id": instructor.user.id,
                "name": f"{instructor.user.first_name} {instructor.user.last_name}",
                "email": instructor.user.email,
                "profile_picture": instructor.profile_picture.url if instructor.profile_picture else None,
                "headline": instructor.headline,
                "biography": instructor.biography,
            },
            "lessons": lesson_data,
            "assignments": list(assignments),
            "certificate": certificate_data
        }

        return Response(course_data)
    




class CourseDetailFullView(APIView):
    def get(self, request, course_id):
        course = get_object_or_404(Course, id=course_id)

        course_data = {
            "id": course.id,
            "title": course.title,
            "subtitle": course.subtitle,
            "topic": course.topic,
            "description": course.description,
            "price": float(course.price),
            "discount": float(course.discount),
            "coupon_code": course.coupon_code,
            "language": course.language,
            "subtitle_language": course.subtitle_language,
            "level": course.course_level,
            "time_duration": course.time_duration,
            "course_image": course.course_image.url if course.course_image else None,
            "demo_video": course.demo_video.url if course.demo_video else None,
            "requirements": course.requirements,
            "learning_objectives": course.learning_objectives,
            "target_audiences": course.target_audiences,
            "welcome_message": course.welcome_message,
            "congratulation_message": course.congratulation_message,
            "is_published": course.is_published,
            "creation_step": course.creation_step,
            "students_enrolled": course.students.count(),
            "created_at": course.created_at,
           
        }

        # Category/Subcategory names
        course_data["category"] = course.category.name if course.category else None
        course_data["subcategory"] = course.subcategory.name if course.subcategory else None

        # Instructor details
        instructor = course.instructor
        course_data["instructor"] = {
            "id": instructor.id,
            "name": instructor.user.get_full_name() if hasattr(instructor, "user") else instructor.name,
            "headline": instructor.headline,
            "bio": instructor.biography,
            "profile_picture": instructor.profile_picture.url if instructor.profile_picture else None,
        }

        # Certificate Template
        certificate = course.certificate_template
        if certificate:
            course_data["certificate_template"] = {
                "title": certificate.name,
                "preview_image": certificate.preview_image.url if certificate.preview_image else None,
                "html_template": certificate.html_template,
            }

        # Curriculum with lessons, concepts, quizzes
        curriculum = []
        lessons = Lesson.objects.filter(course=course, is_deleted=False)
        for lesson in lessons:
            concepts = Concept.objects.filter(lesson=lesson, is_deleted=False)
            quizzes = Quiz.objects.filter(lesson=lesson)
            curriculum.append({
                "lesson_title": lesson.title,
                "concept_count": concepts.count(),
                "concepts": [{"title": c.title} for c in concepts],
                "quizzes": [{"title": q.title} for q in quizzes],
            })

        course_data["curriculum"] = curriculum

        # Assignments
        assignments = Assignment.objects.filter(course=course)
        course_data["assignments"] = [{"question": a.question} for a in assignments]

        # Related courses by category
        related_by_category = Course.objects.filter(
            category=course.category, is_published=True
        ).exclude(id=course.id)[:4]
        course_data["related_by_category"] = [
            {
                "id": c.id,
                "title": c.title,
                "subtitle": c.subtitle,
                "thumbnail": c.course_image.url if c.course_image else None
            } for c in related_by_category
        ]

        # Related courses by instructor
        related_by_instructor = Course.objects.filter(
            instructor=course.instructor, is_published=True
        ).exclude(id=course.id)[:4]
        course_data["related_by_instructor"] = [
            {
                "id": c.id,
                "title": c.title,
                "subtitle": c.subtitle,
                "thumbnail": c.course_image.url if c.course_image else None
            } for c in related_by_instructor
        ]

        # Fetch feedbacks
        feedbacks = CourseFeedback.objects.filter(course=course)
        rating_distribution = dict.fromkeys([1, 2, 3, 4, 5], 0)

        if feedbacks.exists():
            total_feedback = feedbacks.count()
            avg_rating = round(feedbacks.aggregate(Avg("rating"))["rating__avg"], 1)

            # Count of each star
            count_by_star = feedbacks.values('rating').annotate(count=Count('rating'))
            for entry in count_by_star:
                rating_distribution[entry['rating']] = entry['count']

            rating_percent = {
                star: round((count / total_feedback) * 100, 1)
                for star, count in rating_distribution.items()
            }

            course_data["rating"] = avg_rating
            course_data["rating_breakdown"] = rating_percent
            course_data["feedback"] = [
                {
                    "name": fb.student.user.username,
                    "image": fb.student.profile_picture.url if fb.student.profile_picture else "",
                    "rating": fb.rating,
                    "comment": fb.feedback_text,
                    "submitted_at": localtime(fb.submitted_at).strftime("%Y-%m-%d %H:%M")
                }
                for fb in feedbacks.order_by("-submitted_at")[:5]
            ]
        else:
            course_data["rating"] = 0.0
            course_data["rating_breakdown"] = {}
            course_data["feedback"] = []


        return Response(course_data)
   

class EnrolledCoursesRawView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'student':
            return Response({"error": "Only students can view enrolled courses."}, status=403)

        student = get_object_or_404(Student, user=request.user)
        courses = student.enrolled_courses.filter(is_deleted=False, is_published=True)

        result = []
        for course in courses:
            progress = StudentProgress.objects.filter(student=student, course=course).first()
            completed_ids = set(progress.completed_contents.values_list('id', flat=True)) if progress else set()

            # Count completed contents in this course only
            total_lectures = LessonContent.objects.filter(concept__lesson__course=course).count()
            completed_count = LessonContent.objects.filter(
                id__in=completed_ids,
                concept__lesson__course=course
            ).count()

            lecture_completion = round((completed_count / total_lectures) * 100, 2) if total_lectures else 0

            # Check assignment pass
            total_assignments = Assignment.objects.filter(course=course).count()
            passed_assignments = AssignmentSubmission.objects.filter(
                student=student,
                assignment__course=course,
                pass_status='Pass'
            ).count()
            assignment_passed = total_assignments > 0 and passed_assignments == total_assignments

            overall_progress = 100 if lecture_completion == 100 and assignment_passed else lecture_completion

            result.append({
                "id": course.id,
                "title": course.title,
                "subtitle": course.subtitle,
                "image": course.course_image.url if course.course_image else None,
                "lecture": f"{total_lectures} Lectures",
                "progress": f"{overall_progress:.0f}% Completed",
                "instructor": course.instructor.user.username,
            })

        return Response(result, status=200)



from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import (
    Student, Course, Instructor, StudentProgress, LessonContent, QuizQuestion,
    Assignment, Quiz, Lesson
)
import datetime
from django.utils.dateparse import parse_duration
import random

def format_duration(seconds):
    minutes = seconds // 60
    remaining_seconds = seconds % 60
    return f"{minutes}:{remaining_seconds:02d}"

from django.utils.timezone import localtime

class CourseDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        user = request.user

        if user.role != 'student':
            return Response({"error": "Only students can view course details."}, status=403)

        student = get_object_or_404(Student, user=user)
        course = get_object_or_404(Course, id=course_id)
        instructor = course.instructor

        progress = StudentProgress.objects.filter(student=student, course=course).first()
        completed_ids = set(progress.completed_contents.values_list('id', flat=True)) if progress else set()

        # Calculate lecture completion
        total_lectures = LessonContent.objects.filter(concept__lesson__course=course).count()

        # ✅ Only count completed contents that belong to this course
        completed_count = LessonContent.objects.filter(
            id__in=completed_ids,
            concept__lesson__course=course
        ).count()

        lecture_completion = round((completed_count / total_lectures) * 100, 2) if total_lectures > 0 else 0


        # Check if final assignment passed
        total_assignments = Assignment.objects.filter(course=course).count()
        passed_assignments = AssignmentSubmission.objects.filter(
            student=student,
            assignment__course=course,
            pass_status='Pass'
        ).count()

        assignment_passed = total_assignments > 0 and passed_assignments == total_assignments


        overall_progress = 100 if lecture_completion == 100 and assignment_passed else lecture_completion

        # Initialize base response
        response = {
            "title": course.title,
            "subtitle": course.subtitle,
            "demoVideo": course.demo_video.url if course.demo_video else None,
            "instructor": {
                "name": instructor.user.username,
                "image": instructor.profile_picture.url if instructor.profile_picture else "",
                "role": instructor.headline,
                "biography": instructor.biography,
                "students": course.students.count(),
                "courses": Instructor.objects.filter(user=instructor.user).count(),
            },
            "rating": 0.0,
            "rating_breakdown": {},
            "feedback": [],
            "enrolled": course.students.count(),
            "duration": "N/A",
            "validTill": "Lifetime Access",
            "completedPercent": overall_progress,
            "lectureCompletion": lecture_completion,
            "assignmentPassed": assignment_passed,
            "showFinalExam": lecture_completion == 100,  # ✅ frontend can use this flag
            "sectionCount": course.lessons.count(),
            "lectureCount": total_lectures,
            "sections": [],
            "finalAssignment": [],
        }

        # Certificate
        if course.certificate_template:
            cert = course.certificate_template
            response["certificateTemplate"] = {
                "id": cert.id,
                "name": cert.name,
                "type": cert.type,
                "file_type": cert.file_type,
                "file": cert.file.url if cert.file else "",
                "html_template": cert.html_template if cert.file_type == 'html' else "",
                "preview_image": cert.preview_image.url if cert.preview_image else ""
            }
        else:
            response["certificateTemplate"] = None

        # Sections
        for lesson in course.lessons.all():
            section_duration = datetime.timedelta()
            lectures_data = []

            for concept in lesson.concepts.all():
                for content in concept.contents.all():
                    duration = content.duration or "00:00"
                    td = parse_duration(duration)
                    section_duration += td

                    lectures_data.append({
                        "title": concept.title,
                        "duration": duration,
                        "video": content.video.url if content.video else "",
                        "description": content.text_content,
                        "notes": {
                            "text": content.lecture_notes_text or "",
                            "download": content.lecture_notes_file.url if content.lecture_notes_file else "",
                        },
                        "attachFile": content.attached_file.url if content.attached_file else "",
                        "completed": content.id in completed_ids,
                        "content_id": content.id,
                    })

            total_lectures_in_section = len(lectures_data)
            completed_in_section = sum(1 for c in lectures_data if c["completed"])
            section_progress = int((completed_in_section / total_lectures_in_section) * 100) if total_lectures_in_section > 0 else 0

            # Practice quiz
            practice_paper = []
            if hasattr(lesson, 'quiz'):
                questions = list(lesson.quiz.questions.all())
                random.shuffle(questions)
                for q in questions:
                    options = q.options.copy()
                    if q.correct_answer not in options:
                        options.append(q.correct_answer)
                    random.shuffle(options)
                    final_options = options[:4] if q.correct_answer in options[:4] else (options[:3] + [q.correct_answer])
                    random.shuffle(final_options)
                    practice_paper.append({
                        "id": q.id,
                        "question": q.question_text,
                        "options": final_options
                    })

            response["sections"].append({
                "title": lesson.title,
                "total": format_duration(int(section_duration.total_seconds())),
                "finished": f"{section_progress}%",
                "lectureCount": total_lectures_in_section,
                "lectures": lectures_data,
                "practicePaper": practice_paper,
                "sectionProgress": section_progress,
                "completedLectures": completed_in_section,
                "id": lesson.id,
            })

        # Final assignment
        assignments = Assignment.objects.filter(course=course)
        for a in assignments:
            options = a.options.copy()
            if a.answer not in options:
                options.append(a.answer)
            random.shuffle(options)
            final_options = options[:4] if a.answer in options[:4] else (options[:3] + [a.answer])
            random.shuffle(final_options)

            response["finalAssignment"].append({
                "id": a.id,
                "question": a.question,
                "options": final_options
            })

        # Feedback
        feedbacks = CourseFeedback.objects.filter(course=course)
        rating_distribution = dict.fromkeys([1, 2, 3, 4, 5], 0)

        if feedbacks.exists():
            total_feedback = feedbacks.count()
            avg_rating = round(feedbacks.aggregate(Avg("rating"))["rating__avg"], 1)

            count_by_star = feedbacks.values('rating').annotate(count=Count('rating'))
            for entry in count_by_star:
                rating_distribution[entry['rating']] = entry['count']

            rating_percent = {
                star: round((count / total_feedback) * 100, 1)
                for star, count in rating_distribution.items()
            }

            response["rating"] = avg_rating
            response["rating_breakdown"] = rating_percent
            response["feedback"] = [
                {
                    "name": fb.student.user.username,
                    "image": fb.student.profile_picture.url if fb.student.profile_picture else "",
                    "rating": fb.rating,
                    "comment": fb.feedback_text,
                    "submitted_at": localtime(fb.submitted_at).strftime("%Y-%m-%d %H:%M")
                }
                for fb in feedbacks.order_by("-submitted_at")[:5]
            ]

        return Response(response, status=200)


    

class SubmitQuizView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        if user.role != 'student':
            return Response({"error": "Only students can submit quizzes."}, status=403)

        student = get_object_or_404(Student, user=user)
        data = request.data
        quiz_type = data.get("quiz_type")  # "practice" or "final"
        answers = data.get("answers", {})

        if quiz_type == "practice":
            lesson_id = data.get("lesson_id")
            lesson = get_object_or_404(Lesson, id=lesson_id)
            quiz = getattr(lesson, 'quiz', None)
            if not quiz:
                return Response({"error": "No quiz found for this lesson."}, status=404)
            questions = quiz.questions.all()

        elif quiz_type == "final":
            course_id = data.get("course_id")
            course = get_object_or_404(Course, id=course_id)
            questions = Assignment.objects.filter(course=course)

        else:
            return Response({"error": "Invalid quiz type."}, status=400)

        total = len(questions)
        correct = 0
        wrong_questions = []
        suggestions = []
        seen_content_ids = set()

        for question in questions:
            qid = str(question.id)
            submitted_answer = answers.get(qid, "").strip()  # Default to empty string

            # Handle practice questions
            if quiz_type == "practice":
                correct_answer = question.correct_answer.strip()
                question_text = question.question_text
                lesson_content = getattr(question, 'lesson_content', None)
                concept = getattr(lesson_content, 'concept', None) if lesson_content else None

            # Handle final assignments
            elif quiz_type == "final":
                correct_answer = question.answer.strip()
                question_text = question.question
                concept = None

            # Evaluate
            if submitted_answer.lower() == correct_answer.lower():
                correct += 1
            else:
                wrong_questions.append({
                    "question": question_text,
                    "your_answer": submitted_answer if submitted_answer else "(No Answer)",
                    "correct_answer": correct_answer,
                })

                if concept:
                    related_contents = LessonContent.objects.filter(concept=concept)
                    for content in related_contents:
                        if content.id in seen_content_ids:
                            continue
                        seen_content_ids.add(content.id)
                        suggestions.append({
                            "concept_title": concept.title,
                            "content_title": content.text_content[:100] if content.text_content else "(No text)",
                            "video_url": content.video.url if content.video else None,
                            "content_id": content.id,
                        })


        return Response({
            "total": total,
            "correct": correct,
            "wrong": total - correct,
            "wrong_details": wrong_questions,
            "suggestions": suggestions
        })


class EnrolledCourseSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'student':
            return Response({"error": "Only students can view course summary."}, status=403)

        student = get_object_or_404(Student, user=request.user)
        courses = student.enrolled_courses.filter(is_deleted=False, is_published=True)

        total = courses.count()
        active = 0
        completed = 0
        instructors = set()

        for course in courses:
            progress = StudentProgress.objects.filter(student=student, course=course).first()
            completed_ids = set(progress.completed_contents.values_list('id', flat=True)) if progress else set()

            total_lectures = LessonContent.objects.filter(concept__lesson__course=course).count()
            completed_count = LessonContent.objects.filter(
                id__in=completed_ids,
                concept__lesson__course=course
            ).count()
            lecture_completion = round((completed_count / total_lectures) * 100, 2) if total_lectures else 0

            total_assignments = Assignment.objects.filter(course=course).count()
            passed_assignments = AssignmentSubmission.objects.filter(
                student=student,
                assignment__course=course,
                pass_status='Pass'
            ).count()
            assignment_passed = total_assignments > 0 and passed_assignments == total_assignments

            overall_progress = 100 if lecture_completion == 100 and assignment_passed else lecture_completion

            if overall_progress == 100:
                completed += 1
            else:
                active += 1

            if course.instructor:
                instructors.add(course.instructor.user.id)

        return Response({
            "total_enrolled_courses": total,
            "active_courses": active,
            "completed_courses": completed,
            "unique_instructors": len(instructors)
        }, status=200)
        
from django.utils import timezone
from django.db.models import Count, Avg, Prefetch
from datetime import timedelta


class TopInstructorsThisMonthView(APIView):
    def get(self, request):
        # 1. Get courses added in the last 30 days
        past_30_days = timezone.now() - timedelta(days=30)
        recent_courses = Course.objects.filter(created_at__gte=past_30_days)

        # 2. Annotate with student count and average rating
        recent_courses = recent_courses.annotate(
            student_count=Count('students', distinct=True),
            avg_rating=Avg('feedbacks__rating')
        ).order_by('-student_count', '-avg_rating')

        # 3. Get unique instructor IDs from top courses
        instructor_ids = recent_courses.values_list('instructor_id', flat=True).distinct()

        # 4. Fetch instructors with all their courses (and feedbacks and students)
        instructors = Instructor.objects.filter(id__in=instructor_ids).prefetch_related(
            Prefetch(
                'course_set',
                queryset=Course.objects.prefetch_related('feedbacks', 'students')
            )
        )

        # 5. Compile data
        response_data = []
        for instructor in instructors:
            instructor_courses = instructor.course_set.all()


            # Gather all feedbacks across instructor's courses
            all_feedbacks = []
            all_students = set()
            for course in instructor_courses:
                all_feedbacks.extend(course.feedbacks.all())
                all_students.update(course.students.all())

            average_rating = (
                sum(f.rating for f in all_feedbacks) / len(all_feedbacks)
                if all_feedbacks else 0
            )

            instructor_data = InstructorSerializer(instructor).data

            response_data.append({
                "instructor": instructor_data,
                "average_rating": round(average_rating, 2),
                "total_students": len(all_students),
                "total_feedbacks": len(all_feedbacks),
            })

        return Response(response_data, status=status.HTTP_200_OK)


class EnrolledCourseInstructorsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'student':
            return Response({"error": "Only students can view instructors."}, status=403)

        student = get_object_or_404(Student, user=request.user)
        courses = student.enrolled_courses.filter(is_deleted=False, is_published=True)

        instructors_data = []
        seen = set()

        for course in courses:
            instructor = course.instructor
            if instructor.id in seen:
                continue
            seen.add(instructor.id)

            instructor_courses = Course.objects.filter(instructor=instructor, is_published=True, is_deleted=False)

            avg_rating = CourseFeedback.objects.filter(course__in=instructor_courses).aggregate(
                Avg('rating')
            )['rating__avg'] or 0.0

            total_students = Student.objects.filter(enrolled_courses__in=instructor_courses).distinct().count()

            instructors_data.append({  # fixed this line
                "id": instructor.user.id,
                "name": instructor.user.username,
                "email": instructor.user.email,
                "profile_picture": instructor.profile_picture.url if instructor.profile_picture else None,
                "headline": instructor.headline,
                "bio": instructor.biography,
                "average_rating": round(avg_rating, 2),
                "total_students": total_students,
                "course_id": course.id,  # <-- Add this line
                "course_title": course.title if course else None,
            })

        return Response(instructors_data, status=200)


class PrivateMessageStudentListWithLastMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        instructor = request.user

        if instructor.role != 'instructor':
            return Response({"error": "Only instructors can access this."}, status=403)

        student_ids = (
            PrivateMessage.objects
            .filter(receiver=instructor)
            .values_list('sender', flat=True)
            .distinct()
        )

        latest_messages = (
            PrivateMessage.objects
            .filter(receiver=instructor, sender__in=student_ids)
            .order_by('sender', '-timestamp')
        )

        seen = set()
        data = []

        for msg in latest_messages:
            sender_id = msg.sender.id
            if sender_id not in seen:
                seen.add(sender_id)
                student = Student.objects.filter(user=msg.sender).first()

                # ✅ Get count of unread messages from this student to instructor
                unread_count = PrivateMessage.objects.filter(
                    sender=msg.sender,
                    receiver=instructor,
                    is_read=False
                ).count()

                data.append({
                    "student_id": sender_id,
                    "username": msg.sender.username,
                    "profile_picture": (
                        student.profile_picture.url if student and student.profile_picture else None
                    ),
                    "last_message": msg.message,
                    "timestamp": msg.timestamp,
                    "course_id": msg.course.id if hasattr(msg, 'course') and msg.course else None,

                    # Additional fields
                    "receiver_username": msg.receiver.username,
                    "is_read": msg.is_read,
                    "reply_to": msg.reply_to.id if msg.reply_to else None,

                    # ✅ New field
                    "unread_count": unread_count
                })

        return Response(data, status=200)


class DraftCoursesListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        instructor = getattr(request.user, 'instructor', None)
        if not instructor:
            return Response({"error": "Only instructors can view drafts."}, status=403)

        # Get all draft courses
        drafts = Course.objects.filter(
            instructor=instructor,
            is_published=False
        ).exclude(creation_step='complete')

        serializer = CourseSerializer(drafts, many=True, context={'request': request})
        return Response(serializer.data)

class InstructorCourseDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        user = request.user
        course = get_object_or_404(Course, id=course_id)

        # Allow if user is the instructor who owns it or if the role is 'admin'
        if user.role not in ['instructor', 'admin']:
            return Response({"error": "Unauthorized access."}, status=403)

        if user.role == 'instructor' and course.instructor.user != user:
            return Response({"error": "You can only view your own courses."}, status=403)

        

       

        instructor = course.instructor

        # Count total lectures
        total_lectures = LessonContent.objects.filter(concept__lesson__course=course).count()

        response = {
            "title": course.title,
            "subtitle": course.subtitle,
            "demoVideo": course.demo_video.url if course.demo_video else None,
            "is_published": course.is_published,
            "creation_step": course.creation_step,
            "instructor": {
                "name": instructor.user.username,
                "image": instructor.profile_picture.url if instructor.profile_picture else "",
                "role": instructor.headline,
                "biography": instructor.biography,
                "students": course.students.count(),
                "courses": Instructor.objects.filter(user=instructor.user).count(),
            },
            "rating": 0.0,
            "rating_breakdown": {},
            "feedback": [],
            "enrolled": course.students.count(),
            "duration": "N/A",
            "validTill": "Lifetime Access",
            "completedPercent": None,  # Not applicable for instructor
            "lectureCompletion": None,
            "assignmentPassed": None,
            "showFinalExam": False,
            "sectionCount": course.lessons.count(),
            "lectureCount": total_lectures,
            "sections": [],
            "finalAssignment": [],
        }

        # Certificate
        if course.certificate_template:
            cert = course.certificate_template
            response["certificateTemplate"] = {
                "id": cert.id,
                "name": cert.name,
                "type": cert.type,
                "file_type": cert.file_type,
                "file": cert.file.url if cert.file else "",
                "html_template": cert.html_template if cert.file_type == 'html' else "",
                "preview_image": cert.preview_image.url if cert.preview_image else ""
            }
        else:
            response["certificateTemplate"] = None

        # Sections and lectures
        for lesson in course.lessons.all():
            section_duration = datetime.timedelta()
            lectures_data = []

            for concept in lesson.concepts.all():
                for content in concept.contents.all():
                    duration = content.duration or "00:00"
                    td = parse_duration(duration)
                    section_duration += td

                    lectures_data.append({
                        "title": concept.title,
                        "duration": duration,
                        "video": content.video.url if content.video else "",
                        "description": content.text_content,
                        "notes": {
                            "text": content.lecture_notes_text or "",
                            "download": content.lecture_notes_file.url if content.lecture_notes_file else "",
                        },
                        "attachFile": content.attached_file.url if content.attached_file else "",
                        "content_id": content.id,
                    })

            total_lectures_in_section = len(lectures_data)

            # Quiz (if exists)
            practice_paper = []
            if hasattr(lesson, 'quiz'):
                questions = list(lesson.quiz.questions.all())
                random.shuffle(questions)
                for q in questions:
                    options = q.options.copy()
                    if q.correct_answer not in options:
                        options.append(q.correct_answer)
                    random.shuffle(options)
                    final_options = options[:4] if q.correct_answer in options[:4] else (options[:3] + [q.correct_answer])
                    random.shuffle(final_options)
                    practice_paper.append({
                        "id": q.id,
                        "question": q.question_text,
                        "options": final_options
                    })

            response["sections"].append({
                "title": lesson.title,
                "total": format_duration(int(section_duration.total_seconds())),
                "lectureCount": total_lectures_in_section,
                "lectures": lectures_data,
                "practicePaper": practice_paper,
                "id": lesson.id,
            })

        # Final Assignment
        assignments = Assignment.objects.filter(course=course)
        for a in assignments:
            options = a.options.copy()
            if a.answer not in options:
                options.append(a.answer)
            random.shuffle(options)
            final_options = options[:4] if a.answer in options[:4] else (options[:3] + [a.answer])
            random.shuffle(final_options)

            response["finalAssignment"].append({
                "id": a.id,
                "question": a.question,
                "options": final_options
            })

        # Feedback
        feedbacks = CourseFeedback.objects.filter(course=course)
        rating_distribution = dict.fromkeys([1, 2, 3, 4, 5], 0)

        if feedbacks.exists():
            total_feedback = feedbacks.count()
            avg_rating = round(feedbacks.aggregate(Avg("rating"))["rating__avg"], 1)

            count_by_star = feedbacks.values('rating').annotate(count=Count('rating'))
            for entry in count_by_star:
                rating_distribution[entry['rating']] = entry['count']

            rating_percent = {
                star: round((count / total_feedback) * 100, 1)
                for star, count in rating_distribution.items()
            }

            response["rating"] = avg_rating
            response["rating_breakdown"] = rating_percent
            response["feedback"] = [
                {
                    "name": fb.student.user.username,
                    "image": fb.student.profile_picture.url if fb.student.profile_picture else "",
                    "rating": fb.rating,
                    "comment": fb.feedback_text,
                    "submitted_at": localtime(fb.submitted_at).strftime("%Y-%m-%d %H:%M")
                }
                for fb in feedbacks.order_by("-submitted_at")[:5]
            ]

        return Response(response, status=200)


class InstructorListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        instructors = CustomUser.objects.filter(role='instructor')  # Adjust if your model differs
        data = [
            {
                "id": instructor.id,
                "username": instructor.username,
                "email": instructor.email,
                "first_name": instructor.first_name,
                "last_name": instructor.last_name,
            }
            for instructor in instructors
        ]
        return Response(data, status=status.HTTP_200_OK)






class CourseApprovalUpdateView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, course_id):
        try:
            course = Course.objects.get(id=course_id)
            instructor_email = course.instructor.user.email
            instructor_name = course.instructor.user.username
            action = request.data.get("action")

            if action == "approve":
                course.is_approved = True
                course.save()

                # Send approval email
                send_mail(
                    subject="Your course has been approved",
                    message=f"Hi {instructor_name},\n\nCongratulations! Your course \"{course.title}\" has been approved and is now live.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[instructor_email],
                    fail_silently=False,
                )

                return Response({"message": "Course approved successfully."}, status=status.HTTP_200_OK)

            elif action == "disapprove":
                course.is_approved = False
                course.save()

                reason = request.data.get("reason", "No reason provided.")

                # Send disapproval email with reason
                send_mail(
                    subject="Your course has been disapproved",
                    message=f"Hi {instructor_name},\n\nUnfortunately, your course \"{course.title}\" has been disapproved.\n\nReason: {reason}\n\nPlease make the necessary changes and resubmit for review.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[instructor_email],
                    fail_silently=False,
                )

                return Response({"message": "Course disapproved and instructor notified."}, status=status.HTTP_200_OK)

            elif action == "update":
                course.title = request.data.get("title", course.title)
                course.description = request.data.get("description", course.description)
                course.save()

                return Response({"message": "Course updated successfully."}, status=status.HTTP_200_OK)

            else:
                return Response({"error": "Invalid action"}, status=status.HTTP_400_BAD_REQUEST)

        except Course.DoesNotExist:
            return Response({"error": "Course not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PendingCourseListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        courses = Course.objects.filter(is_published=True, is_approved=False)
        data = [
            {
                "id": course.id,
                "title": course.title,
                "description": course.description,
                "instructor": course.instructor.user.username,
                "created_at": course.created_at,
            }
            for course in courses
        ]
        return Response(data, status=status.HTTP_200_OK)


from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils.timezone import localtime
from django.db.models import Avg, Count
import datetime, random
from  api.utils.time_utils import parse_duration, format_duration  # Assuming you have these utilities

class AdminCourseDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        user = request.user

        # Only admins can access this view
        if user.role != 'admin':
            return Response({"error": "Access denied. Admins only."}, status=403)

        course = get_object_or_404(Course, id=course_id)
        instructor = course.instructor
        total_lectures = LessonContent.objects.filter(concept__lesson__course=course).count()

        response = {
            "title": course.title,
            "subtitle": course.subtitle,
            "demoVideo": course.demo_video.url if course.demo_video else None,
            "is_published": course.is_published,
            "creation_step": course.creation_step,
            "instructor": {
                "name": instructor.user.username,
                "image": instructor.profile_picture.url if instructor.profile_picture else "",
                "role": instructor.headline,
                "biography": instructor.biography,
                "students": course.students.count(),
                "courses": Instructor.objects.filter(user=instructor.user).count(),
            },
            "rating": 0.0,
            "rating_breakdown": {},
            "feedback": [],
            "enrolled": course.students.count(),
            "duration": "N/A",
            "validTill": "Lifetime Access",
            "completedPercent": None,
            "lectureCompletion": None,
            "assignmentPassed": None,
            "showFinalExam": False,
            "sectionCount": course.lessons.count(),
            "lectureCount": total_lectures,
            "sections": [],
            "finalAssignment": [],
        }

        # Certificate
        if course.certificate_template:
            cert = course.certificate_template
            response["certificateTemplate"] = {
                "id": cert.id,
                "name": cert.name,
                "type": cert.type,
                "file_type": cert.file_type,
                "file": cert.file.url if cert.file else "",
                "html_template": cert.html_template if cert.file_type == 'html' else "",
                "preview_image": cert.preview_image.url if cert.preview_image else ""
            }
        else:
            response["certificateTemplate"] = None

        # Sections and lectures
        for lesson in course.lessons.all():
            section_duration = datetime.timedelta()
            lectures_data = []

            for concept in lesson.concepts.all():
                for content in concept.contents.all():
                    duration = content.duration or "00:00"
                    td = parse_duration(duration)
                    section_duration += td

                    # ✅ Fetch content-level quiz questions (if any)
                    content_quizzes = []
                    if hasattr(content, 'quiz'):
                        for q in content.quiz.questions.all():
                            options = q.options.copy()
                            if q.correct_answer not in options:
                                options.append(q.correct_answer)
                            random.shuffle(options)
                            final_options = options[:4] if q.correct_answer in options[:4] else (options[:3] + [q.correct_answer])
                            random.shuffle(final_options)
                            content_quizzes.append({
                                "id": q.id,
                                "question": q.question_text,
                                "options": final_options
                            })

                    lectures_data.append({
                        "title": concept.title,
                        "duration": duration,
                        "video": content.video.url if content.video else "",
                        "description": content.text_content,
                        "notes": {
                            "text": content.lecture_notes_text or "",
                            "download": content.lecture_notes_file.url if content.lecture_notes_file else "",
                        },
                        "attachFile": content.attached_file.url if content.attached_file else "",
                        "content_id": content.id,
                        "quiz": content_quizzes  # ✅ Included here
                    })

            # Section-level quiz
            practice_paper = []
            if hasattr(lesson, 'quiz'):
                for q in lesson.quiz.questions.all():
                    options = q.options.copy()
                    if q.correct_answer not in options:
                        options.append(q.correct_answer)
                    random.shuffle(options)
                    final_options = options[:4] if q.correct_answer in options[:4] else (options[:3] + [q.correct_answer])
                    random.shuffle(final_options)
                    practice_paper.append({
                        "id": q.id,
                        "question": q.question_text,
                        "options": final_options
                    })

            response["sections"].append({
                "title": lesson.title,
                "total": format_duration(int(section_duration.total_seconds())),
                "lectureCount": len(lectures_data),
                "lectures": lectures_data,
                "practicePaper": practice_paper,
                "id": lesson.id,
            })

        # Final Assignments
        assignments = Assignment.objects.filter(course=course)
        for a in assignments:
            options = a.options.copy()
            if a.answer not in options:
                options.append(a.answer)
            random.shuffle(options)
            final_options = options[:4] if a.answer in options[:4] else (options[:3] + [a.answer])
            random.shuffle(final_options)

            response["finalAssignment"].append({
                "id": a.id,
                "question": a.question,
                "options": final_options
            })

        # Feedback
        feedbacks = CourseFeedback.objects.filter(course=course)
        rating_distribution = dict.fromkeys([1, 2, 3, 4, 5], 0)

        if feedbacks.exists():
            total_feedback = feedbacks.count()
            avg_rating = round(feedbacks.aggregate(Avg("rating"))["rating__avg"], 1)

            count_by_star = feedbacks.values('rating').annotate(count=Count('rating'))
            for entry in count_by_star:
                rating_distribution[entry['rating']] = entry['count']

            rating_percent = {
                star: round((count / total_feedback) * 100, 1)
                for star, count in rating_distribution.items()
            }

            response["rating"] = avg_rating
            response["rating_breakdown"] = rating_percent
            response["feedback"] = [
                {
                    "name": fb.student.user.username,
                    "image": fb.student.profile_picture.url if fb.student.profile_picture else "",
                    "rating": fb.rating,
                    "comment": fb.feedback_text,
                    "submitted_at": localtime(fb.submitted_at).strftime("%Y-%m-%d %H:%M")
                }
                for fb in feedbacks.order_by("-submitted_at")[:5]
            ]

        return Response(response, status=200)


class UnreadNotificationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        unread_messages = PrivateMessage.objects.filter(receiver=user, is_read=False).order_by('-timestamp')

        data = []

        for msg in unread_messages:
            sender = msg.sender

            # Try getting profile picture from Instructor, Student, or default
            profile_url = None
            if hasattr(sender, 'instructor') and sender.instructor.profile_picture:
                profile_url = sender.instructor.profile_picture.url
            elif hasattr(sender, 'student') and sender.student.profile_picture:
                profile_url = sender.student.profile_picture.url

            data.append({
                "id": msg.id,
                "sender_id": sender.id,
                "sender": sender.username,
                "profile_picture": profile_url,
                "message": msg.message,
                "timestamp": msg.timestamp,
            })

        return Response(data)


import razorpay
from razorpay import Utility
class CreateRazorpayOrder(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, course_id):
        student = get_object_or_404(Student, user=request.user)
        course = get_object_or_404(Course, id=course_id)

        if CoursePayment.objects.filter(student=student, course=course, is_paid=True).exists():
            return Response({"message": "Already enrolled!"})

        # ✅ Calculate discounted amount
        discount = course.discount or 0
        discounted_price = course.price * (1 - (discount / 100))
        final_amount = round(discounted_price, 2)

        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        try:
            order = client.order.create(dict(
                amount=int(final_amount * 100),
                currency="INR",
                payment_capture='1'
            ))
        except razorpay.errors.BadRequestError as e:
            return Response({"error": "Razorpay order creation failed.", "details": str(e)}, status=400)


        CoursePayment.objects.create(
            student=student,
            course=course,
            original_price=course.price,
            discount_percent=discount,
            amount_paid=final_amount,
            razorpay_order_id=order['id']
        )


        return Response({
            "order_id": order['id'],    
            "amount": int(final_amount * 100),
            "currency": "INR",
            "key": settings.RAZORPAY_KEY_ID,
            "final_price": final_amount
        })

class VerifyRazorpayPayment(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        student = get_object_or_404(Student, user=request.user)
        order_id = request.data.get('razorpay_order_id')
        payment_id = request.data.get('razorpay_payment_id')
        signature = request.data.get('razorpay_signature')

        print("Looking for order_id:", order_id)
        print("Looking for student ID:", student.id)

        # Optional: Debug if payment exists
        print("Payments with order_id:", CoursePayment.objects.filter(razorpay_order_id=order_id))
        print("Payments for student:", CoursePayment.objects.filter(student=student))

        # Verify Razorpay Signature
        try:
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            params_dict = {
                'razorpay_order_id': order_id,
                'razorpay_payment_id': payment_id,
                'razorpay_signature': signature
            }
            client.utility.verify_payment_signature(params_dict)
        except Exception as e:
            print("Signature verification failed:", e)
            payment = get_object_or_404(CoursePayment, razorpay_order_id=order_id, student=student)
            payment.payment_status = "failed"
            payment.save()
            return Response({'error': 'Invalid signature'}, status=400)

        # Update Payment Record
        payment = get_object_or_404(CoursePayment, razorpay_order_id=order_id, student=student)
        payment.razorpay_payment_id = payment_id
        payment.razorpay_signature = signature
        payment.is_paid = True
        payment.payment_status = "success"
        payment.save()

        # Enroll student in course
        payment.course.students.add(student)

        return Response({'message': 'Payment successful. Course access granted!'})


class AddToCartView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, course_id):
        student = get_object_or_404(Student, user=request.user)
        course = get_object_or_404(Course, id=course_id)

        # Prevent duplicate
        if CartItem.objects.filter(student=student, course=course).exists():
            return Response({'message': 'Course already in cart'}, status=200)

        CartItem.objects.create(student=student, course=course)
        return Response({'message': 'Course added to cart'}, status=201)


class RemoveFromCartView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, course_id):
        student = get_object_or_404(Student, user=request.user)
        course = get_object_or_404(Course, id=course_id)

        cart_item = CartItem.objects.filter(student=student, course=course).first()
        if cart_item:
            cart_item.delete()
            return Response({'message': 'Course removed from cart'}, status=200)

        return Response({'error': 'Course not found in cart'}, status=404)


class ListCartItemsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        student = get_object_or_404(Student, user=request.user)
        items = CartItem.objects.filter(student=student)
        serializer = CartItemSerializer(items, many=True)
        return Response(serializer.data)
    


class CreateBulkRazorpayOrder(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        student = get_object_or_404(Student, user=request.user)
        cart_items = CartItem.objects.filter(student=student)

        if not cart_items.exists():
            return Response({"error": "Your cart is empty!"}, status=400)

        total_amount = 0
        course_payments = []

        for item in cart_items:
            course = item.course
            if CoursePayment.objects.filter(student=student, course=course, is_paid=True).exists():
                continue  # Skip already paid/enrolled courses

            discount = course.discount or 0
            discounted_price = course.price * (1 - (discount / 100))
            total_amount += round(discounted_price, 2)

            course_payments.append({
                "course": course,
                "original_price": course.price,
                "discount": discount,
                "amount_paid": round(discounted_price, 2)
            })

        if total_amount == 0:
            return Response({"message": "All cart items are already enrolled."})

        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

        try:
            razorpay_order = client.order.create({
                "amount": int(total_amount * 100),
                "currency": "INR",
                "payment_capture": 1
            })
        except Exception as e:
            return Response({"error": "Razorpay order creation failed", "details": str(e)}, status=400)

        # Save payment records for all pending cart items
        for payment in course_payments:
            CoursePayment.objects.create(
                student=student,
                course=payment['course'],
                original_price=payment['original_price'],
                discount_percent=payment['discount'],
                amount_paid=payment['amount_paid'],
                razorpay_order_id=razorpay_order['id']
            )

        return Response({
            "order_id": razorpay_order['id'],
            "amount": int(total_amount * 100),
            "currency": "INR",
            "key": settings.RAZORPAY_KEY_ID,
            "final_price": total_amount
        })
    
class VerifyBulkRazorpayPayment(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        student = get_object_or_404(Student, user=request.user)
        order_id = request.data.get('razorpay_order_id')
        payment_id = request.data.get('razorpay_payment_id')
        signature = request.data.get('razorpay_signature')

        print("🔎 Looking for order_id:", order_id)
        print("🔎 Looking for student ID:", student.id)

        # ✅ Verify Razorpay Signature
        try:
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            params_dict = {
                'razorpay_order_id': order_id,
                'razorpay_payment_id': payment_id,
                'razorpay_signature': signature
            }
            client.utility.verify_payment_signature(params_dict)
        except Exception as e:
            print("❌ Signature verification failed:", e)
            CoursePayment.objects.filter(razorpay_order_id=order_id, student=student).update(payment_status="failed")
            return Response({'error': 'Invalid signature'}, status=400)

        # ✅ Mark all matching payments as successful
        payments = CoursePayment.objects.filter(razorpay_order_id=order_id, student=student)

        if not payments.exists():
            return Response({'error': 'No matching payment records found.'}, status=404)

        for payment in payments:
            payment.razorpay_payment_id = payment_id
            payment.razorpay_signature = signature
            payment.is_paid = True
            payment.payment_status = "success"
            payment.save()

            # ✅ Enroll student in the course
            payment.course.students.add(student)

        return Response({'message': 'Bulk payment verified. Courses access granted!'})

from collections import defaultdict

class StudentPaymentHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        student = get_object_or_404(Student, user=request.user)
        payments = CoursePayment.objects.filter(student=student, is_paid=True).order_by('-created_at')

        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

        grouped_history = defaultdict(lambda: {
            "courses": [],
            "payment": None,
        })

        for payment in payments:
            if not payment.razorpay_payment_id:
                continue  # skip if not completed

            try:
                razorpay_info = client.payment.fetch(payment.razorpay_payment_id)
                card = razorpay_info.get("card", {})
                order_id = payment.razorpay_order_id

                # Append course info
                grouped_history[order_id]["courses"].append({
                    "title": payment.course.title,
                    "image": payment.course.course_image.url if payment.course.course_image else None,
                    "instructor": payment.course.instructor.user.username,
                    "price": float(payment.original_price),
                    "discount": float(payment.discount_percent),
                    "paid_amount": float(payment.amount_paid),
                })

                # Add shared payment info once
                if not grouped_history[order_id]["payment"]:
                    grouped_history[order_id]["payment"] = {
                        "order_id": order_id,
                        "payment_id": payment.razorpay_payment_id,
                        "method": razorpay_info.get("method"),
                        "status": payment.payment_status,
                        "timestamp": payment.created_at.isoformat(),
                        "email": razorpay_info.get("email"),
                        "contact": razorpay_info.get("contact"),
                        "card": {
                            "last4": card.get("last4"),
                            "network": card.get("network"),
                            "type": card.get("type"),
                            "issuer": card.get("issuer"),
                        }
                    }

            except Exception as e:
                print(f"⚠️ Failed to fetch Razorpay info for {payment.razorpay_payment_id}: {e}")
                continue

        return Response(list(grouped_history.values()))