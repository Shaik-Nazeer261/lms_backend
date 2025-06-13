from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.conf import settings
import uuid

# Create your models here.
class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('instructor', 'Instructor'),
        ('student', 'Student'),
    )
    role=models.CharField(max_length=10,choices=ROLE_CHOICES,default='student')

    def __str__(self):
        return f"{self.username} - {self.role}"
    
class Instructor(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    headline = models.CharField(max_length=255, blank=True, null=True)
    biography = models.TextField(blank=True, null=True)
    social_links = models.JSONField(default=dict)
    language = models.CharField(max_length=50, blank=True, null=True)
    profile_picture = models.ImageField(upload_to="profile_pics/", blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True, help_text="Include country code, e.g. +919876543210")
    personal_website = models.URLField(blank=True, null=True)
    facebook_url = models.URLField(blank=True, null=True)
    instagram_url = models.URLField(blank=True, null=True)
    linkedin_url = models.URLField(blank=True, null=True)
    twitter_url = models.URLField(blank=True, null=True)
    whatsapp_number = models.CharField(max_length=15, blank=True, null=True)  # phone number format
    youtube_url = models.URLField(blank=True, null=True)

    def __str__(self):
        return self.user.username


class Student(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    headline = models.CharField(max_length=255, blank=True, null=True)
    biography = models.TextField(blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    social_links = models.JSONField(default=dict)
    language = models.CharField(max_length=50, blank=True, null=True)
    profile_picture = models.ImageField(upload_to="profile_pics/", blank=True, null=True)

    def __str__(self):
        return self.user.username

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class SubCategory(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="subcategories")
    name = models.CharField(max_length=100)

    class Meta:
        unique_together = ('category', 'name')

    def __str__(self):
        return f"{self.category.name} > {self.name}"

class Course(models.Model):
    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, blank=True, null=True)
    topic = models.CharField(max_length=255, blank=True, null=True)

    category = models.ForeignKey('Category', on_delete=models.SET_NULL, null=True, related_name='courses')
    subcategory = models.ForeignKey('SubCategory', on_delete=models.SET_NULL, null=True, related_name='courses')

    instructor = models.ForeignKey('Instructor', on_delete=models.CASCADE)
    language = models.CharField(max_length=50, blank=True, null=True)
    subtitle_language = models.CharField(max_length=50, blank=True, null=True)

    course_level = models.CharField(max_length=50, blank=True, null=True)
    time_duration = models.CharField(max_length=50, blank=True, null=True)

    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # e.g. 20.00 means 20%
    coupon_code = models.CharField(max_length=50, blank=True, null=True)


    course_image = models.ImageField(upload_to="course_images/", blank=True, null=True)
    demo_video = models.FileField(upload_to="course_demos/", blank=True, null=True)

    description = models.TextField(blank=True, null=True)
    requirements = models.JSONField(default=list)
    learning_objectives = models.JSONField(default=list)
    target_audiences = models.JSONField(default=list)

    welcome_message = models.TextField(blank=True, null=True)
    congratulation_message = models.TextField(blank=True, null=True)

    is_published = models.BooleanField(default=False)
    creation_step = models.CharField(max_length=50, default='basic')  # e.g., 'basic', 'advanced', 'curriculum', 'publish'
    is_approved = models.BooleanField(default=False)  # Admin-controlled

    students = models.ManyToManyField('Student', related_name='enrolled_courses', blank=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    certificate_template = models.ForeignKey(
        'CertificateTemplate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='courses_using'
    )

    def __str__(self):
        return self.title
#  Lesson Model
class Lesson(models.Model):
    course = models.ForeignKey('Course', on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False)  # Soft delete

    def __str__(self):
        return f"{self.course.title} - {self.title}"

#  Concept Model
class Concept(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='concepts')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    is_deleted = models.BooleanField(default=False)  # Soft delete

    class Meta:
        ordering = ['order']  # Default ordering

    def __str__(self):
        return f"{self.lesson.title} - {self.title}"

#  LessonContent Model
class LessonContent(models.Model):
    CONTENT_TYPE_CHOICES = (
        ('video', 'Video'),
        ('pdf', 'PDF'),
        ('text', 'Text'),
    )

    concept = models.ForeignKey('Concept', on_delete=models.CASCADE, related_name='contents')
    content_type = models.CharField(max_length=10, choices=CONTENT_TYPE_CHOICES)
    
    video = models.FileField(upload_to="lessons/videos/", blank=True, null=True)
    pdf = models.FileField(upload_to="lessons/pdfs/", blank=True, null=True)
    text_content = models.TextField(blank=True, null=True)

    # ✅ New fields from frontend
    captions = models.TextField(blank=True, null=True)
    attached_file = models.FileField(upload_to="lessons/attachments/", blank=True, null=True)
    lecture_notes_text = models.TextField(blank=True, null=True)
    lecture_notes_file = models.FileField(upload_to="lessons/notes/", blank=True, null=True)

    order = models.PositiveIntegerField(default=0)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    duration = models.CharField(max_length=10, blank=True, null=True)  # new field

    class Meta:
        unique_together = ('concept', 'order')
        ordering = ['order']

    def __str__(self):
        return f"{self.concept.title} - {self.content_type} - {self.order}"
    

class ContentCompletion(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    content = models.ForeignKey(LessonContent, on_delete=models.CASCADE)
    video_completed = models.BooleanField(default=False)
    pdf_completed = models.BooleanField(default=False)
    text_completed = models.BooleanField(default=False)

    class Meta:
        unique_together = ('student', 'content')

    def is_fully_completed(self):
        return self.video_completed or self.pdf_completed or self.text_completed


class StudentProgress(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    completed_contents = models.ManyToManyField(LessonContent, blank=True)
    progress_percentage = models.FloatField(default=0.0)

    class Meta:
        unique_together = ('student', 'course')

    def __str__(self):
        return f"{self.student.user.username} - {self.course.title}"


# Quiz Model
class Quiz(models.Model):
    lesson = models.OneToOneField(Lesson, on_delete=models.CASCADE, related_name="quiz")
    instructor = models.ForeignKey(CustomUser, on_delete=models.CASCADE, limit_choices_to={'role': 'instructor'})  #  Correct
    title = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.lesson.title} - {self.title}"

#  QuizQuestion Model
class QuizQuestion(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, null=True, blank=True, related_name='questions')  #  related_name for reverse lookup
    question_text = models.TextField()
    correct_answer = models.CharField(max_length=255)
    options = models.JSONField(default=list)  # Store multiple choices
    lesson_content = models.ForeignKey(LessonContent, null=True, blank=True, on_delete=models.SET_NULL, related_name="quiz_questions")

    def __str__(self):
        if self.quiz:
            return f"{self.quiz.title} - {self.question_text[:50]}"
        elif self.lesson_content:
            return f"Content ID {self.lesson_content.id} - {self.question_text[:50]}"
        else:
            return f"Unlinked Question - {self.question_text[:50]}"

#  QuizResult Model
class QuizResult(models.Model):
    student = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="quiz_results", limit_choices_to={'role': 'student'})  # ✅ Only students
    subject = models.CharField(max_length=255)
    topic = models.CharField(max_length=255)
    score = models.IntegerField()
    total_questions = models.IntegerField()
    correct_answers = models.IntegerField()
    incorrect_answers = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.username} - {self.topic} - {self.score}/{self.total_questions}"
    
class VideoQuestion(models.Model):
    content = models.ForeignKey(LessonContent, on_delete=models.CASCADE, related_name="video_questions")
    timestamp = models.FloatField(help_text="Time in seconds when question appears")
    question_text = models.TextField()
    correct_answer = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

class Assignment(models.Model):
    instructor = models.ForeignKey(Instructor, on_delete=models.CASCADE)  #  Correct
    course = models.ForeignKey('Course', on_delete=models.CASCADE)
    question = models.TextField()
    options = models.JSONField(default=list, blank=True)  #  Add this
    answer = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.course.title} - {self.question[:50]}"
    

class AssignmentSubmission(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE)
    submitted_answer = models.TextField()
    is_correct = models.BooleanField(default=False)
    score = models.FloatField(default=0.0)
    pass_status = models.CharField(max_length=10, default="Fail")  # Pass or Fail
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'assignment')  # Ensures unique submission per student-assignment

    def __str__(self):
        return f"{self.student.user.username} - {self.assignment.question[:30]}"

    


class LiveClass(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    title = models.CharField(max_length=255)
    description = models.TextField()
    scheduled_time = models.DateTimeField()
    meeting_link = models.URLField()
    instructor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="live_classes", null=True, blank=True)
    course = models.ForeignKey("Course", on_delete=models.CASCADE, related_name="live_classes", null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')  # ✅ New field

    def __str__(self):
        return f"{self.title} ({self.course.title})"

class CourseChatMessage(models.Model):
    course = models.ForeignKey('Course', on_delete=models.CASCADE)
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.TextField()
    attachment = models.FileField(upload_to='chat_attachments/', null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    reply_to = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='replies')
    is_edited = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.sender.username}: {self.message[:30]}"
    
class PrivateMessage(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_private_messages")
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="received_private_messages")
    message = models.TextField()
    attachment = models.FileField(upload_to='private_chat_attachments/', null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False)
    is_edited = models.BooleanField(default=False)
    
    #  NEW FIELD for reply support
    reply_to = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='replies')
    is_read = models.BooleanField(default=False)  # ← NEW FIELD

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.sender.username} -> {self.receiver.username}: {self.message[:30]}"

    def is_owner(self, user):
        return self.sender == user
    

class CertificateTemplate(models.Model):
    TEMPLATE_TYPE_CHOICES = (
        ('default', 'Predefined'),   # HTML stored in `html_template`
        ('custom', 'Custom Upload'), # PDF or DOCX uploaded to `file`
    )

    FILE_TYPE_CHOICES = (
    ('html', 'HTML'),
    ('plain', 'Plain Text'),
    ('docx', 'DOCX'),
)


    name = models.CharField(max_length=100)
    type = models.CharField(max_length=10, choices=TEMPLATE_TYPE_CHOICES, default='default')
    instructor = models.ForeignKey(Instructor, on_delete=models.CASCADE, related_name='certificate_templates')
    
    preview_image = models.ImageField(upload_to="certificate_templates/previews/", blank=True, null=True)

    html_template = models.TextField(blank=True, null=True)  # used when file_type == html
    file = models.FileField(upload_to='certificate_templates/files/', blank=True, null=True)  # for custom templates

    file_type = models.CharField(max_length=10, choices=FILE_TYPE_CHOICES, default='html')  # distinguish html/pdf/docx

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.get_type_display()})"
    

class Certificate(models.Model):
    student = models.ForeignKey('Student', on_delete=models.CASCADE)
    course = models.ForeignKey('Course', on_delete=models.CASCADE)
    issue_date = models.DateField(auto_now_add=True)
    certificate_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    pdf_file = models.FileField(upload_to='certificates/')

    class Meta:
        unique_together = ('student', 'course')

    def __str__(self):
        return f"{self.student.user.username} - {self.course.title}"
    

class StudentNote(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    concept = models.ForeignKey(Concept, on_delete=models.CASCADE)
    note = models.TextField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('student', 'concept')


class CourseFeedback(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="feedbacks")
    rating = models.PositiveIntegerField()  # 1 to 5
    feedback_text = models.TextField()
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("student", "course")  # One feedback per student per course

    def __str__(self):
        return f"{self.student.user.username} - {self.course.title} ({self.rating}⭐)"


class Wishlist(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='wishlist_entries')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='wishlisted_entries')
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'course')

    def __str__(self):
        return f"{self.student.user.username} ➜ {self.course.title}"
    

# models.py
class CartItem(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'course')


class Job(models.Model):

    job_title = models.CharField(max_length=255)
    ctc = models.CharField(max_length=50)
    years_of_experience = models.CharField(max_length=100)
    location = models.CharField(max_length=100)
    job_description = models.TextField()
    vacancies = models.IntegerField(default=1)  # new
    last_date_to_apply = models.DateField(null=True, blank=True)  # new
    
    address = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    job_type = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return self.job_title
    
class JobApplications(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='applications')
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone_number = models.CharField(max_length=15)
    education = models.CharField(max_length=100)
    experience = models.PositiveIntegerField()
    resume = models.FileField(upload_to='resumes/')
    cover_letter = models.TextField()
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.job.title}"
    

class CoursePayment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    original_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    razorpay_order_id = models.CharField(max_length=100)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=100, blank=True, null=True)
    is_paid = models.BooleanField(default=False)
    payment_status = models.CharField(max_length=20, choices=[
    ("pending", "Pending"),
    ("success", "Success"),
    ("failed", "Failed")
    ], default="pending")
    created_at = models.DateTimeField(auto_now_add=True)


