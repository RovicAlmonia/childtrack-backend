from django.db import models
from django.contrib.auth.models import User

class TeacherProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    age = models.IntegerField()
    gender = models.CharField(max_length=10)
    section = models.CharField(max_length=50)
    contact = models.CharField(max_length=15)
    address = models.TextField()
    
    def __str__(self):
        return self.user.username

class Attendance(models.Model):
    STATUS_CHOICES = [
        ('Present', 'Present'),
        ('Absent', 'Absent'),
        ('Late', 'Late'),
        ('Drop-off', 'Drop-off'),
        ('Pick-up', 'Pick-up'),
        ('Dropped Out', 'Dropped Out'),  # Added new status
    ]
    
    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
    ]
    
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE, related_name='attendances')
    student_name = models.CharField(max_length=100)
    student_lrn = models.CharField(max_length=50, blank=True, null=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default='Male')
    date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Present')
    qr_code_data = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    session = models.CharField(
        max_length=2,
        choices=[('AM', 'Morning'), ('PM', 'Afternoon')],
        null=True,
        blank=True
    )
    reason = models.TextField(blank=True, null=True)  # Added for dropout reason
    
    class Meta:
        ordering = ['-date', '-timestamp']
        unique_together = ['teacher', 'student_name', 'date', 'session']
    
    def __str__(self):
        return f"{self.student_name} - {self.status} - {self.date}"

class UnauthorizedPerson(models.Model):
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE, related_name='unauthorized_persons')
    name = models.CharField(max_length=100)
    address = models.TextField()
    age = models.IntegerField()
    student_name = models.CharField(max_length=100)
    guardian_name = models.CharField(max_length=100)
    relation = models.CharField(max_length=50)
    contact = models.CharField(max_length=15)
    photo = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.name} - {self.student_name}"class UnauthorizedPerson(models.Model):
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE, related_name='unauthorized_persons')
    name = models.CharField(max_length=100)
    address = models.TextField()
    age = models.IntegerField()
    student_name = models.CharField(max_length=100)
    guardian_name = models.CharField(max_length=100)
    relation = models.CharField(max_length=50)
    contact = models.CharField(max_length=15)
    photo = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.name} - {self.student_name}"
