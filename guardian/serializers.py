from rest_framework import serializers
from .models import Guardian

class GuardianSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source='teacher.user.username', read_only=True)
    
    class Meta:
        model = Guardian
        fields = ['id', 'teacher', 'teacher_name', 'name', 'age', 'address', 
                  'relationship', 'contact', 'student_name', 'timestamp']
        read_only_fields = ['timestamp']
