# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import plane.api.views.base as base_views
import plane.app.views.page.wiki as wiki_views


class PageAPIViewSet(wiki_views.PageViewSetMixin, base_views.BaseViewSet):
    writes_bypass_editor: bool = True


class CollectionAPIViewSet(wiki_views.CollectionViewSetMixin, base_views.BaseViewSet):
    pass
