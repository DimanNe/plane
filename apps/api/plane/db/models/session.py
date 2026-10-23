# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import datetime
import string

# Django imports
from django.contrib.sessions.backends.db import SessionStore as DBSessionStore
from django.contrib.sessions.base_session import AbstractBaseSession
from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string

VALID_KEY_CHARS = string.ascii_lowercase + string.digits


class Session(AbstractBaseSession):
    device_info = models.JSONField(null=True, blank=True, default=None)
    session_key = models.CharField(max_length=128, primary_key=True)
    user_id = models.CharField(null=True, max_length=50, db_index=True)

    @classmethod
    def get_session_store_class(cls):
        return SessionStore

    class Meta(AbstractBaseSession.Meta):
        db_table = "sessions"


class SessionStore(DBSessionStore):
    @classmethod
    def get_model_class(cls):
        return Session

    def load(self):
        """
        Renews the expiry of a session in use, so that a person stays signed in while they use Plane, however long
        ago they signed in. Only an expiry that is a while old is renewed: saving the session on every request
        (SESSION_SAVE_EVERY_REQUEST) would add a write to the database to each request. The session middleware
        saves a session marked modified and sends its cookie again, with the renewed expiry.
        """
        EXPIRY_RENEWAL_INTERVAL = datetime.timedelta(days=1)
        session = self._get_session_from_db()
        if session is None:
            return {}
        session_data = self.decode(session.session_data)
        expiry_age = datetime.timedelta(seconds=self.get_expiry_age(expiry=session_data.get("_session_expiry")))
        if session.expire_date - timezone.now() < expiry_age - EXPIRY_RENEWAL_INTERVAL:
            self.modified = True
        return session_data

    def _get_new_session_key(self):
        """
        Return a new session key that is not present in the current backend.
        Override this method to use a custom session key generation mechanism.
        """
        while True:
            session_key = get_random_string(128, VALID_KEY_CHARS)
            if not self.exists(session_key):
                return session_key

    def create_model_instance(self, data):
        obj = super().create_model_instance(data)
        try:
            user_id = data.get("_auth_user_id")
        except (ValueError, TypeError):
            user_id = None
        obj.user_id = user_id

        # Save the device info
        device_info = data.get("device_info")
        obj.device_info = device_info if isinstance(device_info, dict) else None
        return obj
