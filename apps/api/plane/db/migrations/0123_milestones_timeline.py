import django.db.migrations
import django.db.models
import django.db.models.deletion
import uuid
import django.conf


class Migration(django.db.migrations.Migration):
    dependencies = [("db", "0122_alter_draftissue_assignees_alter_issue_assignees_and_more")]
    operations = [
        django.db.migrations.AddField(
            model_name="project", name="milestone_view", field=django.db.models.BooleanField(default=False)
        ),
        django.db.migrations.CreateModel(
            name="Milestone",
            fields=[
                (
                    "id",
                    django.db.models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        unique=True,
                        db_index=True,
                    ),
                ),
                ("created_at", django.db.models.DateTimeField(auto_now_add=True, verbose_name="Created At")),
                ("updated_at", django.db.models.DateTimeField(auto_now=True, verbose_name="Last Modified At")),
                ("deleted_at", django.db.models.DateTimeField(null=True, blank=True, verbose_name="Deleted At")),
                ("title", django.db.models.CharField(max_length=255)),
                ("description_html", django.db.models.TextField(blank=True, default="<p></p>")),
                ("target_date", django.db.models.DateField(null=True, blank=True)),
                ("external_source", django.db.models.CharField(max_length=255, null=True, blank=True)),
                ("external_id", django.db.models.CharField(max_length=255, null=True, blank=True)),
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
                        on_delete=django.db.models.deletion.CASCADE,
                        to="db.workspace",
                        related_name="workspace_%(class)s",
                    ),
                ),
                (
                    "project",
                    django.db.models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="db.project", related_name="project_%(class)s"
                    ),
                ),
            ],
            options={
                "verbose_name": "Milestone",
                "verbose_name_plural": "Milestones",
                "db_table": "milestones",
                "ordering": ("-created_at",),
            },
        ),
        django.db.migrations.AddConstraint(
            model_name="milestone",
            constraint=django.db.models.UniqueConstraint(
                fields=("project", "title"),
                condition=django.db.models.Q(deleted_at__isnull=True),
                name="milestone_unique_project_title_when_deleted_at_null",
            ),
        ),
        django.db.migrations.AddField(
            model_name="issue",
            name="milestone",
            field=django.db.models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="issues",
                to="db.milestone",
            ),
        ),
        django.db.migrations.AddField(
            model_name="issueversion", name="milestone", field=django.db.models.UUIDField(null=True, blank=True)
        ),
    ]
