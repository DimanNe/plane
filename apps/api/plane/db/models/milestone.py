# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import django.db.models as django_models

import plane.db.models.project as project_models


class Milestone(project_models.ProjectBaseModel):
    title = django_models.CharField(max_length=255)
    description_html = django_models.TextField(blank=True, default="<p></p>")
    target_date = django_models.DateField(null=True, blank=True)
    external_source = django_models.CharField(max_length=255, null=True, blank=True)
    external_id = django_models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        constraints = [
            django_models.UniqueConstraint(
                fields=["project", "title"],
                condition=django_models.Q(deleted_at__isnull=True),
                name="milestone_unique_project_title_when_deleted_at_null",
            )
        ]
        verbose_name = "Milestone"
        verbose_name_plural = "Milestones"
        db_table = "milestones"
        ordering = ("-created_at",)
