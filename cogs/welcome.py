"""Public-facing welcome/goodbye messages — the classic ProBot-style feature.

Nothing here is configurable by editing this file per-server; all of that
lives in the database and is edited through /settings (cogs/settings.py).
That's the point of the whole template: one codebase, one running bot,
unlimited servers each with their own channel + message text.
"""

from __future__ import annotations

import logging

import discord
from discord.ext import commands

from utils.formatting import render_template

log = logging.getLogger("himyar-bot.welcome")


class Welcome(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        settings = await self.bot.db.get_settings(member.guild.id)  # type: ignore[attr-defined]
        if not settings.welcome_enabled or not settings.welcome_channel_id:
            return

        channel = member.guild.get_channel(settings.welcome_channel_id)
        if channel is None:
            return

        text = render_template(settings.welcome_message, member=member, guild=member.guild)
        embed = discord.Embed(description=text, color=discord.Color.green())
        embed.set_thumbnail(url=member.display_avatar.url)

        try:
            await channel.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            log.warning("Couldn't send welcome message in guild %s", member.guild.id)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        settings = await self.bot.db.get_settings(member.guild.id)  # type: ignore[attr-defined]
        if not settings.goodbye_enabled or not settings.goodbye_channel_id:
            return

        channel = member.guild.get_channel(settings.goodbye_channel_id)
        if channel is None:
            return

        text = render_template(settings.goodbye_message, member=member, guild=member.guild)
        embed = discord.Embed(description=text, color=discord.Color.red())
        embed.set_thumbnail(url=member.display_avatar.url)

        try:
            await channel.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            log.warning("Couldn't send goodbye message in guild %s", member.guild.id)


async def setup(bot: commands.Bot):
    await bot.add_cog(Welcome(bot))
