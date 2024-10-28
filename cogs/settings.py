# cogs/settings.py
from discord.ext import commands
import discord
from discord import app_commands
from typing import Optional
from datetime import datetime

class Settings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = bot.config
        
    @app_commands.command(name="settings")
    @app_commands.default_permissions(administrator=True)
    async def settings(self, interaction: discord.Interaction):
        if interaction.user.id != self.bot.owner_id:
            await interaction.response.send_message(
                "Only the bot owner can use this command!",
                ephemeral=True
            )
            return
            
        view = SettingsView(self.bot)
        await interaction.response.send_message(
            "Bot Settings",
            view=view,
            ephemeral=True
        )
        
    @app_commands.command(name="toggle-event-create-notifications")
    @app_commands.default_permissions(manage_messages=True)
    async def toggle_event_notifications(self, interaction: discord.Interaction):
        if not interaction.guild:
            return
            
        if not self.config.event_notification_role_id:
            await interaction.response.send_message(
                "Event notification role is not configured!",
                ephemeral=True
            )
            return
            
        role = interaction.guild.get_role(self.config.event_notification_role_id)
        if not role:
            await interaction.response.send_message(
                "Event notification role not found!",
                ephemeral=True
            )
            return
            
        member = interaction.guild.get_member(interaction.user.id)
        if role in member.roles:
            await member.remove_roles(role)
            message = "You will no longer receive event creation notifications."
        else:
            await member.add_roles(role)
            message = "You will now receive event creation notifications."
            
        await interaction.response.send_message(message, ephemeral=True)
        
    @app_commands.command(name="toggle-daily-summaries")
    async def toggle_daily_summaries(self, interaction: discord.Interaction):
        if not interaction.guild:
            return
            
        if not self.config.daily_summary_role_id:
            await interaction.response.send_message(
                "Daily summary role is not configured!",
                ephemeral=True
            )
            return
            
        role = interaction.guild.get_role(self.config.daily_summary_role_id)
        if not role:
            await interaction.response.send_message(
                "Daily summary role not found!",
                ephemeral=True
            )
            return
            
        member = interaction.guild.get_member(interaction.user.id)
        if role in member.roles:
            await member.remove_roles(role)
            message = "You will no longer receive daily summaries."
        else:
            await member.add_roles(role)
            message = "You will now receive daily summaries."
            
        await interaction.response.send_message(message, ephemeral=True)

class SettingsView(discord.ui.View):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.config = bot.config
        
    @discord.ui.button(label="Event Notifications", style=discord.ButtonStyle.primary)
    async def event_notifications(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = EventNotificationSettings(self.config)
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label="Daily Summary", style=discord.ButtonStyle.primary)
    async def daily_summary(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = DailySummarySettings(self.config)
        await interaction.response.send_modal(modal)
        
    @discord.ui.button(label="Calendar Settings", style=discord.ButtonStyle.primary)
    async def calendar_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = CalendarSettings(self.config)
        await interaction.response.send_modal(modal)

class EventNotificationSettings(discord.ui.Modal, title="Event Notification Settings"):
    def __init__(self, config):
        super().__init__()
        self.config = config
        
        self.channel = discord.ui.TextInput(
            label="Notification Channel ID",
            placeholder="Enter channel ID",
            default=str(config.event_notification_channel_id) if config.event_notification_channel_id else "",
            required=True
        )
        self.add_item(self.channel)
        
        self.role = discord.ui.TextInput(
            label="Notification Role ID",
            placeholder="Enter role ID",
            default=str(config.event_notification_role_id) if config.event_notification_role_id else "",
            required=True
        )
        self.add_item(self.role)
        
    async def on_submit(self, interaction: discord.Interaction):
        try:
            self.config.event_notification_channel_id = int(self.channel.value)
            self.config.event_notification_role_id = int(self.role.value)
            self.config.save()
            await interaction.response.send_message("Event notification settings updated!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("Please enter valid channel and role IDs!", ephemeral=True)

class DailySummarySettings(discord.ui.Modal, title="Daily Summary Settings"):
    def __init__(self, config):
        super().__init__()
        self.config = config
        
        self.channel = discord.ui.TextInput(
            label="Summary Channel ID",
            placeholder="Enter channel ID",
            default=str(config.daily_summary_channel_id) if config.daily_summary_channel_id else "",
            required=True
        )
        self.add_item(self.channel)
        
        self.role = discord.ui.TextInput(
            label="Summary Role ID",
            placeholder="Enter role ID",
            default=str(config.daily_summary_role_id) if config.daily_summary_role_id else "",
            required=True
        )
        self.add_item(self.role)
        
        self.time = discord.ui.TextInput(
            label="Summary Time (24h format)",
            placeholder="HH:MM",
            default=config.daily_summary_time,
            required=True
        )
        self.add_item(self.time)
        
        self.enabled = discord.ui.TextInput(
            label="Enabled (true/false)",
            default=str(config.daily_summary_enabled).lower(),
            required=True
        )
        self.add_item(self.enabled)
        
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Validate time format
            datetime.strptime(self.time.value, "%H:%M")
            
            self.config.daily_summary_channel_id = int(self.channel.value)
            self.config.daily_summary_role_id = int(self.role.value)
            self.config.daily_summary_time = self.time.value
            self.config.daily_summary_enabled = self.enabled.value.lower() == "true"
            self.config.save()
            await interaction.response.send_message("Daily summary settings updated!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message(
                "Please enter valid channel/role IDs and time in HH:MM format!",
                ephemeral=True
            )

class CalendarSettings(discord.ui.Modal, title="Calendar Settings"):
    def __init__(self, config):
        super().__init__()
        self.config = config
        
        self.calendar_id = discord.ui.TextInput(
            label="Google Calendar ID",
            placeholder="Enter calendar ID",
            default=config.google_calendar_id,
            required=True
        )
        self.add_item(self.calendar_id)
        
        self.check_interval = discord.ui.TextInput(
            label="Check Interval (minutes)",
            placeholder="Enter number of minutes",
            default=str(config.calendar_check_interval),
            required=True
        )
        self.add_item(self.check_interval)
        
    async def on_submit(self, interaction: discord.Interaction):
        try:
            self.config.google_calendar_id = self.calendar_id.value
            self.config.calendar_check_interval = int(self.check_interval.value)
            self.config.save()
            await interaction.response.send_message("Calendar settings updated!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("Please enter a valid number for check interval!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Settings(bot))