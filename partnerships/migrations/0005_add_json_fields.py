from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('partnerships', '0004_remove_partnership_description_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='partnership',
            name='registration_data',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='partnership',
            name='partners_data',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
