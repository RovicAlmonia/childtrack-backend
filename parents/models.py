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
        try:
            teacher_name = self.teacher.user.username if self.teacher and hasattr(self.teacher, 'user') else 'No Teacher'
            return f"{self.name} (LRN: {self.lrn}) - {teacher_name}"
        except:
            return f"{self.name} (LRN: {self.lrn})"
    
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
    must_change_credentials = models.BooleanField(default=False)
    avatar = models.ImageField(upload_to='parent_avatars/', blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    contact_number = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    qr_code_data = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        try:
            student_name = self.student.name if self.student else 'No Student'
            teacher_name = self.teacher.user.username if self.teacher and hasattr(self.teacher, 'user') else 'No Teacher'
            return f"{self.name} ({self.role}) - {student_name} - Teacher: {teacher_name}"
        except:
            return f"{self.name} ({self.role})"
    
    class Meta:
        unique_together = ['student', 'role']
        ordering = ['teacher', 'student', 'role']
        verbose_name = "Parent/Guardian"
        verbose_name_plural = "Parents/Guardians"

    def save(self, *args, **kwargs):
        """
        Auto-generate username/password when not provided and mark the record
        as requiring a credentials change on first login.
        This makes the behavior consistent whether records are created via
        the registration endpoint or the Django admin.
        """
        # determine if this is a new record
        is_new = self.pk is None

        orig_username = getattr(self, 'username', None)
        orig_password = getattr(self, 'password', None)

        username_missing = not orig_username or str(orig_username).strip() == ''
        password_missing = not orig_password or str(orig_password).strip() == ''

        generated_username = None
        if username_missing:
            # derive last token of the name as default username
            name_parts = (self.name or '').strip().split()
            base = name_parts[-1] if len(name_parts) else 'parent'
            candidate = base
            suffix = 1
            # avoid simple collisions by appending a numeric suffix when necessary
            while ParentGuardian.objects.filter(username=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base}{suffix}"
                suffix += 1
            self.username = candidate
            generated_username = candidate

        if password_missing:
            uname_for_pw = generated_username or (self.username or 'parent')
            self.password = f"{uname_for_pw}123"

        # If either credential was auto-generated on creation, require change on first login
        if is_new and (username_missing or password_missing):
            self.must_change_credentials = True

        super().save(*args, **kwargs)


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
        try:
            username = self.user.username if self.user else 'No User'
            parent_name = self.parent_guardian.name if self.parent_guardian else 'No Parent'
            return f"{username} - {parent_name}"
        except:
            return f"Mobile Account #{self.pk}"
    
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
        try:
            parent_name = self.parent.name if self.parent else 'Unknown'
            return f"Notification to {parent_name}: {self.type}"
        except:
            return f"Notification #{self.pk}"


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
        try:
            parent_name = self.parent.name if self.parent else 'Unknown'
            return f"Event for {parent_name}: {self.title}"
        except:
            return f"Event: {self.title}"


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
        try:
            student_name = self.student.name if self.student else 'Unknown student'
            return f"{self.subject} - {student_name}"
        except:
            return f"{self.subject}"


