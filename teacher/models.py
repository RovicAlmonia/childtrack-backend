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
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE)
    student_name = models.CharField(max_length=100)
    qr_code_data = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.student_name} - {self.timestamp}"
