from django.db import migrations, models
import django.db.models.deletion
import uuid
from django.conf import settings


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("licenses", "0010_license_company_license_replacement_reason_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="LicenseStatusHistory",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("old_status", models.CharField(max_length=20)),
                ("new_status", models.CharField(max_length=20)),
                ("change_date", models.DateTimeField(auto_now_add=True)),
                ("reason", models.TextField(blank=True, null=True)),
                ("changed_by", models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, null=True, blank=True)),
                ("license", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="licenses.license", related_name="status_history")),
            ],
            options={"ordering": ["-change_date"]},
        ),
    ]
