from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('systemsettings', '0006_systemsettings_use_gmail_oauth'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemsettings',
            name='gemini_api_key',
            field=models.CharField(blank=True, default='', help_text='Google Gemini API key for document verification', max_length=255),
        ),
    ]
