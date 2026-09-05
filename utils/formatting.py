"""Shared helpers for turning a message template + member/guild into text."""

from __future__ import annotations

import discord


def render_template(template: str, *, member: discord.Member, guild: discord.Guild) -> str:
    """Fill in the placeholders users can put in their welcome/goodbye text.

    Unknown "{placeholders}" are left as-is instead of raising, so a typo
    in a custom message never crashes the join/leave handler.
    """
    replacements = {
        "{mention}": member.mention,
        "{name}": member.display_name,
        "{username}": str(member),
        "{server}": guild.name,
        "{member_count}": str(guild.member_count),
    }
    result = template
    for placeholder, value in replacements.items():
        result = result.replace(placeholder, value)
    return result


PLACEHOLDER_HELP = (
    "Available placeholders: `{mention}` `{name}` `{username}` "
    "`{server}` `{member_count}`"
)
