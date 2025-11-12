# teacher/migrations/0002_attendance_student_lrn.py
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('teacher', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='attendance',
            name='student_lrn',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
