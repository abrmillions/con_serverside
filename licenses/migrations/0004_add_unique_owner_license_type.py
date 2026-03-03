from django.db import migrations, models


def remove_duplicate_owner_type_records(apps, schema_editor):
    License = apps.get_model('licenses', 'License')
    from django.db.models import Count

    # Find owner+license_type combinations having more than one record
    duplicates = (
        License.objects.values('owner_id', 'license_type')
        .annotate(c=Count('id'))
        .filter(c__gt=1)
    )

    for dup in duplicates:
        owner_id = dup['owner_id']
        ltype = dup['license_type']
        # Keep the earliest created (smallest id) and remove others
        q = License.objects.filter(owner_id=owner_id, license_type=ltype).order_by('id')
        keep = q.first()
        to_delete = q.exclude(pk=keep.pk)
        # Delete duplicates
        to_delete.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('licenses', '0003_license_expiry_date_license_issued_by_and_more'),
    ]

    operations = [
        migrations.RunPython(remove_duplicate_owner_type_records, reverse_code=migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='license',
            constraint=models.UniqueConstraint(fields=['owner', 'license_type'], name='unique_owner_license_type'),
        ),
    ]
