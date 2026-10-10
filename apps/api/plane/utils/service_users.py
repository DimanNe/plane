# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
A service user stands for an agent: people assign work items to it, and nobody signs in as it.

It has to show wherever members are listed and chosen, so it is an ordinary user and not `is_bot`:
a bot is left out of the lists of members and of their counts. Its `bot_type` says what it is.

It has no password. Where a person has an e-mail address it has a value that is not an address:
every way to sign in asks for an address and refuses this value before it looks for a user.
"""

import email.utils as email_utils
import typing as t
import uuid

import django.core.mail.backends.smtp as smtp_backend
import django.core.mail.message as mail_message
import django.utils.text as text_utils

import plane.db.models as db_models
import plane.utils.permissions as permissions

# Not a domain that mail can be sent to: it has no dot, so no validation of an address accepts it.
EMAIL_SUFFIX: str = "@service-user"
# The address is the user name too, which is shorter than a name can be.
NAME_IN_ADDRESS_LENGTH: int = 64


def is_service_user_address(address: str) -> bool:
    return email_utils.parseaddr(address)[1].lower().endswith(EMAIL_SUFFIX)


def find_service_user(workspace_id: uuid.UUID, name: str) -> t.Optional[db_models.User]:
    """The service user of the workspace that has this name, whatever the case of its letters.
    A workspace has one per name, so one that was removed from the workspace is found too."""
    return db_models.User.objects.filter(
        bot_type=db_models.BotTypeEnum.SERVICE_USER,
        display_name__iexact=name,
        member_workspace__workspace_id=workspace_id,
    ).first()


def create_service_user(name: str) -> db_models.User:
    # The name leads, for the lists of members that show the address, and its first letter for a member
    # without a picture. Only letters, digits, "-" and "_" of the name: an address is read up to a comma or a space.
    name_in_address: str = text_utils.slugify(name, allow_unicode=True)[:NAME_IN_ADDRESS_LENGTH] or "service-user"
    address: str = f"{name_in_address}.{uuid.uuid4().hex}{EMAIL_SUFFIX}"
    user: db_models.User = db_models.User(
        username=address,
        email=address,
        display_name=name,
        first_name=name,
        bot_type=db_models.BotTypeEnum.SERVICE_USER,
    )
    user.set_unusable_password()
    user.save()
    # Saving a user makes preferences that ask for an e-mail about every change of its work items.
    preferences: t.Dict[str, bool] = dict.fromkeys(
        ("property_change", "state_change", "comment", "mention", "issue_completed"), False
    )
    db_models.UserNotificationPreference.objects.filter(user=user).update(**preferences)
    return user


def add_service_user_to_project(
    project: db_models.Project, name: str
) -> t.Tuple[db_models.WorkspaceMember, db_models.ProjectMember, bool]:
    """Find the service user of the project's workspace by its name, or create it, and make it a member of the
    workspace and of the project with the role of a member. The caller makes it one transaction.
    Returns the two memberships, and whether the user was created."""
    # Two requests for one name wait for each other here, so they do not make two users.
    db_models.Workspace.objects.select_for_update().get(pk=project.workspace_id)
    found: t.Optional[db_models.User] = find_service_user(project.workspace_id, name)
    user: db_models.User = found or create_service_user(name)
    role: int = permissions.ROLE.MEMBER.value
    workspace_member: db_models.WorkspaceMember
    workspace_member, _ = db_models.WorkspaceMember.objects.get_or_create(
        workspace_id=project.workspace_id, member=user, defaults={"role": role}
    )
    project_member: db_models.ProjectMember
    project_member, _ = db_models.ProjectMember.objects.get_or_create(
        project=project, member=user, defaults={"role": role}
    )
    membership: t.Union[db_models.WorkspaceMember, db_models.ProjectMember]
    for membership in (workspace_member, project_member):
        # removed from the workspace or from the project before, in the settings of its members
        if not membership.is_active:
            membership.is_active = True
            membership.save(update_fields=["is_active"])
    return workspace_member, project_member, found is None


class EmailBackend(smtp_backend.EmailBackend):
    """
    Sends by SMTP, and nothing to a service user.

    Every e-mail of Plane leaves through the backend of the settings, whatever writes it: a notification, the
    note that somebody was added to a project, or a part that does not exist yet. A service user has no mailbox.
    """

    def send_messages(self, email_messages: t.Sequence[mail_message.EmailMessage]) -> int:
        message: mail_message.EmailMessage
        for message in email_messages:
            field: str
            for field in ("to", "cc", "bcc"):
                setattr(
                    message,
                    field,
                    [address for address in getattr(message, field) if not is_service_user_address(address)],
                )
        return super().send_messages([message for message in email_messages if message.recipients()])
