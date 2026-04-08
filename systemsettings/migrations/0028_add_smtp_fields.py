
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('systemsettings', '0027_remove_systemsettings_use_brevo_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemsettings',
            name='email_provider',
            field=models.CharField(choices=[('brevo', 'Brevo'), ('smtp', 'SMTP')], default='brevo', help_text='Email service provider', max_length=20),
        ),
        migrations.AddField(
            model_name='systemsettings',
            name='smtp_host',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='systemsettings',
            name='smtp_port',
            field=models.IntegerField(blank=True, default=587, null=True),
        ),
        migrations.AddField(
            model_name='systemsettings',
            name='smtp_user',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='systemsettings',
            name='smtp_password',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='systemsettings',
            name='smtp_use_tls',
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name='systemsettings',
            name='brevo_api_key',
            field=models.CharField(blank=True, help_text='Brevo API Key', max_length=255),
        ),
    ]
