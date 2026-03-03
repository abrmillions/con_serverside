from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vehicles', '0004_prune_duplicates'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='vehicle',
            constraint=models.UniqueConstraint(fields=('owner',), name='unique_vehicle_per_owner'),
        ),
    ]
