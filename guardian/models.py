from django.db import models
from teacher.models import TeacherProfile

class Guardian(models.Model):
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    age = models.IntegerField()
    address = models.TextField()
    relationship = models.CharField(max_length=50)
    contact = models.CharField(max_length=15)
    student_name = models.CharField(max_length=100)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} - {self.student_name}"
    
    class Meta:
        verbose_name = "Guardian"
        verbose_name_plural = "Guardians"
        ordering = ['-timestamp']
