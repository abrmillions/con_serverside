from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0002_customuser_phone_customuser_profile_photo'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='email_verified',
            field=models.BooleanField(default=False),
        ),
    ]
