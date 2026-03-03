from django.core.management.base import BaseCommand
from applications.models import Application


def normalize_grade(value: str) -> str:
    s = (value or "").strip().lower()
    if s in ("grade-a", "a", "grade 1", "grade1"):
        return "Grade 1 - Large Projects"
    if s in ("grade-b", "b", "grade 2", "grade2"):
        return "Grade 2 - Medium Projects"
    if s in ("grade-c", "c", "grade 3", "grade3"):
        return "Grade 3 - Small Projects"
    if s in ("specialized", "specialised", "specialized contractor", "specialised contractor"):
        return "Specialized Contractor"
    return value


class Command(BaseCommand):
    def handle(self, *args, **options):
        qs = Application.objects.filter(license_type="Contractor License")
        updated = 0
        for app in qs.iterator():
            try:
                d = app.data or {}
                raw = d.get("grade") or d.get("licenseType") or d.get("category")
                if not raw:
                    continue
                norm = normalize_grade(str(raw))
                if d.get("grade") != norm:
                    d["grade"] = norm
                    app.data = d
                    app.save(update_fields=["data"])
                    updated += 1
            except Exception:
                continue
        self.stdout.write(str(updated))
