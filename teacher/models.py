from django.db import models
from django.contrib.auth.models import User


class TeacherProfile(models.Model):
    """
    Teacher profile model that extends the Django User model.
    Stores additional information about teachers including their section assignment.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile')
    name = models.CharField(max_length=100)
    age = models.IntegerField()
    gender = models.CharField(max_length=10)
    section = models.CharField(max_length=50)
    contact = models.CharField(max_length=15)
    address = models.TextField()
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Teacher Profile'
        verbose_name_plural = 'Teacher Profiles'
    
    def __str__(self):
        return f"{self.name} - {self.section}"


class Attendance(models.Model):
    """
    Attendance model to track student attendance records.
    Supports AM/PM sessions and various attendance statuses.
    """
    STATUS_CHOICES = [
        ('Present', 'Present'),
        ('Absent', 'Absent'),
        ('Late', 'Late'),
        ('Drop-off', 'Drop-off'),
        ('Pick-up', 'Pick-up'),
        ('Dropped Out', 'Dropped Out'),
    ]
    
    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
    ]
    
    SESSION_CHOICES = [
        ('AM', 'Morning'),
        ('PM', 'Afternoon'),
    ]
    
    teacher = models.ForeignKey(
        TeacherProfile, 
        on_delete=models.CASCADE, 
        related_name='attendances'
    )
    student_name = models.CharField(max_length=100)
    student_lrn = models.CharField(max_length=50, blank=True, null=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default='Male')
    date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Present')
    session = models.CharField(
        max_length=2,
        choices=SESSION_CHOICES,
        null=True,
        blank=True
    )
    qr_code_data = models.TextField(blank=True, null=True)
    reason = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date', '-timestamp']
        unique_together = ['teacher', 'student_name', 'date', 'session']
        verbose_name = 'Attendance Record'
        verbose_name_plural = 'Attendance Records'
        indexes = [
            models.Index(fields=['teacher', 'date']),
            models.Index(fields=['student_name']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        session_str = f" ({self.session})" if self.session else ""
        return f"{self.student_name} - {self.status} - {self.date}{session_str}"


class UnauthorizedPerson(models.Model):
    """
    Model to track unauthorized persons attempting to access or pick up students.
    Stores information about the person and their relation to the student.
    """
    teacher = models.ForeignKey(
        TeacherProfile, 
        on_delete=models.CASCADE, 
        related_name='unauthorized_persons'
    )
    name = models.CharField(max_length=100)
    address = models.TextField()
    age = models.IntegerField()
    student_name = models.CharField(max_length=100)
    guardian_name = models.CharField(max_length=100)
    relation = models.CharField(max_length=50)
    contact = models.CharField(max_length=15)
    photo = models.TextField(blank=True, null=True)  # Base64 encoded image
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Unauthorized Person'
        verbose_name_plural = 'Unauthorized Persons'
        indexes = [
            models.Index(fields=['teacher', 'timestamp']),
            models.Index(fields=['student_name']),
        ]
    
    def __str__(self):
        return f"{self.name} (attempted access to {self.student_name})"
