from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("guardian", "0003_add_missing_columns"),
    ]

    operations = [
        migrations.AlterField(
            model_name="guardian",
            name="contact",
            field=models.CharField(max_length=50, null=True, blank=True),
        ),
    ]
