# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import plane.api.views.base as base_views
import plane.app.views.milestone as milestone_views


class MilestoneAPIViewSet(milestone_views.MilestoneViewSetMixin, base_views.BaseViewSet):
    pass
