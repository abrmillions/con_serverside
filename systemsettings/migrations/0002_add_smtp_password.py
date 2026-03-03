from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('systemsettings', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemsettings',
            name='smtp_password',
            field=models.CharField(max_length=255, default="", blank=True, null=True),
        ),
    ]
