from django.db import migrations


def prune_duplicate_vehicles(apps, schema_editor):
    Vehicle = apps.get_model('vehicles', 'Vehicle')
    db_alias = schema_editor.connection.alias

    by_owner = {}
    for v in Vehicle.objects.using(db_alias).all():
        oid = getattr(v, 'owner_id', None)
        if not oid:
            continue
        by_owner.setdefault(oid, []).append(v)

    for owner_id, items in by_owner.items():
        if len(items) <= 1:
            continue
        def keyf(x):
            ca = getattr(x, 'registered_at', None) or getattr(x, 'created_at', None)
            return (ca or 0, x.pk)
        items_sorted = sorted(items, key=keyf)
        keep = items_sorted[-1]
        for v in items_sorted[:-1]:
            if v.pk != keep.pk:
                v.delete()


class Migration(migrations.Migration):
    dependencies = [
        ('vehicles', '0003_vehicle_chassis_number_vehicle_plate_number'),
    ]

    operations = [
        migrations.RunPython(prune_duplicate_vehicles, migrations.RunPython.noop),
    ]

