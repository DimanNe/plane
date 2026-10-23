# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import dataclasses as dc
import datetime
import typing as t

import django.conf as conf
import django.db.models as django_models
import pytest

import plane.db.models.session as session_models

pytestmark: t.List[pytest.MarkDecorator] = [pytest.mark.django_db, pytest.mark.unit]


@dc.dataclass(frozen=True)
class Tc:
    name: str
    # how long ago the expiry of the session was set, when it was made or last renewed
    expiry_set_ago: datetime.timedelta
    # the session's own expiry, as an administrator's session has one; None for the expiry of every session
    own_expiry_seconds: t.Optional[int]
    # what loading the session gives, and whether it is then marked to be saved with a renewed expiry
    expected: t.Tuple[t.Dict[str, t.Any], bool]


def test_session_store_load_renews_expiry_only_once_it_is_a_while_old() -> None:
    session_age: datetime.timedelta = datetime.timedelta(seconds=conf.settings.SESSION_COOKIE_AGE)
    tcs: t.List[Tc] = [
        Tc("just made", datetime.timedelta(0), None, ({"kept": "value"}, False)),
        Tc("renewed an hour ago", datetime.timedelta(hours=1), None, ({"kept": "value"}, False)),
        Tc("renewed two days ago", datetime.timedelta(days=2), None, ({"kept": "value"}, True)),
        Tc(
            "an administrator's session of an hour, made half an hour ago",
            datetime.timedelta(minutes=30),
            3600,
            ({"kept": "value", "_session_expiry": 3600}, False),
        ),
        Tc("expired", session_age + datetime.timedelta(days=1), None, ({}, False)),
    ]
    for i, tc in enumerate(tcs):
        made: session_models.SessionStore = session_models.SessionStore()
        made["kept"] = "value"
        if tc.own_expiry_seconds is not None:
            made.set_expiry(tc.own_expiry_seconds)
        made.save(must_create=True)
        session_models.Session.objects.filter(session_key=made.session_key).update(
            expire_date=django_models.F("expire_date") - tc.expiry_set_ago
        )

        loaded: session_models.SessionStore = session_models.SessionStore(made.session_key)
        actual: t.Tuple[t.Dict[str, t.Any], bool] = (loaded.load(), loaded.modified)
        assert actual == tc.expected, f"Testcase #{i + 1} {tc.name}"
