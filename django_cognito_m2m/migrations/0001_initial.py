from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ServiceClientActivity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("client_id", models.CharField(db_index=True, max_length=255, unique=True)),
                ("first_seen_at", models.DateTimeField()),
                ("last_seen_at", models.DateTimeField(db_index=True)),
            ],
            options={
                "verbose_name": "service client activity",
                "verbose_name_plural": "service client activity",
                "ordering": ["client_id"],
            },
        ),
    ]
