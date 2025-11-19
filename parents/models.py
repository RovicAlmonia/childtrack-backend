from django.db import models
from django.contrib.auth.models import User
from teacher.models import TeacherProfile

class Student(models.Model):
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
    ]
    
    lrn = models.CharField(max_length=20, unique=True, primary_key=True)
    name = models.CharField(max_length=100)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True, null=True)
    grade_level = models.CharField(max_length=20, blank=True, null=True)
    section = models.CharField(max_length=50, blank=True, null=True)
    teacher = models.ForeignKey(
        TeacherProfile, 
        on_delete=models.CASCADE,
        related_name='students'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} (LRN: {self.lrn}) - {self.teacher.user.username}"
    
    class Meta:
        ordering = ['teacher', 'name']
        verbose_name = "Student"
        verbose_name_plural = "Students"


class ParentGuardian(models.Model):
    ROLE_CHOICES = [
        ('Parent1', 'Parent 1'),
        ('Parent2', 'Parent 2'),
        ('Guardian', 'Guardian'),
    ]
    
    student = models.ForeignKey(
        Student, 
        on_delete=models.CASCADE, 
        related_name='parents_guardians'
    )
    teacher = models.ForeignKey(
        TeacherProfile,
        on_delete=models.CASCADE,
        related_name='parents_guardians'
    )
    name = models.CharField(max_length=100)
    
    username = models.CharField(max_length=100, blank=True, null=True)
    password = models.CharField(max_length=100, blank=True, null=True)
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    contact_number = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    qr_code_data = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.role}) - {self.student.name} - Teacher: {self.teacher.user.username}"
    
    class Meta:
        unique_together = ['student', 'role']
        ordering = ['teacher', 'student', 'role']
        verbose_name = "Parent/Guardian"
        verbose_name_plural = "Parents/Guardians"


class ParentMobileAccount(models.Model):
    """Mobile app account for parents/guardians"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='parent_mobile_account')
    parent_guardian = models.OneToOneField(
        ParentGuardian, 
        on_delete=models.CASCADE, 
        related_name='mobile_account'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.parent_guardian.name}"
    
    class Meta:
        verbose_name = "Parent Mobile Account"
        verbose_name_plural = "Parent Mobile Accounts"
        


class MobileRegistration(models.Model):
    phone_number = models.CharField(max_length=15, unique=True)
    verification_code = models.CharField(max_length=6, blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'parents_mobileregistration'
        
    def __str__(self):
        return f"{self.phone_number} - {'Verified' if self.is_verified else 'Unverified'}"



class ParentNotification(models.Model):
    NOTIFICATION_TYPES = [
        ('attendance', 'Attendance'),
        ('pickup', 'Pickup'),
        ('event', 'Event'),
        ('other', 'Other'),
    ]

    parent = models.ForeignKey(
        ParentGuardian,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='notifications',
        blank=True,
        null=True
    )
    type = models.CharField(max_length=32, choices=NOTIFICATION_TYPES, default='other')
    message = models.TextField()
    extra_data = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        parent_name = self.parent.name if self.parent_id else 'Unknown'
        return f"Notification to {parent_name}: {self.type}"



class ParentEvent(models.Model):
    EVENT_TYPES = [
        ('school', 'School'),
        ('meeting', 'Meeting'),
        ('reminder', 'Reminder'),
        ('other', 'Other'),
    ]

    parent = models.ForeignKey(
        ParentGuardian,
        on_delete=models.CASCADE,
        related_name='events'
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='events',
        blank=True,
        null=True
    )
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    event_type = models.CharField(max_length=32, choices=EVENT_TYPES, default='other')
    scheduled_at = models.DateTimeField(blank=True, null=True)
    location = models.CharField(max_length=150, blank=True)
    extra_data = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-scheduled_at', '-created_at']

    def __str__(self):
        parent_name = self.parent.name if self.parent_id else 'Unknown'
        return f"Event for {parent_name}: {self.title}"


class ParentSchedule(models.Model):
    DAYS_OF_WEEK = [
        ('monday', 'Monday'),
        ('tuesday', 'Tuesday'),
        ('wednesday', 'Wednesday'),
        ('thursday', 'Thursday'),
        ('friday', 'Friday'),
        ('saturday', 'Saturday'),
        ('sunday', 'Sunday'),
    ]

    parent = models.ForeignKey(
        ParentGuardian,
        on_delete=models.CASCADE,
        related_name='schedules',
        blank=True,
        null=True,
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='schedules',
    )
    teacher = models.ForeignKey(
        TeacherProfile,
        on_delete=models.CASCADE,
        related_name='schedules',
        blank=True,
        null=True,
    )
    subject = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    day_of_week = models.CharField(max_length=9, choices=DAYS_OF_WEEK, blank=True)
    start_time = models.TimeField(blank=True, null=True)
    end_time = models.TimeField(blank=True, null=True)
    time_label = models.CharField(max_length=120, blank=True)
    room = models.CharField(max_length=50, blank=True)
    icon = models.CharField(max_length=64, blank=True, default='book-outline')
    extra_data = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['student', 'day_of_week', 'start_time', 'subject', 'created_at']

    def __str__(self):
        student_name = self.student.name if self.student_id else 'Unknown student'
        return f"{self.subject} - {student_name}"



