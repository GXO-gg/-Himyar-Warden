"""
The whole point of this bot: server admins configure it from *inside*
Discord — no website, no login, no separate dashboard to keep in sync.

Running /settings opens a little in-Discord control panel (an ephemeral
message only the invoker can see) with buttons for each section. Each
section has its own view with toggles, a channel picker, and — for
welcome/goodbye — a button that opens a modal (a real text-input popup)
to edit the message template. Every change writes straight to the
database and the panel re-renders in place.

This pattern (Panel -> section Views -> Selects/Modals, all talking to
one Database instance) is meant to be copy-pasted into your other bots —
add a new section by adding one entry to build_section_embed/SectionView
and one button to MainMenuView.
"""

from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.database import Database, GuildSettings, LOG_EVENT_CHOICES
from utils.formatting import PLACEHOLDER_HELP

SECTION_TITLES = {
    "welcome": "👋 Welcome Messages",
    "goodbye": "👋 Goodbye Messages",
    "logging": "🧾 Server Logs",
}


# ---------------------------------------------------------------------------
# Embeds
# ---------------------------------------------------------------------------

def _status_line(enabled: bool, channel_id: Optional[int], extra: str = "") -> str:
    if not enabled or not channel_id:
        return "Disabled"
    line = f"Enabled — <#{channel_id}>"
    if extra:
        line += f" ({extra})"
    return line


def build_overview_embed(settings: GuildSettings, guild: discord.Guild) -> discord.Embed:
    embed = discord.Embed(
        title="Server Settings",
        description=(
            "Pick a section below to configure it. Changes apply immediately.\n"
            "Only you can see and use this panel."
        ),
        color=discord.Color.blurple(),
    )
    embed.add_field(
        name=SECTION_TITLES["welcome"],
        value=_status_line(settings.welcome_enabled, settings.welcome_channel_id),
        inline=False,
    )
    embed.add_field(
        name=SECTION_TITLES["goodbye"],
        value=_status_line(settings.goodbye_enabled, settings.goodbye_channel_id),
        inline=False,
    )
    embed.add_field(
        name=SECTION_TITLES["logging"],
        value=_status_line(
            settings.logging_enabled,
            settings.log_channel_id,
            extra=f"{len(settings.log_events)} event types",
        ),
        inline=False,
    )
    if guild.icon:
        embed.set_footer(text=guild.name, icon_url=guild.icon.url)
    else:
        embed.set_footer(text=guild.name)
    return embed


def build_section_embed(section: str, settings: GuildSettings, guild: discord.Guild) -> discord.Embed:
    embed = discord.Embed(title=SECTION_TITLES[section], color=discord.Color.blurple())

    if section == "welcome":
        embed.add_field(name="Status", value="Enabled" if settings.welcome_enabled else "Disabled")
        embed.add_field(
            name="Channel",
            value=f"<#{settings.welcome_channel_id}>" if settings.welcome_channel_id else "Not set",
        )
        embed.add_field(name="Message", value=f"```{settings.welcome_message}```", inline=False)
        embed.add_field(name="Placeholders", value=PLACEHOLDER_HELP, inline=False)

    elif section == "goodbye":
        embed.add_field(name="Status", value="Enabled" if settings.goodbye_enabled else "Disabled")
        embed.add_field(
            name="Channel",
            value=f"<#{settings.goodbye_channel_id}>" if settings.goodbye_channel_id else "Not set",
        )
        embed.add_field(name="Message", value=f"```{settings.goodbye_message}```", inline=False)
        embed.add_field(name="Placeholders", value=PLACEHOLDER_HELP, inline=False)

    else:  # logging
        embed.add_field(name="Status", value="Enabled" if settings.logging_enabled else "Disabled")
        embed.add_field(
            name="Channel",
            value=f"<#{settings.log_channel_id}>" if settings.log_channel_id else "Not set",
        )
        if settings.log_events:
            events = ", ".join(LOG_EVENT_CHOICES[e] for e in sorted(settings.log_events) if e in LOG_EVENT_CHOICES)
        else:
            events = "None selected"
        embed.add_field(name="Logged events", value=events, inline=False)

    return embed


# ---------------------------------------------------------------------------
# The panel: shared state + navigation for one /settings invocation
# ---------------------------------------------------------------------------

class SettingsPanel:
    def __init__(self, bot: commands.Bot, guild: discord.Guild, invoker_id: int):
        self.bot = bot
        self.db: Database = bot.db  # type: ignore[attr-defined]
        self.guild = guild
        self.invoker_id = invoker_id

    async def check_user(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.invoker_id:
            await interaction.response.send_message(
                "Only the person who ran `/settings` can use these controls.",
                ephemeral=True,
            )
            return False
        return True

    async def send_initial(self, interaction: discord.Interaction) -> None:
        settings = await self.db.get_settings(self.guild.id)
        embed = build_overview_embed(settings, self.guild)
        await interaction.response.send_message(embed=embed, view=MainMenuView(self), ephemeral=True)

    async def show_main(self, interaction: discord.Interaction) -> None:
        settings = await self.db.get_settings(self.guild.id)
        embed = build_overview_embed(settings, self.guild)
        await interaction.response.edit_message(embed=embed, view=MainMenuView(self))

    async def show_section(self, interaction: discord.Interaction, section: str) -> None:
        settings = await self.db.get_settings(self.guild.id)
        embed = build_section_embed(section, settings, self.guild)
        await interaction.response.edit_message(embed=embed, view=SectionView(self, section, settings))

    async def refresh_section(self, interaction: discord.Interaction, section: str) -> None:
        """Re-render a section after a change (toggle, channel pick, modal submit, etc)."""
        settings = await self.db.get_settings(self.guild.id)
        embed = build_section_embed(section, settings, self.guild)
        await interaction.response.edit_message(embed=embed, view=SectionView(self, section, settings))


# ---------------------------------------------------------------------------
# Main menu
# ---------------------------------------------------------------------------

class MainMenuView(discord.ui.View):
    def __init__(self, panel: SettingsPanel):
        super().__init__(timeout=300)
        self.panel = panel
        self.add_item(_SectionButton(panel, "welcome", "👋 Welcome"))
        self.add_item(_SectionButton(panel, "goodbye", "👋 Goodbye"))
        self.add_item(_SectionButton(panel, "logging", "🧾 Logging"))
        self.add_item(_CloseButton(panel))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await self.panel.check_user(interaction)


class _SectionButton(discord.ui.Button):
    def __init__(self, panel: SettingsPanel, section: str, label: str):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.panel = panel
        self.section = section

    async def callback(self, interaction: discord.Interaction):
        await self.panel.show_section(interaction, self.section)


class _CloseButton(discord.ui.Button):
    def __init__(self, panel: SettingsPanel):
        super().__init__(label="Close", style=discord.ButtonStyle.secondary, row=1)
        self.panel = panel

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="Settings closed.", embed=None, view=None)


# ---------------------------------------------------------------------------
# Section view (welcome / goodbye / logging)
# ---------------------------------------------------------------------------

class SectionView(discord.ui.View):
    def __init__(self, panel: SettingsPanel, section: str, settings: GuildSettings):
        super().__init__(timeout=300)
        self.panel = panel
        self.section = section

        enabled = {
            "welcome": settings.welcome_enabled,
            "goodbye": settings.goodbye_enabled,
            "logging": settings.logging_enabled,
        }[section]

        self.add_item(_ToggleButton(panel, section, enabled))
        self.add_item(_ChannelPicker(panel, section))

        if section in ("welcome", "goodbye"):
            self.add_item(_EditMessageButton(panel, section))
        else:
            self.add_item(_LogEventsSelect(panel, settings.log_events))

        self.add_item(_BackButton(panel))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await self.panel.check_user(interaction)


class _ToggleButton(discord.ui.Button):
    def __init__(self, panel: SettingsPanel, section: str, enabled: bool):
        super().__init__(
            label="Turn off" if enabled else "Turn on",
            style=discord.ButtonStyle.danger if enabled else discord.ButtonStyle.success,
        )
        self.panel = panel
        self.section = section

    async def callback(self, interaction: discord.Interaction):
        settings = await self.panel.db.get_settings(self.panel.guild.id)
        if self.section == "welcome":
            await self.panel.db.set_welcome(self.panel.guild.id, enabled=not settings.welcome_enabled)
        elif self.section == "goodbye":
            await self.panel.db.set_goodbye(self.panel.guild.id, enabled=not settings.goodbye_enabled)
        else:
            await self.panel.db.set_logging_enabled(self.panel.guild.id, not settings.logging_enabled)
        await self.panel.refresh_section(interaction, self.section)


class _ChannelPicker(discord.ui.ChannelSelect):
    def __init__(self, panel: SettingsPanel, section: str):
        super().__init__(
            placeholder="Choose a channel...",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
            min_values=1,
            max_values=1,
        )
        self.panel = panel
        self.section = section

    async def callback(self, interaction: discord.Interaction):
        channel = self.values[0]
        if self.section == "welcome":
            await self.panel.db.set_welcome(self.panel.guild.id, channel_id=channel.id, enabled=True)
        elif self.section == "goodbye":
            await self.panel.db.set_goodbye(self.panel.guild.id, channel_id=channel.id, enabled=True)
        else:
            await self.panel.db.set_logging_channel(self.panel.guild.id, channel.id)
        await self.panel.refresh_section(interaction, self.section)


class _EditMessageButton(discord.ui.Button):
    def __init__(self, panel: SettingsPanel, section: str):
        super().__init__(label="Edit message text", style=discord.ButtonStyle.secondary)
        self.panel = panel
        self.section = section

    async def callback(self, interaction: discord.Interaction):
        settings = await self.panel.db.get_settings(self.panel.guild.id)
        current = settings.welcome_message if self.section == "welcome" else settings.goodbye_message
        await interaction.response.send_modal(_MessageModal(self.panel, self.section, current))


class _MessageModal(discord.ui.Modal):
    def __init__(self, panel: SettingsPanel, section: str, current: str):
        super().__init__(title=f"Edit {section.title()} Message")
        self.panel = panel
        self.section = section
        self.text_input = discord.ui.TextInput(
            label="Message",
            style=discord.TextStyle.paragraph,
            default=current,
            max_length=1000,
        )
        self.add_item(self.text_input)

    async def on_submit(self, interaction: discord.Interaction):
        value = str(self.text_input.value)
        if self.section == "welcome":
            await self.panel.db.set_welcome(self.panel.guild.id, message=value)
        else:
            await self.panel.db.set_goodbye(self.panel.guild.id, message=value)
        await self.panel.refresh_section(interaction, self.section)


class _LogEventsSelect(discord.ui.Select):
    def __init__(self, panel: SettingsPanel, current_events: set[str]):
        options = [
            discord.SelectOption(label=label, value=key, default=(key in current_events))
            for key, label in LOG_EVENT_CHOICES.items()
        ]
        super().__init__(
            placeholder="Choose which events to log...",
            min_values=0,
            max_values=len(options),
            options=options,
        )
        self.panel = panel

    async def callback(self, interaction: discord.Interaction):
        await self.panel.db.set_log_events(self.panel.guild.id, set(self.values))
        await self.panel.refresh_section(interaction, "logging")


class _BackButton(discord.ui.Button):
    def __init__(self, panel: SettingsPanel):
        super().__init__(label="← Back", style=discord.ButtonStyle.secondary, row=4)
        self.panel = panel

    async def callback(self, interaction: discord.Interaction):
        await self.panel.show_main(interaction)


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------

class Settings(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="settings",
        description="Configure this bot for your server (welcome, goodbye, logging).",
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def settings_command(self, interaction: discord.Interaction):
        assert interaction.guild is not None
        panel = SettingsPanel(self.bot, interaction.guild, interaction.user.id)
        await panel.send_initial(interaction)


async def setup(bot: commands.Bot):
    await bot.add_cog(Settings(bot))
