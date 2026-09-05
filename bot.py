"""
Entry point. Run with:  python bot.py

Loads the database + every cog, syncs slash commands, and logs in.
See README.md for how to get a token and invite link.
"""

from __future__ import annotations

import logging
import os

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from utils.database import Database

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("himyar-bot")

TOKEN = os.getenv("DISCORD_TOKEN")
DEV_GUILD_ID = os.getenv("DEV_GUILD_ID") or None

INITIAL_EXTENSIONS = [
    "cogs.settings",
    "cogs.welcome",
    "cogs.logging_events",
]


class HimyarBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True  # required: join/leave events, role/nick updates
        intents.message_content = True  # required: meaningful edit/delete logs
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            help_command=None,
        )
        self.db = Database()

    async def setup_hook(self):
        await self.db.setup()

        for extension in INITIAL_EXTENSIONS:
            await self.load_extension(extension)

        self.tree.on_error = self.on_app_command_error

        if DEV_GUILD_ID:
            guild = discord.Object(id=int(DEV_GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("Synced commands to dev guild %s (instant)", DEV_GUILD_ID)
        else:
            await self.tree.sync()
            log.info("Synced global commands (can take up to an hour to appear everywhere)")

    async def on_ready(self):
        log.info(
            "Logged in as %s (id=%s) — in %d server(s)",
            self.user,
            self.user.id if self.user else "?",
            len(self.guilds),
        )
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name="/settings")
        )

    async def on_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        if isinstance(error, app_commands.MissingPermissions):
            message = "You need the **Manage Server** permission to use this."
        elif isinstance(error, app_commands.NoPrivateMessage):
            message = "This command only works inside a server."
        else:
            message = "Something went wrong running that command."
            log.exception("Unhandled app command error", exc_info=error)

        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


def main():
    if not TOKEN:
        raise SystemExit(
            "DISCORD_TOKEN is not set. Copy .env.example to .env and paste your bot token in."
        )
    bot = HimyarBot()
    bot.run(TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
