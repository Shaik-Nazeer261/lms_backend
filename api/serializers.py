from rest_framework import serializers
from .models import *
from django.core.mail import send_mail
from django.conf import settings
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
import random
import string
from django.db import transaction
import json
from django.shortcuts import get_object_or_404
from django.db.models import Avg


from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user

        # Determine if user is a student or instructor and get profile picture accordingly
        profile_image = None
        if hasattr(user, 'student') and user.student.profile_picture:
            profile_image = user.student.profile_picture.url
        elif hasattr(user, 'instructor') and user.instructor.profile_picture:
            profile_image = user.instructor.profile_picture.url

        data['user'] = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': user.role,
            'profile_image': profile_image
        }

        return data


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model =CustomUser
        fields = ['username','email','first_name','last_name']

    def create(self,validated_data):

        temp_password =''.join(random.choices(string.ascii_letters +string.digits,k=8))

        user=CustomUser.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            first_name=validated_data.get('first_name',''),
            last_name=validated_data.get('last_name',''),
            password=temp_password,
            role='instructor',
            is_active=False
            )
        

        
        token =default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))


        verify_url = f"{settings.BACKEND_URL}/api/verify-teacher/{uid}/{token}/"


        send_mail(
            subject='LMS Teacher Verification',
            message=f'Hi {user.first_name},\n\nYoy have been added as a teacher .\nYour temporary password is:{temp_password}\n\nPlease verify your account using this link:\n{verify_url}\n\n After verification ,you can set a new password.',
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[user.email],
            fail_silently=False,

        )
        return user
    

class InstructorSerializer(serializers.ModelSerializer):
    user = UserSerializer()  # nested serializer

    class Meta:
        model = Instructor
        fields = [
            "id",
            "user_id",
            "user",
            "headline",
            "biography",
            "language",
            "profile_picture",
            "phone_number",
            "personal_website",
            "facebook_url",
            "instagram_url",
            "linkedin_url",
            "twitter_url",
            "whatsapp_number",
            "youtube_url",
        ]


class StudentSerializer(serializers.ModelSerializer):
    user= UserSerializer()  # nested serializer
    class Meta:
        model = Student
        fields = [
            "id",
            'user_id',
            "user",
            "headline",
            "biography",
            "website",
            "social_links",
            "language",
            "profile_picture",
        ]

        
class StudentRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    class Meta:
        model = CustomUser
        fields = ['username','email','first_name','last_name','password']
    
    def validate_username(self,value):
        if CustomUser.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already exists")
        return value
    
    def validate_email(self,value):
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists")
        return value
    

    def create(self,validated_data):
        user = CustomUser.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            first_name=validated_data.get('first_name',''),
            last_name=validated_data.get('last_name',''),
            password=validated_data['password'],
            role='student',
            is_active=True
        )
       
        if user.role == 'student':
            Student.objects.create(user=user)
        return user


class CertificateTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CertificateTemplate
        fields = [
            'id', 'name', 'type', 'file_type',
            'html_template', 'file', 'preview_image',
            'instructor', 'created_at'
        ]
        read_only_fields = ['instructor', 'created_at']

    def validate(self, data):
        template_type = data.get("type")
        file_type = data.get("file_type")

        # Remove strict binding between type and file_type
        if file_type in ["html", "plain"] and not data.get("html_template"):
            raise serializers.ValidationError("HTML/Plain templates must include `html_template`.")
        if file_type in ["pdf", "docx"] and not data.get("file"):
            raise serializers.ValidationError("DOCX/PDF templates must include an uploaded file.")
        
        return data

    def create(self, validated_data):
        request = self.context.get('request')
        if request and hasattr(request.user, 'instructor'):
            validated_data['instructor'] = request.user.instructor
        return super().create(validated_data)
    
class CategorySerializer(serializers.ModelSerializer):
    course_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'course_count']

    def get_course_count(self, obj):
        return obj.courses.count()


class SubCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SubCategory
        fields = ['id', 'name', 'category']

class CategoryWithSubSerializer(serializers.ModelSerializer):
    subcategories = SubCategorySerializer(many=True, read_only=True)

    class Meta:
        model = Category
        fields = ['id', 'name', 'subcategories']


class CourseSerializer(serializers.ModelSerializer):
    instructor_name = serializers.CharField(source="instructor.user.username", read_only=True)
    creation_progress = serializers.SerializerMethodField()
    certificate_template = CertificateTemplateSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    subcategory = SubCategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(source="category", queryset=Category.objects.all(), write_only=True)
    subcategory_id = serializers.PrimaryKeyRelatedField(source="subcategory", queryset=SubCategory.objects.all(), write_only=True)
    enrolled_students_count = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    course_image = serializers.SerializerMethodField()
    enrolled_student_ids = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id',
            'title',
            'category',
            'subcategory',
            'category_id',
            'subcategory_id',
            'instructor',
            'instructor_name',
            'description',
            'requirements',
            'learning_objectives',
            'course_image',
            'is_deleted',
            'certificate_template',
            # 'is_paid',
            'price',
            'creation_progress',
            'demo_video',
            'course_level',
            'language', 
            'time_duration',
            # 'course_expiration',
            'created_at',
            'enrolled_students_count',
            'average_rating',
            'is_published',
            'creation_step',
            'enrolled_student_ids',  # ← add here
        ]
        extra_kwargs = {
            "instructor": {"required": False},
            "title": {"required": False},
            "category": {"required": False},
            "description": {"required": False},
            "requirements": {"required": False},
            "learning_objectives": {"required": False},
            "course_image": {"required": False},
        }

    def get_creation_progress(self, obj):
        required_fields = [
            obj.title,
            obj.category,
            obj.subcategory,
            obj.description,
            obj.requirements,
            obj.learning_objectives,
            obj.price,
            obj.course_level,
            obj.language,
            obj.time_duration,
            obj.demo_video,
            obj.certificate_template,
            obj.course_image
        ]

        total_fields = len(required_fields)
        filled_fields = sum(bool(field) for field in required_fields)
        progress = int((filled_fields / total_fields) * 100)

        # Cap progress at 99% if the course is not published
        if progress == 100 and not obj.is_published:
            progress = 99

        return progress


    def create(self, validated_data):
        instructor = Instructor.objects.get(user=self.context['request'].user)
        course = Course(**validated_data)
        course.instructor = instructor
        course.save()
        return course

    def get_enrolled_students_count(self, obj):
        return obj.students.count()

    def get_average_rating(self, obj):
        return round(obj.feedbacks.aggregate(Avg('rating'))['rating__avg'] or 0, 2)
    
    def get_course_image(self, obj):
        request = self.context.get("request")
        if obj.course_image:
            original_url = obj.course_image.url
            modified_url = f"/api{original_url}"  # prepend /api
            return request.build_absolute_uri(modified_url)
        return None

    def validate(self, data):
        category = data.get("category")
        subcategory = data.get("subcategory")

        if subcategory and category and subcategory.category_id != category.id:
            raise serializers.ValidationError({
                "subcategory_id": "Selected subcategory does not belong to the given category."
            })
        return data
    
    def get_enrolled_student_ids(self, obj):
        return list(obj.students.values_list('user_id', flat=True))


    


class VideoQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = VideoQuestion
        fields = ['id', 'timestamp', 'question_text', 'correct_answer']

class QuizQuestionSerializer(serializers.ModelSerializer):
    options = serializers.SerializerMethodField()
    lesson_content_id = serializers.IntegerField(write_only=True, required=False)
    quiz_id = serializers.IntegerField(source="quiz.id", read_only=True)
    content_reference = serializers.SerializerMethodField()
    correct_answer = serializers.CharField()  # Expose correct answer

    class Meta:
        model = QuizQuestion
        fields = ['id', 'question_text', 'correct_answer', 'options', 'lesson_content_id', 'quiz_id', 'content_reference']

    def get_options(self, obj):
        import random
        # Filter out any blank or null values
        options = [opt for opt in obj.options if opt] if isinstance(obj.options, list) else []

        # Ensure the correct answer is included
        if obj.correct_answer and obj.correct_answer not in options:
            options.append(obj.correct_answer)

        # Limit to 4 options max, including the correct answer
        if len(options) > 4:
            if obj.correct_answer in options:
                options.remove(obj.correct_answer)
            options = random.sample(options, 3)
            options.append(obj.correct_answer)

        random.shuffle(options)
        return options

    def get_content_reference(self, obj):
        if obj.lesson_content:
            concept = getattr(obj.lesson_content, 'concept', None)
            return {
                "content_id": obj.lesson_content.id,
                "text_content": getattr(obj.lesson_content, 'text_content', ''),
                "concept_title": getattr(concept, 'title', '') if concept else '',
            }
        return None

    def create(self, validated_data):
        options = validated_data.pop("options", [])
        content_id = validated_data.pop("lesson_content_id", None)
        lesson_content = None
        if content_id:
            lesson_content = get_object_or_404(LessonContent, id=content_id)

        quiz = validated_data.get("quiz") or self.context.get("quiz")

        question = QuizQuestion.objects.create(
            quiz=quiz,
            lesson_content=lesson_content,
            options=options,
            **validated_data
        )
        return question



class LessonContentSerializer(serializers.ModelSerializer):
    video_questions = VideoQuestionSerializer(many=True, required=False)
    quiz_questions = QuizQuestionSerializer(many=True, required=False)  #  NEW

    class Meta:
        model = LessonContent
        fields = ['id', 'video', 'pdf', 'text_content', 'order', 'created_at', 'video_questions', 'quiz_questions']
        extra_kwargs = {
            'video': {'required': False},
            'pdf': {'required': False},
            'text_content': {'required': False},
            'order': {'required': False},
        }

    def validate(self, data):
        if not any(data.get(field) for field in ['video', 'pdf', 'text_content']):
            raise serializers.ValidationError("At least one content type must be provided.")
        return data




    def create(self, validated_data):
        video_questions_data = self.initial_data.get("video_questions", [])
        quiz_questions_data = self.initial_data.get("quiz_questions", [])

        # Parse JSON strings if needed
        for key, source in [('video_questions', video_questions_data), ('quiz_questions', quiz_questions_data)]:
            if isinstance(source, str):
                try:
                    parsed = json.loads(source)
                    if key == 'video_questions':
                        video_questions_data = parsed
                    else:
                        quiz_questions_data = parsed
                except json.JSONDecodeError:
                    raise serializers.ValidationError(f"Invalid JSON format for {key}.")

        # Determine content type
        content_type = None
        if validated_data.get('video'):
            content_type = 'video'
        elif validated_data.get('pdf'):
            content_type = 'pdf'
        elif validated_data.get('text_content'):
            content_type = 'text'

        try:
            with transaction.atomic():
                # ✅ Create LessonContent
                content = LessonContent.objects.create(content_type=content_type, **validated_data)

                # ✅ Create Video Questions
                for q in video_questions_data:
                    if isinstance(q, dict):
                        VideoQuestion.objects.create(content=content, **q)

                # ✅ Get related lesson and quiz
                concept = validated_data['concept']
                lesson = concept.lesson

                # Auto-create quiz if not exists
               # Get instructor from context (passed via view)
                instructor = self.context.get('request').user


                # Auto-create quiz if not exists
                quiz = getattr(lesson, 'quiz', None)
                if not quiz:
                    quiz = Quiz.objects.create(
                        lesson=lesson,
                        title=f"{lesson.title} Quiz",
                        instructor=instructor  # ✅ FIX: Add this line
                    )
                    lesson.quiz = quiz
                    lesson.save()

                # ✅ Create Quiz Questions (linked to lesson's quiz)
                for q in quiz_questions_data:
                    if isinstance(q, dict):
                        QuizQuestion.objects.create(
                            quiz=quiz,
                            lesson_content=content,
                            question_text=q.get('question_text'),
                            correct_answer=q.get('correct_answer'),
                            options=q.get('options', [])  # ✅ Store options directly
                        )



                return content

        except Exception as e:
            print("🔥 ERROR in content creation:", str(e))
            raise serializers.ValidationError({"error": str(e)})


    
    def update(self, instance, validated_data):
        video_questions_data = self.initial_data.get("video_questions", [])
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Infer and update content_type again
        if validated_data.get('video'):
            instance.content_type = 'video'
        elif validated_data.get('pdf'):
            instance.content_type = 'pdf'
        elif validated_data.get('text_content'):
            instance.content_type = 'text'

        instance.save()

        if video_questions_data:
            instance.video_questions.all().delete()
            for q in video_questions_data:
                VideoQuestion.objects.create(content=instance, **q)

        return instance

class LessonContentUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LessonContent
        fields = ['video', 'pdf', 'text_content', 'order']
        extra_kwargs = {
            'video': {'required': False},
            'pdf': {'required': False},
            'text_content': {'required': False},
            'order': {'required': False},
        }

    def validate(self, data):
        content_fields = ['video', 'pdf', 'text_content']
        if not any([
            data.get('video'),
            data.get('pdf'),
            data.get('text_content'),
            self.instance and (self.instance.video or self.instance.pdf or self.instance.text_content)
        ]):
            raise serializers.ValidationError("At least one content type must be provided.")
        return data

    def update(self, instance, validated_data):
        if validated_data.get('video'):
            instance.content_type = 'video'
        elif validated_data.get('pdf'):
            instance.content_type = 'pdf'
        elif validated_data.get('text_content'):
            instance.content_type = 'text'

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance



class ConceptSerializer(serializers.ModelSerializer):
    contents = LessonContentSerializer(many=True, read_only=True)

    class Meta:
        model = Concept
        fields = ['id', 'lesson', 'title', 'description', 'order', 'contents']
        extra_kwargs = {
            'lesson': {'read_only': True},
        }

class LessonSerializer(serializers.ModelSerializer):
    concepts = ConceptSerializer(many=True, read_only=True)
    quiz = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = ['id', 'course', 'title', 'concepts', 'quiz', 'created_at']
        extra_kwargs = {
        'course': {'read_only': True},
        }


    def get_quiz(self, lesson):
        all_questions = []
        contents = LessonContent.objects.filter(concept__lesson=lesson)

        for content in contents:
            for question in content.quiz_questions.all():
                question_data = QuizQuestionSerializer(question, context=self.context).data
                all_questions.append(question_data)

        return {
            "quiz_id": lesson.quiz.id if hasattr(lesson, 'quiz') else None,
            "title": f"Auto-Quiz from Content: {lesson.title}",
            "questions": all_questions
        } if all_questions else None
    

class AssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Assignment
        fields = ['id', 'question', 'answer', 'options']


class AssignmentCreateSerializer(serializers.Serializer):
    course = serializers.PrimaryKeyRelatedField(queryset=Course.objects.all())
    assignments = serializers.ListField(
        child=serializers.DictField()
    )

    def validate(self, data):
        for item in data['assignments']:
            if not item.get('question') or not item.get('answer'):
                raise serializers.ValidationError("Each assignment must have a 'question' and an 'answer'.")
            if 'options' in item:
                options = item['options']
                if not isinstance(options, list) or not all(isinstance(opt, str) for opt in options):
                    raise serializers.ValidationError("Options must be a list of strings.")
                # if item['answer'] not in options:
                #     raise serializers.ValidationError("Answer must be one of the options.")
        return data
    

class AssignmentResultSerializer(serializers.ModelSerializer):
    assignment_question = serializers.CharField(source="assignment.question", read_only=True)

    class Meta:
        model = AssignmentSubmission
        fields = ['id', 'assignment', 'assignment_question', 'submitted_answer', 'is_correct', 'score', 'pass_status', 'submitted_at']


class LiveClassSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source="course.title", read_only=True)  #  Add this line
    class Meta:
        model = LiveClass
        fields = ["id", "title", "description", "scheduled_time", "meeting_link", "course", "status","course_title"]
        read_only_fields = ["status"]  #  Instructor cannot directly set it to approved

class CourseChatMessageSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source="sender.username", read_only=True)
    sender_id = serializers.IntegerField(source="sender.id", read_only=True)
    isMine = serializers.SerializerMethodField()
    reply_to_message = serializers.SerializerMethodField()
    attachment_url = serializers.SerializerMethodField()

    class Meta:
        model = CourseChatMessage
        fields = [
            'id',
            'message',
            'sender_username',
            'sender_id',
            'timestamp',
            'isMine',
            'reply_to',
            'reply_to_message',
            'is_edited',
            'is_deleted',
            'attachment_url'
        ]
            

    def get_isMine(self, obj):
        request = self.context.get('request')
        if request and hasattr(request, "user"):
            return request.user == obj.sender
        return False

    def get_reply_to_message(self, obj):
        if obj.reply_to and not obj.reply_to.is_deleted:
            return {
                "id": obj.reply_to.id,
                "sender_username": obj.reply_to.sender.username,
                "message": obj.reply_to.message[:100]  # show first 100 chars as preview
            }
        return None
    def get_attachment_url(self, obj):
        request = self.context.get('request')
        if obj.attachment:
            return request.build_absolute_uri(obj.attachment.url)
        return None
    
class PrivateMessageSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source="sender.username", read_only=True)
    receiver_username = serializers.CharField(source="receiver.username", read_only=True)
    reply_to_message = serializers.SerializerMethodField()
    is_read = serializers.BooleanField(read_only=True)

    class Meta:
        model = PrivateMessage
        fields = [
            'id',
            'sender_username',
            'receiver_username',
            'message',
            'attachment',
            'timestamp',
            'reply_to',           # include this if you need to send reply ID from frontend
            'reply_to_message',    # this is what frontend displays
            'is_read'  # ← Include in response
        ]

    def get_reply_to_message(self, obj):
        if obj.reply_to:
            return {
                'id': obj.reply_to.id,
                'sender_username': obj.reply_to.sender.username,
                'message': obj.reply_to.message
            }
        return None
    

class StudentProgressSerializer(serializers.ModelSerializer):
    student = serializers.PrimaryKeyRelatedField(read_only=True)
    course = serializers.PrimaryKeyRelatedField(read_only=True)
    completed_contents = serializers.PrimaryKeyRelatedField(many=True, read_only=True)

    class Meta:
        model = StudentProgress
        fields = ['student', 'course', 'completed_contents', 'progress_percentage']


class StudentNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentNote
        fields = ['id', 'student', 'concept', 'note', 'updated_at']
        read_only_fields = ['student', 'updated_at']

class CourseFeedbackSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.user.username', read_only=True)
    student_image = serializers.SerializerMethodField()  # ✅ Add this line

    class Meta:
        model = CourseFeedback
        fields = ['id', 'student', 'student_name','student_image', 'course', 'rating', 'feedback_text', 'submitted_at']
        read_only_fields = ['student', 'submitted_at','course']

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value

    def get_student_image(self, obj):
        if obj.student.profile_picture:
            return obj.student.profile_picture.url
        return ""  # or return a default image path

class WishlistSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source='course.title', read_only=True)
    course_id = serializers.IntegerField(source='course.id', read_only=True)
    average_rating = serializers.SerializerMethodField()
    rated_members = serializers.SerializerMethodField()
    instructor_name = serializers.SerializerMethodField()
    price = serializers.DecimalField(source='course.price', max_digits=10, decimal_places=2, read_only=True)
    course_image = serializers.SerializerMethodField()

    class Meta:
        model = Wishlist
        fields = [
            'id',
            'course_id',
            'course_title',
            'price',
            'average_rating',
            'rated_members',
            'instructor_name',
            'added_at',
            'course_image'
        ]

    def get_average_rating(self, obj):
        return round(obj.course.feedbacks.aggregate(Avg('rating'))['rating__avg'] or 0, 2)

    def get_rated_members(self, obj):
        return obj.course.feedbacks.count()

    def get_instructor_name(self, obj):
        instructor = getattr(obj.course, 'instructor', None)
        if instructor and instructor.user:
            return instructor.user.username
        return None

    def get_course_image(self, obj):
        request = self.context.get('request')
        image_url = obj.course.course_image.url if obj.course.course_image else None
        if image_url and request is not None:
            return request.build_absolute_uri(image_url)
        return image_url
        

# serializers.py
class CartItemSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source='course.title', read_only=True)
    course_price = serializers.DecimalField(source='course.price', max_digits=10, decimal_places=2, read_only=True)
    course_discount = serializers.DecimalField(source='course.discount', max_digits=10, decimal_places=2, read_only=True)
    instructor_name = serializers.CharField(source='course.instructor.user.username', read_only=True)
    average_rating = serializers.SerializerMethodField()
    total_feedbacks = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = [
            'id',
            'student',
            'course',
            'added_at',
            'course_title',
            'course_price',
            'course_discount',
            'instructor_name',
            'average_rating',
            'total_feedbacks',
        ]
        read_only_fields = ['student', 'added_at']

    def get_average_rating(self, obj):
        feedbacks = obj.course.feedbacks.all()
        return round(feedbacks.aggregate(Avg('rating'))['rating__avg'] or 0, 1)

    def get_total_feedbacks(self, obj):
        return obj.course.feedbacks.count()


        
class JobPostSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = '__all__'
        
# from .models import JobApplications

class JobApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobApplications
        fields = '__all__'

