from django.urls import path, include
from .views import *
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from rest_framework.routers import DefaultRouter
from django.conf.urls.static import static
from django.conf import settings

router = DefaultRouter()
router.register(r'live_classes', LiveClassViewSet, basename='liveclass')
router.register(r'certificate-templates', CertificateTemplateViewSet, basename='certificate-templates')
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'subcategories', SubCategoryViewSet, basename='subcategory')



urlpatterns =[
    
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('add_teacher/',AddTeacherView.as_view(),name='add-teacher'),
    path('verify-teacher/<uidb64>/<token>/',VerifyTeacherView.as_view(),name='verify-teacher'),
    path('forgot-password/',ForgotPasswordView.as_view(),name='forgot-password'),
    path('reset-password/<uidb64>/<token>/',ResetPasswordView.as_view(),name='reset-password'),
    path('student-register/',StudentRegisterView.as_view(),name='student-register'),
    path('category-course-count/', CategoryCourseCountView.as_view(), name='category-course-count'),
    path('category-subcategory/', CategoryWithSubcategoryView.as_view(), name='category-subcategory'),
    path('courses/<int:course_id>/feedback/', CourseFeedbackList.as_view(), name='course-feedback-list'),

    # instructor urls
    path('profile/', InstructorProfileView.as_view(), name="instructor-profile"),
    path('student/profile/', StudentProfileView.as_view(), name="student-profile"),
    path('create-course/',CourseCreateView.as_view(),name='create-course'),
    path('courses/', CourseListView.as_view(), name='course-list'),
    path('instructor/courses/', InstructorCourseListView.as_view(), name='instructor-courses'),
    path('update-course/<int:course_id>/',CourseUpdateView.as_view(),name='update-course'),
    path('delete-course/<int:course_id>/', CourseDeleteView.as_view(), name='delete-course'),
    path('courses/<int:course_id>/restore/', CourseRestoreView.as_view(), name='restore-course'),
    path('courses/<int:course_id>/lessons/', LessonCreateView.as_view(), name='create-lesson'),
    path('courses/<int:course_id>/lessons/list/', LessonListView.as_view(), name='list-lessons'),
    path('courses/<int:course_id>/lessons/<int:lesson_id>/delete/', LessonDeleteView.as_view(), name='delete-lesson'),
    path('courses/<int:course_id>/lessons/<int:lesson_id>/restore/', LessonRestoreView.as_view(), name='restore-lesson'),
    path('courses/lessons/<int:lesson_id>/update/', LessonUpdateView.as_view(), name='update-lesson'),
    path('lessons/<int:lesson_id>/concepts/', ConceptCreateView.as_view(), name='add-concept'),
    path('lessons/<int:lesson_id>/concepts/list/', ConceptListView.as_view(), name='list-concepts'),
    path('lessons/<int:lesson_id>/concepts/<int:concept_id>/delete/', ConceptDeleteView.as_view(), name='delete-concept'),
    path('lessons/<int:lesson_id>/concepts/<int:concept_id>/restore/', ConceptRestoreView.as_view(), name='restore-concept'),
    path('lessons/concepts/<int:concept_id>/update/', ConceptUpdateView.as_view(), name='update-concept'),
    path('concepts/<int:concept_id>/contents/', LessonContentCreateView.as_view(), name='add-content'),
    path('concepts/<int:concept_id>/contents/list/', LessonContentListView.as_view(), name='list-contents'),
    path('concepts/<int:concept_id>/content/<int:content_id>/update/', LessonContentUpdateView.as_view(), name='lesson-content-update'),
    path('concepts/<int:concept_id>/content/<int:content_id>/delete/', LessonContentDeleteView.as_view(), name='delete-lesson-content'),
    path('upload-image/', UploadImageView.as_view(), name='upload-image'),
    path('content/<int:content_id>/video-questions/', VideoQuestionListCreateView.as_view(), name='video-question-list-create'),
    path('video-questions/<int:id>/delete/', VideoQuestionDeleteView.as_view(), name='video-question-delete'),
    path('video-questions/<int:id>/update/', VideoQuestionUpdateView.as_view(), name='video-question-update'),
    path('assignments/bulk-create/', AssignmentCreateView.as_view(), name='bulk-create-assignment'),
    path('courses/<int:course_id>/assignments/', AssignmentListView.as_view(), name='get-assignments'),
    path('courses/<int:course_id>/assignments/<int:assignment_id>/delete/', AssignmentDeleteView.as_view(), name='delete-assignment'),
    path('courses/<int:course_id>/assignments/delete-all/', DeleteAllAssignmentsView.as_view(), name='delete-all-assignments'),
    path('courses/<int:course_id>/chat/', CourseChatView.as_view(), name='course-chat'),
    path('courses/<int:course_id>/chat/private/<int:user_id>/', PrivateMessageView.as_view(), name='private-chat'),
    path('chat/private/students/', PrivateChatStudentListView.as_view(), name='chat-student-list'),
    path('chat/private/thread/<int:user_id>/', PrivateChatThreadView.as_view(), name='chat-thread'),
    path('chat/private/message/<int:message_id>/edit/', EditPrivateMessageView.as_view(), name='edit-private-message'),
    path('chat/private/message/<int:message_id>/delete/', DeletePrivateMessageView.as_view(), name='delete-private-message'),
    path('chat/private/instructors/', PrivateChatInstructorListView.as_view(), name='chat-instructor-list'),
    path('chat/private/mark-seen/', MarkMessagesAsSeenView.as_view(), name='mark-chat-seen'),

    path('courses/<int:course_id>/set-certificate/', SetCertificateTemplateView.as_view(), name='set-certificate'),
    path('courses/<int:course_id>/issue-certificate/', CheckAndIssueCertificateView.as_view(), name='issue-certificate'),


        # student urls
    path('student/profile/', StudentProfileView.as_view(), name="student-profile"),
    path('courses/<int:course_id>/enroll/', EnrollStudentView.as_view(), name='enroll-student'),
    path('courses/<int:course_id>/students/', EnrolledStudentsListView.as_view(), name='enrolled-students'),
    
    path('courses/<int:course_id>/certificate/', CertificateDownloadView.as_view(), name='certificate-download'),
    path("certificate/verify/<str:certificate_id>/", VerifyCertificateView.as_view()),
    path('concepts/<int:concept_id>/note/', SaveNoteView.as_view(), name='save-note'),
    path('concepts/<int:concept_id>/note/get/', GetNoteView.as_view(), name='get-note'),
    path('courses/<int:course_id>/feedback/submit/', SubmitCourseFeedback.as_view(), name='submit-feedback'),
    path('wishlist/', WishlistListView.as_view(), name='wishlist-list'),
    path('wishlist/add/<int:course_id>/', AddToWishlistView.as_view(), name='wishlist-add'),
    path('wishlist/remove/<int:course_id>/', RemoveFromWishlistView.as_view(), name='wishlist-remove'),
        
    # ameer added routes 
            #new urls
        # instructor
    path('instructor/create-course/', InstructorCourseCreateView.as_view(), name='instructor-create-course'),

    path('instructor/create-course/<int:course_id>/', InstructorCourseCreateView.as_view()),


    path('instructor/update-course/<int:course_id>/advanced/', CourseAdvancedInfoUpdateView.as_view(), name='course-advanced-update'),

    path('instructor/update-course/<int:course_id>/curriculum/', CourseCurriculumCompleteView.as_view(), name='course-curriculum-update'),

    path('instructor/publish-course/<int:course_id>/', PublishCourseView.as_view(), name='course-publish'),
    
    path('instructor/final-publish-course/<int:course_id>/', FinalPublishCourseView.as_view()),

    path('instructor/course-review/<int:course_id>/', CourseReviewAPIView.as_view(), name='course-review'),

    

    path('courses/<int:course_id>/assignments/upload/', UploadAssignmentFileView.as_view(), name='upload-assignment-file'),

    path('chat/private/students-with-last-message/',PrivateMessageStudentListWithLastMessageView.as_view(),name='chat-student-list-with-last-message'),
    path('instructor/draft-courses/', DraftCoursesListView.as_view(), name='draft-courses'),
    path('instructor/course-detail/<int:course_id>/', InstructorCourseDetailView.as_view(), name='instructor-course-detail'),
    path('notifications/unread/', UnreadNotificationsView.as_view(), name='unread-notifications'),




        # student
        path('student/course-summary/', EnrolledCourseSummaryView.as_view(), name='course-summary'),

    path('courses/', CourseListView.as_view(), name='course-list'),
    path('course-detail-full/<int:course_id>/', CourseDetailFullView.as_view(), name='course-detail-full'),
    path('student/enrolled-courses/', EnrolledCoursesRawView.as_view(), name='student-enrolled-courses'),
path('watch-course/<int:course_id>/', CourseDetailView.as_view(), name='watch-course'),
path('submit-quiz/', SubmitQuizView.as_view(), name='submit-quiz'),
path('courses/<int:course_id>/content/<int:content_id>/auto-complete/', AutoCompleteContentView.as_view(), name='auto-complete-content'),
    path('courses/<int:course_id>/progress/', CourseProgressView.as_view(), name='course-progress'),
        path('courses/<int:course_id>/assignments/submit/', SubmitAssignmentView.as_view(), name='submit-assignment'),

    path('courses/<int:course_id>/assignment-results/', StudentAssignmentResultView.as_view(), name='assignment-results'),
    path('student/enrolled-instructors/', EnrolledCourseInstructorsView.as_view(), name='enrolled-instructors'),
path('student/enrolled-course-instructors/', EnrolledCourseInstructorsView.as_view(), name='enrolled-course-instructors'),
path('cart/', ListCartItemsView.as_view(), name='cart-list'),
path('cart/add/<int:course_id>/', AddToCartView.as_view(), name='cart-add'),
path('cart/remove/<int:course_id>/', RemoveFromCartView.as_view(), name='cart-remove'),
# urls.py
path('payment-history/', StudentPaymentHistoryView.as_view(), name='payment-history'),






    
    
    
    path('jobs/', JobPostCreateView.as_view(), name='job-create'),
    
    path('apply/', JobApplicationsView.as_view(), name='apply-for-job'),
    
    path('topinsturctors/',TopInstructorsThisMonthView.as_view(),name='top-instructors'),


# admin

path('instructors/', InstructorListView.as_view(), name='instructor-list'),
path('admin/pending-courses/', PendingCourseListView.as_view(), name='pending-courses'),
    path('admin/course/<int:course_id>/action/', CourseApprovalUpdateView.as_view(), name='course-approval-update'),
path('admin/course/<int:course_id>/', AdminCourseDetailView.as_view(), name='admin-course-detail'),

#payment
path('create-order/<int:course_id>/', CreateRazorpayOrder.as_view(), name='create-order'),
path('create-bulk-order/', CreateBulkRazorpayOrder.as_view(), name='create-bulk-order'),

    path('verify-payment/', VerifyRazorpayPayment.as_view(), name='verify-payment'),
path('verify-bulk-payment/', VerifyBulkRazorpayPayment.as_view(), name='verify-bulk-payment'),



    
    # path('jobs/<int:pk>/', JobPostDetailView.as_view(), name='job-detail'),
    path('', include(router.urls)),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)