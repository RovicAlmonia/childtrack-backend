from django.db import models
from teacher.models import TeacherProfile
from parents.models import ParentGuardian, Student

class Guardian(models.Model):
    teacher = models.ForeignKey(
        TeacherProfile,
        on_delete=models.CASCADE,
        related_name='guardians'
    )

    parent_guardian = models.ForeignKey(
        ParentGuardian,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    student = models.ForeignKey(
        Student,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    name = models.CharField(max_length=100)
    age = models.IntegerField()
    address = models.TextField(blank=True, null=True)
    relationship = models.CharField(max_length=50, blank=True, null=True)
    contact = models.CharField(max_length=20, blank=True, null=True)
    student_name = models.CharField(max_length=100)
    photo = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('allowed', 'Allowed'),
            ('declined', 'Declined')
        ],
        default='pending'
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.name} - {self.student_name}"
