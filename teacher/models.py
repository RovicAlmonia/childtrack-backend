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
    
    # Guardian information fields (NEW - add these)
    guardian_name = models.CharField(max_length=100, blank=True, null=True)
    guardian_age = models.IntegerField(blank=True, null=True)
    guardian_address = models.TextField(blank=True, null=True)
    guardian_relationship = models.CharField(max_length=50, blank=True, null=True)
    guardian_contact = models.CharField(max_length=15, blank=True, null=True)
    is_unregistered = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.student_name} - {self.timestamp}"

# REMOVE UnregisteredGuardian model completely - don't use it
