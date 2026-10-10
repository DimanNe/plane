# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
Tells open pages which records changed, whoever changed them.

A trigger on every table of workspace data reports each changed row with NOTIFY: the table, the
kind of change and the ids of the row, never its content. A thread of the API passes these on to
a Redis channel; the live server sends them to the browsers, which fetch what they show.
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

# to_jsonb makes the row readable by column name, so one function serves every table. A soft
# delete is an update like any other.
TRIGGER_FUNCTION: str = f"""
create or replace function plane_notify_row_change() returns trigger language plpgsql as $$
declare
    r jsonb := to_jsonb(case when tg_op = 'DELETE' then old else new end);
begin
    perform pg_notify('{POSTGRES_CHANNEL}', json_build_object(
        't', tg_table_name, 'op', left(tg_op, 1), 'id', r->>'id',
        'w', r->>'workspace_id', 'p', r->>'project_id', 'i', r->>'issue_id')::text);
    return null;
end $$
"""
TABLES_OF_WORKSPACE_DATA: str = """
select table_name from information_schema.columns join information_schema.tables using (table_schema, table_name)
where table_schema = current_schema() and table_type = 'BASE TABLE' and column_name = 'workspace_id'
"""

logger: logging.Logger = logging.getLogger("plane.api")


def install_triggers(using: str, **kwargs: t.Any) -> None:
    """
    Receives post_migrate, so a table that a later migration adds gets its trigger with it.
    """
    connection: django_db_base.BaseDatabaseWrapper = django_db.connections[using]
    cursor: django_db_utils.CursorWrapper
    with connection.cursor() as cursor:
        cursor.execute(TRIGGER_FUNCTION)
        cursor.execute(TABLES_OF_WORKSPACE_DATA)
        table: str
        for (table,) in cursor.fetchall():
            cursor.execute(
                f"create or replace trigger plane_notify_row_change after insert or update or delete "
                f"on {connection.ops.quote_name(table)} for each row execute function plane_notify_row_change()"
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
