from django.db.models import Count
from licenses.models import License

duplicates = License.objects.values('owner_id','license_type').annotate(cnt=Count('id')).filter(cnt__gt=1)
print('Duplicate groups:', list(duplicates))
removed = []
for dup in duplicates:
    owner = dup['owner_id']
    ltype = dup['license_type']
    qs = License.objects.filter(owner_id=owner, license_type=ltype).order_by('id')
    keep = qs.first()
    extras = qs.exclude(pk=keep.pk)
    for e in list(extras):
        removed.append((e.id, owner, ltype))
        e.delete()

print('Removed records:', removed)
