"""
Per-guild settings storage.

Everything the bot needs to remember about a server (welcome/goodbye
channels + messages, logging channel + which events to log) lives in one
SQLite file at data/settings.sqlite3. SQLite is plenty for this: one bot
process, mostly-read traffic, and no external database to stand up —
which matters if this bot is going to be invited to lots of servers you
don't personally administer.

Every column has a sensible default, so a guild that has never touched
/settings still gets working (if generic) welcome/goodbye messages —
same idea as ProBot's out-of-the-box behavior.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Optional

import aiosqlite

DB_PATH = "data/settings.sqlite3"

# The full set of loggable event categories. Keys here are what gets
# stored (comma-separated) in the log_events column, and what the
# settings UI's multi-select presents as choices.
LOG_EVENT_CHOICES: dict[str, str] = {
    "message_delete": "Message deleted",
    "message_edit": "Message edited",
    "member_join": "Member joined",
    "member_leave": "Member left / was kicked",
    "member_ban": "Member banned / unbanned",
    "nickname_change": "Nickname changed",
    "role_change": "Member roles changed",
    "channel_create": "Channel created",
    "channel_delete": "Channel deleted",
}

DEFAULT_LOG_EVENTS = ",".join(LOG_EVENT_CHOICES.keys())  # all on by default

DEFAULT_WELCOME_MESSAGE = (
    "Welcome to **{server}**, {mention}! You're member #{member_count}."
)
DEFAULT_GOODBYE_MESSAGE = "**{name}** just left {server}. We're now at {member_count} members."

SCHEMA = """
CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id            INTEGER PRIMARY KEY,
    welcome_enabled      INTEGER NOT NULL DEFAULT 0,
    welcome_channel_id   INTEGER,
    welcome_message      TEXT NOT NULL DEFAULT '{default_welcome}',
    goodbye_enabled      INTEGER NOT NULL DEFAULT 0,
    goodbye_channel_id   INTEGER,
    goodbye_message      TEXT NOT NULL DEFAULT '{default_goodbye}',
    logging_enabled      INTEGER NOT NULL DEFAULT 0,
    log_channel_id       INTEGER,
    log_events           TEXT NOT NULL DEFAULT '{default_events}'
);
""".format(
    default_welcome=DEFAULT_WELCOME_MESSAGE.replace("'", "''"),
    default_goodbye=DEFAULT_GOODBYE_MESSAGE.replace("'", "''"),
    default_events=DEFAULT_LOG_EVENTS,
)


@dataclass
class GuildSettings:
    guild_id: int
    welcome_enabled: bool = False
    welcome_channel_id: Optional[int] = None
    welcome_message: str = DEFAULT_WELCOME_MESSAGE
    goodbye_enabled: bool = False
    goodbye_channel_id: Optional[int] = None
    goodbye_message: str = DEFAULT_GOODBYE_MESSAGE
    logging_enabled: bool = False
    log_channel_id: Optional[int] = None
    log_events: set[str] = field(default_factory=lambda: set(LOG_EVENT_CHOICES.keys()))

    @classmethod
    def from_row(cls, row: aiosqlite.Row) -> "GuildSettings":
        events = row["log_events"].split(",") if row["log_events"] else []
        return cls(
            guild_id=row["guild_id"],
            welcome_enabled=bool(row["welcome_enabled"]),
            welcome_channel_id=row["welcome_channel_id"],
            welcome_message=row["welcome_message"],
            goodbye_enabled=bool(row["goodbye_enabled"]),
            goodbye_channel_id=row["goodbye_channel_id"],
            goodbye_message=row["goodbye_message"],
            logging_enabled=bool(row["logging_enabled"]),
            log_channel_id=row["log_channel_id"],
            log_events=set(e for e in events if e),
        )


class Database:
    """Thin async wrapper around the guild_settings table.

    One instance lives on the bot (bot.db) and is shared by every cog.
    A lock serializes writes so two settings changes firing at once
    (e.g. two admins clicking buttons at the same moment) can't race.
    """

    def __init__(self, path: str = DB_PATH):
        self.path = path
        self._lock = asyncio.Lock()

    async def setup(self) -> None:
        # A fresh clone from git won't have data/ at all — git doesn't
        # track empty directories, and the sqlite file itself is
        # gitignored — so create it rather than crashing on first run.
        parent = os.path.dirname(self.path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        async with aiosqlite.connect(self.path) as db:
            await db.execute(SCHEMA)
            await db.commit()

    async def get_settings(self, guild_id: int) -> GuildSettings:
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM guild_settings WHERE guild_id = ?", (guild_id,)
            )
            row = await cur.fetchone()
            if row is None:
                # First time we've seen this guild — create its row with
                # defaults so later reads/writes are simple updates.
                await db.execute(
                    "INSERT INTO guild_settings (guild_id) VALUES (?)", (guild_id,)
                )
                await db.commit()
                cur = await db.execute(
                    "SELECT * FROM guild_settings WHERE guild_id = ?", (guild_id,)
                )
                row = await cur.fetchone()
            return GuildSettings.from_row(row)

    async def _update(self, guild_id: int, **fields) -> None:
        if not fields:
            return
        # Make sure the row exists before UPDATEing it.
        await self.get_settings(guild_id)
        columns = ", ".join(f"{key} = ?" for key in fields)
        values = list(fields.values()) + [guild_id]
        async with self._lock:
            async with aiosqlite.connect(self.path) as db:
                await db.execute(
                    f"UPDATE guild_settings SET {columns} WHERE guild_id = ?",
                    values,
                )
                await db.commit()

    async def set_welcome(
        self,
        guild_id: int,
        *,
        enabled: Optional[bool] = None,
        channel_id: Optional[int] = None,
        message: Optional[str] = None,
    ) -> None:
        fields = {}
        if enabled is not None:
            fields["welcome_enabled"] = int(enabled)
        if channel_id is not None:
            fields["welcome_channel_id"] = channel_id
        if message is not None:
            fields["welcome_message"] = message
        await self._update(guild_id, **fields)

    async def set_goodbye(
        self,
        guild_id: int,
        *,
        enabled: Optional[bool] = None,
        channel_id: Optional[int] = None,
        message: Optional[str] = None,
    ) -> None:
        fields = {}
        if enabled is not None:
            fields["goodbye_enabled"] = int(enabled)
        if channel_id is not None:
            fields["goodbye_channel_id"] = channel_id
        if message is not None:
            fields["goodbye_message"] = message
        await self._update(guild_id, **fields)

    async def set_logging_channel(self, guild_id: int, channel_id: int) -> None:
        await self._update(guild_id, logging_enabled=1, log_channel_id=channel_id)

    async def set_logging_enabled(self, guild_id: int, enabled: bool) -> None:
        await self._update(guild_id, logging_enabled=int(enabled))

    async def set_log_events(self, guild_id: int, events: set[str]) -> None:
        await self._update(guild_id, log_events=",".join(sorted(events)))
