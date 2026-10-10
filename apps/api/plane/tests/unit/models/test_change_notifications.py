# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import concurrent.futures
import json
import typing as t

import django.core.management.sql as management_sql
import django.db as django_db
import psycopg
import pytest
import redis.client

import plane.db.change_notifications as change_notifications
import plane.db.models as db_models
import plane.settings.redis as redis_settings

# The triggers notify at commit, so these tests commit.
pytestmark: t.List[pytest.MarkDecorator] = [pytest.mark.django_db(transaction=True), pytest.mark.unit]

Change: t.TypeAlias = t.Dict[str, t.Optional[str]]


@pytest.fixture
def project(workspace: db_models.Workspace) -> db_models.Project:
    return db_models.Project.objects.create(workspace=workspace, name="Followed", identifier="FO")


@pytest.fixture
def issue(project: db_models.Project) -> db_models.Issue:
    return db_models.Issue.objects.create(project=project, name="Work item")


@pytest.fixture
def listener(issue: db_models.Issue) -> t.Iterator[psycopg.Connection]:
    """A second connection that listens from now on: after the work item of the test was created."""
    connection: psycopg.Connection
    with psycopg.connect(**django_db.connection.get_connection_params(), autocommit=True) as connection:
        connection.execute(f"listen {change_notifications.POSTGRES_CHANNEL}")
        yield connection


def get_changes(listener: psycopg.Connection) -> t.List[Change]:
    return [json.loads(notification.payload) for notification in listener.notifies(timeout=0.3)]


def get_issue_change(issue: db_models.Issue, operation: str) -> Change:
    return {
        "t": "issues",
        "op": operation,
        "id": str(issue.id),
        "w": str(issue.workspace_id),
        "p": str(issue.project_id),
        "i": None,
    }


def end_listening_connections() -> None:
    cursor: django_db.backends.utils.CursorWrapper
    with django_db.connection.cursor() as cursor:
        cursor.execute(
            "select pg_terminate_backend(pid) from pg_stat_activity "
            "where datname = current_database() and query like 'listen %' and pid <> pg_backend_pid()"
        )


@pytest.fixture
def relay_and_messages() -> t.Iterator[t.Tuple[concurrent.futures.Future, redis.client.PubSub]]:
    """A running relay, and what it publishes from its start on."""
    messages: redis.client.PubSub = redis_settings.redis_instance().pubsub(ignore_subscribe_messages=True)
    messages.subscribe(change_notifications.REDIS_CHANNEL)
    messages.get_message(timeout=5)
    executor: concurrent.futures.ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor() as executor:
        yield executor.submit(change_notifications.relay_changes), messages
        end_listening_connections()
    messages.close()


def get_message(messages: redis.client.PubSub) -> str:
    return messages.get_message(timeout=5)["data"].decode()


@pytest.mark.parametrize(
    "write, operation",
    [
        (lambda issue: issue.save(), "U"),
        (lambda issue: db_models.Issue.objects.filter(pk=issue.pk).update(name="Renamed"), "U"),
        (lambda issue: db_models.Issue.objects.bulk_update([issue], ["name"]), "U"),
        # A delete is a soft delete, of one work item and of a query set
        (lambda issue: issue.delete(), "U"),
        (lambda issue: db_models.Issue.objects.filter(pk=issue.pk).delete(), "U"),
    ],
    ids=["save", "query set update", "bulk update", "soft delete", "query set soft delete"],
)
def test_every_way_of_writing_a_work_item_reports_it(
    issue: db_models.Issue,
    listener: psycopg.Connection,
    write: t.Callable[[db_models.Issue], t.Any],
    operation: str,
) -> None:
    write(issue)

    assert get_changes(listener) == [get_issue_change(issue, operation)]


def test_bulk_create_reports_every_row(project: db_models.Project, listener: psycopg.Connection) -> None:
    issues: t.List[db_models.Issue] = db_models.Issue.objects.bulk_create(
        [db_models.Issue(project=project, workspace=project.workspace, name=name) for name in ("One", "Two")]
    )

    assert get_changes(listener) == [get_issue_change(issue, "I") for issue in issues]


def test_row_of_a_work_item_names_the_work_item_when_inserted_and_when_deleted(
    issue: db_models.Issue, create_user: db_models.User, listener: psycopg.Connection
) -> None:
    assignee: db_models.IssueAssignee = db_models.IssueAssignee.objects.create(
        issue=issue, assignee=create_user, project=issue.project
    )
    change: Change = {
        "t": "issue_assignees",
        "id": str(assignee.id),
        "w": str(issue.workspace_id),
        "p": str(issue.project_id),
        "i": str(issue.id),
    }

    assignee.delete(soft=False)

    assert get_changes(listener) == [{**change, "op": "I"}, {**change, "op": "D"}]


def test_table_added_later_reports_after_the_next_migrate(
    workspace: db_models.Workspace, listener: psycopg.Connection
) -> None:
    cursor: django_db.backends.utils.CursorWrapper
    with django_db.connection.cursor() as cursor:
        cursor.execute("create table added_later (id integer, workspace_id uuid)")
        try:
            management_sql.emit_post_migrate_signal(verbosity=0, interactive=False, db=django_db.DEFAULT_DB_ALIAS)
            cursor.execute("insert into added_later values (7, %s)", [workspace.id])

            assert get_changes(listener) == [
                {"t": "added_later", "op": "I", "id": "7", "w": str(workspace.id), "p": None, "i": None}
            ]
        finally:
            cursor.execute("drop table added_later")


def test_relay_first_tells_the_pages_to_fetch_again(
    relay_and_messages: t.Tuple[concurrent.futures.Future, redis.client.PubSub],
) -> None:
    assert get_message(relay_and_messages[1]) == change_notifications.RESYNC_MESSAGE


def test_relay_passes_a_change_on_to_redis(
    issue: db_models.Issue, relay_and_messages: t.Tuple[concurrent.futures.Future, redis.client.PubSub]
) -> None:
    messages: redis.client.PubSub = relay_and_messages[1]
    get_message(messages)

    db_models.Issue.objects.filter(pk=issue.pk).update(name="Renamed")

    assert json.loads(get_message(messages)) == get_issue_change(issue, "U")


def test_relay_ends_with_its_database_connection(
    relay_and_messages: t.Tuple[concurrent.futures.Future, redis.client.PubSub],
) -> None:
    relay: concurrent.futures.Future = relay_and_messages[0]
    get_message(relay_and_messages[1])

    end_listening_connections()

    assert isinstance(relay.exception(timeout=5), psycopg.OperationalError)
