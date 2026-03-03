from django.db import migrations, models
import django.db.models.deletion
import uuid
from django.conf import settings


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Company",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("name", models.CharField(max_length=255, unique=True)),
                ("registration_number", models.CharField(max_length=100, unique=True, blank=True, null=True)),
                ("address", models.TextField(blank=True, null=True)),
                ("city", models.CharField(max_length=100, blank=True, null=True)),
                ("state", models.CharField(max_length=100, blank=True, null=True)),
                ("zip_code", models.CharField(max_length=20, blank=True, null=True)),
                ("phone", models.CharField(max_length=20, blank=True, null=True)),
                ("email", models.EmailField(max_length=254, blank=True, null=True)),
                ("website", models.URLField(blank=True, null=True)),
                ("registration_date", models.DateField(auto_now_add=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("contact_person", models.ForeignKey(related_name="managed_companies", on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, blank=True, null=True)),
            ],
        ),
    ]
