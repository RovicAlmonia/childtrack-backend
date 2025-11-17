from django.db import models
from teacher.models import TeacherProfile

class Guardian(models.Model):
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE, related_name='guardians')
    name = models.CharField(max_length=255)
    age = models.IntegerField()
    address = models.TextField(blank=True, null=True)
    relationship = models.CharField(max_length=100, blank=True, null=True)
    contact = models.CharField(max_length=50, blank=True, null=True)
    student_name = models.CharField(max_length=255)
    photo = models.ImageField(upload_to='guardian_photos/', blank=True, null=True)  # NEW FIELD
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.name} - Guardian of {self.student_name}"
