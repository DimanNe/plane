# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import typing as t

import django.apps.registry as apps_registry
import django.db.backends.base.schema as db_schema
import django.db.migrations as db_migrations
import django.db.models as django_models

DEPENDENCY_TYPES: t.Tuple[str, ...] = ("blocked_by", "start_before", "finish_before")


def link_dependencies_without_days(
    apps: apps_registry.Apps, schema_editor: t.Optional[db_schema.BaseDatabaseSchemaEditor]
) -> None:
    """Until now a dependency with a delay of 0 kept its two work items together on the timeline. That is what
    linked means from here on, and linked is stored as no delay."""
    relation_model: t.Type[django_models.Model] = apps.get_model("db", "IssueRelation")
    relation_model._base_manager.filter(relation_type__in=DEPENDENCY_TYPES, delay=0).update(delay=None)


def give_linked_dependencies_no_days(
    apps: apps_registry.Apps, schema_editor: t.Optional[db_schema.BaseDatabaseSchemaEditor]
) -> None:
    relation_model: t.Type[django_models.Model] = apps.get_model("db", "IssueRelation")
    relation_model._base_manager.filter(delay=None).update(delay=0)


class Migration(db_migrations.Migration):
    dependencies = [
        ("db", "0127_timeline_delay_and_fixed_start"),
    ]

    operations = [
        db_migrations.AlterField(
            model_name="issuerelation",
            name="delay",
            field=django_models.PositiveIntegerField(blank=True, default=0, null=True),
        ),
        db_migrations.RunPython(link_dependencies_without_days, give_linked_dependencies_no_days),
    ]
