from django.contrib import admin
from .models import *
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin


# Register your models here.
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'role')
    list_filter = ('role',)
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email', 'role')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login',)}),   
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'role', 'is_active', 'is_staff', 'is_superuser')}
        ),
    )
    search_fields = ('username', 'email')
    ordering = ('username',)
    filter_horizontal = ('groups', 'user_permissions',)
    list_per_page = 10
admin.site.register(CustomUser, UserAdmin)
admin.site.register(Course)
admin.site.register(Job)
admin.site.register(JobApplications)
admin.site.register(Lesson)
admin.site.register(Concept)
admin.site.register(LessonContent)
admin.site.register(Assignment)
admin.site.register(LiveClass)
admin.site.register(Category)
admin.site.register(SubCategory)
admin.site.register(CoursePayment)




