from django.db import models
from teacher.models import TeacherProfile

class Student(models.Model):
    lrn = models.CharField(max_length=20, unique=True, primary_key=True)
    name = models.CharField(max_length=100)
    grade_level = models.CharField(max_length=20, blank=True, null=True)
    section = models.CharField(max_length=50, blank=True, null=True)
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE, related_name='students')  # ✅ Required now
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} (LRN: {self.lrn}) - Teacher: {self.teacher.user.username}"
    
    class Meta:
        ordering = ['name']
        verbose_name = "Student"
        verbose_name_plural = "Students"

class ParentGuardian(models.Model):
    ROLE_CHOICES = [
        ('Parent1', 'Parent 1'),
        ('Parent2', 'Parent 2'),
        ('Guardian', 'Guardian'),
    ]
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='parents_guardians')
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE, related_name='parents_guardians')  # ✅ Added
    name = models.CharField(max_length=100)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    contact_number = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    qr_code_data = models.TextField()  # JSON string with all info
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.role}) - {self.student.name} - Teacher: {self.teacher.user.username}"
    
    class Meta:
        unique_together = ['student', 'role']
        ordering = ['student', 'role']
        verbose_name = "Parent/Guardian"
        verbose_name_plural = "Parents/Guardians"
