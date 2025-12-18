# Generated manually: set default for photo to avoid NULL inserts
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('guardian', '0002_alter_guardian_options_alter_guardian_contact_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='guardian',
            name='photo',
            field=models.TextField(blank=True, default=''),
        ),
    ]
