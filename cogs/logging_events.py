"""
Server activity logs — message edits/deletes, joins/leaves, bans,
nickname and role changes, channel create/delete.

Every event checks the same three things before it does anything:
1. Is logging turned on for this guild at all?
2. Is a log channel actually set (and does it still exist)?
3. Did the admin choose to log *this* event type in /settings?

That gating all lives in `_get_log_channel`, so adding a new loggable
event elsewhere in this file is just: check the gate, build an embed,
send it.
"""

from __future__ import annotations

import logging
from typing import Optional

import discord
from discord.ext import commands

from utils.database import GuildSettings

log = logging.getLogger("himyar-bot.logging")


class LoggingEvents(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # -- shared gate -------------------------------------------------

    async def _get_log_channel(
        self, guild: discord.Guild, event_key: str
    ) -> Optional[discord.abc.Messageable]:
        settings: GuildSettings = await self.bot.db.get_settings(guild.id)  # type: ignore[attr-defined]
        if not settings.logging_enabled or not settings.log_channel_id:
            return None
        if event_key not in settings.log_events:
            return None
        return guild.get_channel(settings.log_channel_id)

    async def _send(self, channel: Optional[discord.abc.Messageable], embed: discord.Embed) -> None:
        if channel is None:
            return
        try:
            await channel.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            log.warning("Couldn't send a log message (missing permissions?)")

    # -- messages ------------------------------------------------------

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.guild is None or message.author.bot:
            return
        channel = await self._get_log_channel(message.guild, "message_delete")
        if channel is None or channel.id == message.channel.id:
            return
        embed = discord.Embed(
            title="Message deleted",
            description=message.content or "*(no text content — embed, image, or attachment)*",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
        embed.add_field(name="Channel", value=message.channel.mention)
        await self._send(channel, embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.guild is None or before.author.bot:
            return
        if before.content == after.content:
            return  # e.g. an embed finished loading — not a real edit
        channel = await self._get_log_channel(before.guild, "message_edit")
        if channel is None or channel.id == before.channel.id:
            return
        embed = discord.Embed(
            title="Message edited",
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_author(name=str(before.author), icon_url=before.author.display_avatar.url)
        embed.add_field(name="Channel", value=before.channel.mention, inline=False)
        embed.add_field(name="Before", value=(before.content or "*(empty)*")[:1024], inline=False)
        embed.add_field(name="After", value=(after.content or "*(empty)*")[:1024], inline=False)
        if before.jump_url:
            embed.add_field(name="Jump to message", value=after.jump_url, inline=False)
        await self._send(channel, embed)

    # -- members ---------------------------------------------------------

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        channel = await self._get_log_channel(member.guild, "member_join")
        embed = discord.Embed(
            title="Member joined",
            description=f"{member.mention} ({member})",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Account created", value=discord.utils.format_dt(member.created_at, "R"))
        embed.set_thumbnail(url=member.display_avatar.url)
        await self._send(channel, embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        channel = await self._get_log_channel(member.guild, "member_leave")
        embed = discord.Embed(
            title="Member left",
            description=f"{member.mention} ({member})",
            color=discord.Color.dark_orange(),
            timestamp=discord.utils.utcnow(),
        )
        joined = getattr(member, "joined_at", None)
        if joined:
            embed.add_field(name="Was a member for", value=discord.utils.format_dt(joined, "R"))
        embed.set_thumbnail(url=member.display_avatar.url)
        await self._send(channel, embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        channel = await self._get_log_channel(guild, "member_ban")
        embed = discord.Embed(
            title="Member banned",
            description=f"{user.mention} ({user})",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )
        await self._send(channel, embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        channel = await self._get_log_channel(guild, "member_ban")
        embed = discord.Embed(
            title="Member unbanned",
            description=f"{user.mention} ({user})",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow(),
        )
        await self._send(channel, embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.nick != after.nick:
            channel = await self._get_log_channel(after.guild, "nickname_change")
            embed = discord.Embed(
                title="Nickname changed",
                color=discord.Color.blurple(),
                timestamp=discord.utils.utcnow(),
            )
            embed.set_author(name=str(after), icon_url=after.display_avatar.url)
            embed.add_field(name="Before", value=before.nick or before.name, inline=True)
            embed.add_field(name="After", value=after.nick or after.name, inline=True)
            await self._send(channel, embed)

        if set(before.roles) != set(after.roles):
            channel = await self._get_log_channel(after.guild, "role_change")
            added = set(after.roles) - set(before.roles)
            removed = set(before.roles) - set(after.roles)
            if added or removed:
                embed = discord.Embed(
                    title="Roles updated",
                    color=discord.Color.blurple(),
                    timestamp=discord.utils.utcnow(),
                )
                embed.set_author(name=str(after), icon_url=after.display_avatar.url)
                if added:
                    embed.add_field(name="Added", value=", ".join(r.mention for r in added), inline=False)
                if removed:
                    embed.add_field(name="Removed", value=", ".join(r.mention for r in removed), inline=False)
                await self._send(channel, embed)

    # -- channels ----------------------------------------------------

    @commands.Cog.listener()
    async def on_guild_channel_create(self, ch: discord.abc.GuildChannel):
        channel = await self._get_log_channel(ch.guild, "channel_create")
        embed = discord.Embed(
            title="Channel created",
            description=f"{ch.mention if hasattr(ch, 'mention') else ch.name} (`{ch.type}`)",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow(),
        )
        await self._send(channel, embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, ch: discord.abc.GuildChannel):
        channel = await self._get_log_channel(ch.guild, "channel_delete")
        embed = discord.Embed(
            title="Channel deleted",
            description=f"#{ch.name} (`{ch.type}`)",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow(),
        )
        await self._send(channel, embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(LoggingEvents(bot))
