from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('guardian', '0001_initial'),
        ('parents', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='guardian',
            name='student',
            field=models.ForeignKey(
                to='parents.student',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='guardians',
                null=True,
                blank=True,
            ),
        ),
    ]
