from django.db import migrations


def prune_duplicate_partnerships(apps, schema_editor):
    Partnership = apps.get_model('partnerships', 'Partnership')
    ApprovalLog = apps.get_model('partnerships', 'PartnershipApprovalLog')
    PartnershipDocument = apps.get_model('partnerships', 'PartnershipDocument')
    db_alias = schema_editor.connection.alias

    # Build map owner_id -> [partnerships]
    by_owner = {}
    for p in Partnership.objects.using(db_alias).all():
        oid = getattr(p, 'owner_id', None)
        if not oid:
            # Leave records without owner untouched
            continue
        by_owner.setdefault(oid, []).append(p)

    for owner_id, items in by_owner.items():
        if len(items) <= 1:
            continue
        # Choose the partnership to keep: prefer latest created_at, fallback to max id
        def keyf(x):
            ca = getattr(x, 'created_at', None)
            return (ca or 0, x.pk)
        items_sorted = sorted(items, key=keyf)
        keep = items_sorted[-1]
        to_delete = [p for p in items_sorted[:-1] if p.pk != keep.pk]

        # Re-attach ApprovalLogs and Documents to kept partnership
        for p in to_delete:
            # Move approval logs
            for log in ApprovalLog.objects.using(db_alias).filter(partnership_id=p.pk):
                log.partnership_id = keep.pk
                log.save(update_fields=['partnership'])
            # Move documents
            for doc in PartnershipDocument.objects.using(db_alias).filter(partnership_id=p.pk):
                doc.partnership_id = keep.pk
                doc.save(update_fields=['partnership'])
            # Finally delete duplicate partnership
            p.delete()


class Migration(migrations.Migration):
    dependencies = [
        ('partnerships', '0006_partnership_cp_id'),
    ]

    operations = [
        migrations.RunPython(prune_duplicate_partnerships, migrations.RunPython.noop),
    ]

