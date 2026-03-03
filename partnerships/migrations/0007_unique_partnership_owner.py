from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partnerships', '0007_prune_duplicates'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='partnership',
            constraint=models.UniqueConstraint(fields=('owner',), name='unique_partnership_per_owner'),
        ),
    ]
