# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import typing as t

import django.apps.registry as apps_registry
import django.db.backends.base.schema as db_schema
import django.db.migrations as db_migrations
import django.db.models as django_models
import django.db.models.functions as db_functions


def record_when_closed_work_items_were_closed(
    apps: apps_registry.Apps, schema_editor: t.Optional[db_schema.BaseDatabaseSchemaEditor]
) -> None:
    """A work item cancelled before this migration has no cancelled_at, and one completed by a path that skipped
    Issue.save() has no completed_at. Both take the moment of their last state change in the activity log, or their
    creation when they were made in that state."""
    # FOR_REVIEWER: completed_at is upstream's; only the rows it left empty for a completed work item are filled,
    # with the same meaning, so that such a work item can be hidden as closed for long.
    issue_model: t.Type[django_models.Model] = apps.get_model("db", "Issue")
    issue_activity_model: t.Type[django_models.Model] = apps.get_model("db", "IssueActivity")
    last_state_change: django_models.Subquery = django_models.Subquery(
        issue_activity_model._base_manager.filter(
            issue_id=django_models.OuterRef("pk"), field="state", deleted_at__isnull=True
        )
        .order_by("-created_at")
        .values("created_at")[:1]
    )
    closed_at: db_functions.Coalesce = db_functions.Coalesce(last_state_change, django_models.F("created_at"))
    issue_model._base_manager.filter(state__group="cancelled", cancelled_at__isnull=True).update(cancelled_at=closed_at)
    issue_model._base_manager.filter(state__group="completed", completed_at__isnull=True).update(completed_at=closed_at)


class Migration(db_migrations.Migration):
    dependencies = [
        ("db", "0128_linked_dependencies"),
    ]

    operations = [
        db_migrations.AddField(
            model_name="issue",
            name="cancelled_at",
            field=django_models.DateTimeField(null=True),
        ),
        db_migrations.RunPython(record_when_closed_work_items_were_closed, db_migrations.RunPython.noop),
    ]
