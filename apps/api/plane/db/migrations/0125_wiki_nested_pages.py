import uuid

import django.conf
import django.db.migrations
import django.db.models
import django.db.models.deletion


class Migration(django.db.migrations.Migration):
    dependencies = [("db", "0124_custom_properties")]
    operations = [
        django.db.migrations.AddField(
            model_name="workspace", name="is_wiki_enabled", field=django.db.models.BooleanField(default=True)
        ),
        django.db.migrations.CreateModel(
            name="Collection",
            fields=[
                ("created_at", django.db.models.DateTimeField(auto_now_add=True, verbose_name="Created At")),
                ("updated_at", django.db.models.DateTimeField(auto_now=True, verbose_name="Last Modified At")),
                ("deleted_at", django.db.models.DateTimeField(blank=True, null=True, verbose_name="Deleted At")),
                (
                    "id",
                    django.db.models.UUIDField(
                        db_index=True,
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        unique=True,
                    ),
                ),
                ("name", django.db.models.CharField(max_length=255)),
                (
                    "access",
                    django.db.models.PositiveSmallIntegerField(choices=[(1, "Private"), (0, "Public")], default=0),
                ),
                ("logo_props", django.db.models.JSONField(default=dict)),
                ("sort_order", django.db.models.FloatField(default=65535)),
                ("is_default", django.db.models.BooleanField(default=False)),
                (
                    "created_by",
                    django.db.models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created_by",
                        to=django.conf.settings.AUTH_USER_MODEL,
                        verbose_name="Created By",
                    ),
                ),
                (
                    "owned_by",
                    django.db.models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="collections",
                        to=django.conf.settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "updated_by",
                    django.db.models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_updated_by",
                        to=django.conf.settings.AUTH_USER_MODEL,
                        verbose_name="Last Modified By",
                    ),
                ),
                (
                    "workspace",
                    django.db.models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="collections", to="db.workspace"
                    ),
                ),
            ],
            options={
                "verbose_name": "Collection",
                "verbose_name_plural": "Collections",
                "db_table": "collections",
                "ordering": ("sort_order", "created_at"),
            },
        ),
        django.db.migrations.AddField(
            model_name="page",
            name="collection",
            field=django.db.models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="pages",
                to="db.collection",
            ),
        ),
        django.db.migrations.AddConstraint(
            model_name="collection",
            constraint=django.db.models.UniqueConstraint(
                condition=django.db.models.Q(("deleted_at__isnull", True), ("is_default", True)),
                fields=("workspace",),
                name="collection_unique_default_per_workspace",
            ),
        ),
    ]
