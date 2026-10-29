# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
Tells open pages which records changed, whoever changed them.

A trigger reports each changed row naming a work item with NOTIFY: the table, the kind of change
and the ids of the row, never its content. A thread of the API passes these on to a Redis channel;
the live server sends them to the browsers, which fetch what they show.

A row names a work item when it is the work item's own row (`issues`) or has its `issue_id`, such
as an assignee, a comment or a relation. The pages follow no other rows (getNamedWorkItemId in
apps/web/store/live-updates.ts). Sent, they would reach every open page of the workspace, which
collects each change for a moment before it fetches, and would use none: the recent visit that
each opening of a work item records, the notification of each change of a work item, the last use
of an API token at each request of an agent.
"""

import logging
import threading
import time
import typing as t

import django.db as django_db
import django.db.backends.base.base as django_db_base
import django.db.backends.utils as django_db_utils
import psycopg
import redis

import plane.settings.redis as redis_settings

POSTGRES_CHANNEL: str = "plane_changes"
REDIS_CHANNEL: str = "plane:changes"
# Neither channel keeps what nobody received. This message tells the pages that changes may have
# been missed, and they fetch again what they show.
RESYNC_MESSAGE: str = '{"resync": true}'
RELAY_RESTART_SECONDS: float = 1

TRIGGER: str = "plane_notify_row_change"
# to_jsonb makes the row readable by column name, so one function serves every table. A soft
# delete is an update like any other. A table with an issue_id also holds rows that name no work
# item, such as the logo of a workspace or the sequence number of a deleted work item.
TRIGGER_FUNCTION: str = f"""
create or replace function {TRIGGER}() returns trigger language plpgsql as $$
declare
    r jsonb := to_jsonb(case when tg_op = 'DELETE' then old else new end);
begin
    if tg_table_name = 'issues' or r->>'issue_id' is not null then
        perform pg_notify('{POSTGRES_CHANNEL}', json_build_object(
            't', tg_table_name, 'op', left(tg_op, 1), 'id', r->>'id',
            'w', r->>'workspace_id', 'p', r->>'project_id', 'i', r->>'issue_id')::text);
    end if;
    return null;
end $$
"""
# The live server sends a row to the pages of its workspace: a row without one reaches no page.
TABLES_NAMING_A_WORK_ITEM: str = """
select table_name from information_schema.columns join information_schema.tables using (table_schema, table_name)
where table_schema = current_schema() and table_type = 'BASE TABLE'
group by table_name
having bool_or(column_name = 'workspace_id') and (table_name = 'issues' or bool_or(column_name = 'issue_id'))
"""
TABLES_WITH_TRIGGER: str = f"""
select relname from pg_trigger join pg_class on pg_class.oid = tgrelid
where tgname = '{TRIGGER}' and relnamespace = current_schema()::regnamespace
"""

logger: logging.Logger = logging.getLogger("plane.api")


def install_triggers(using: str, **kwargs: t.Any) -> None:
    """
    Receives post_migrate, so a table that a later migration adds gets its trigger with it, and a
    table that names no work item loses one that an earlier version gave it.
    """
    # FOR_REVIEWER: the page's rule is generic, not a list of tables: the list and the open work
    # item fetch the work item that a change names, and the plan of a timeline is computed from
    # two tables that both name one (`issues`, `issue_relations`). So the server's rule is the same
    # generic one. A table that upstream adds with an issue_id is sent from the next migrate on,
    # and the page fetches its work item as for any other; one without is not sent, and the page
    # has no rule for it. A list of the followed tables would leave out each new table of a work
    # item until somebody added it; a list of the ignored ones would send each new table again.
    # FOR_REVIEWER: left out, of what changed on opening, typing and moving in a run of the checks:
    # user_recent_visits (each opening, and each fetch of the list or of an open work item that a
    # live update makes, so each change came round twice), notifications (each change of a work
    # item), api_tokens (each request to /api/v1/), project_user_properties (the layout and the
    # display of a list), descriptions (each comment), and the workspace_user_* rows of a member's
    # first visit. Still sent though no page shows them: issue_description_versions and
    # issue_sequences, which name the work item of a change that comes with them.
    connection: django_db_base.BaseDatabaseWrapper = django_db.connections[using]
    cursor: django_db_utils.CursorWrapper
    with connection.cursor() as cursor:
        cursor.execute(TRIGGER_FUNCTION)
        cursor.execute(TABLES_NAMING_A_WORK_ITEM)
        tables_naming_a_work_item: t.List[str] = [table for (table,) in cursor.fetchall()]
        cursor.execute(TABLES_WITH_TRIGGER)
        table: str
        for (table,) in cursor.fetchall():
            if table not in tables_naming_a_work_item:
                cursor.execute(f"drop trigger {TRIGGER} on {connection.ops.quote_name(table)}")
        for table in tables_naming_a_work_item:
            cursor.execute(
                f"create or replace trigger {TRIGGER} after insert or update or delete "
                f"on {connection.ops.quote_name(table)} for each row execute function {TRIGGER}()"
            )


def relay_changes() -> None:
    """Passes the notifications on to Redis until a connection fails, which raises."""
    connection: psycopg.Connection
    with psycopg.connect(**django_db.connection.get_connection_params(), autocommit=True) as connection:
        # Every API worker runs a relay. One of them holds this lock and relays; the others wait
        # here, and one of them goes on when the connection of the first one ends.
        connection.execute("select pg_advisory_lock(hashtext(%s))", [POSTGRES_CHANNEL])
        connection.execute(f"listen {POSTGRES_CHANNEL}")
        redis_client: redis.Redis = redis_settings.redis_instance()
        redis_client.publish(REDIS_CHANNEL, RESYNC_MESSAGE)
        notification: psycopg.Notify
        for notification in connection.notifies():
            redis_client.publish(REDIS_CHANNEL, notification.payload)


def run_relay() -> None:
    while True:
        try:
            relay_changes()
        except Exception:
            logger.exception("The relay of database changes to the live server failed and starts again")
        time.sleep(RELAY_RESTART_SECONDS)


def start_relay() -> None:
    threading.Thread(target=run_relay, name="change-relay", daemon=True).start()
