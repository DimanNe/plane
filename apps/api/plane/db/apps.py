# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.apps import AppConfig
from django.db.models.signals import post_migrate

from plane.db.change_notifications import install_triggers


class DbConfig(AppConfig):
    name = "plane.db"

    def ready(self):
        post_migrate.connect(install_triggers, sender=self)
