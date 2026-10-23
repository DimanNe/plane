# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import typing as t

from django.db import models


def prevent_lost_update(instance: models.Model, saved_field_names: t.Iterable[str]) -> None:
    """Two saves of one row can be on their way at once, such as the autosaves of a work item's title and of its
    description. Each request loaded the row before the other one saved it, and saving the row whole would put
    back what the other stored meanwhile: a lost update. Locks the row until the save's transaction ends, and
    reads again every field that this save does not set. Call it in that transaction, before the instance is read.
    """
    saved_field_names = set(saved_field_names)
    manager = type(instance)._base_manager
    list(manager.select_for_update().filter(pk=instance.pk).values_list("pk", flat=True))
    instance.refresh_from_db(
        fields=[
            field.name
            for field in instance._meta.concrete_fields
            if not field.primary_key and field.name not in saved_field_names and field.attname not in saved_field_names
        ]
    )
    # A model that tracks its changes (plane.db.mixins.ChangeTrackerMixin) compares with what it loaded, which the
    # read has just replaced.
    if hasattr(instance, "_track_fields"):
        instance._track_fields()
