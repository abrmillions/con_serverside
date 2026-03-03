from django.core.management.base import BaseCommand
from documents.models import Document
from documents.utils import infer_document_name
import os

class Command(BaseCommand):
    help = "Backfill human-friendly names for existing Document records"

    def handle(self, *args, **options):
        qs = Document.objects.all()
        updated = 0
        for doc in qs.iterator():
            try:
                current = (doc.name or "").strip()
                candidate_source = current or (getattr(doc.file, "name", "") or "")
                if not candidate_source:
                    continue
                inferred = infer_document_name(candidate_source)
                if not current or current.strip().lower() in {"", os.path.basename(getattr(doc.file, "name", "")).lower()} or current.islower():
                    if inferred and inferred != current:
                        doc.name = inferred
                        doc.save(update_fields=["name"])
                        updated += 1
            except Exception:
                continue
        self.stdout.write(self.style.SUCCESS(f"Backfill complete. Updated {updated} documents."))

