# cogs/settings.py
import os
import sys
from discord.ext import commands
import discord
from discord import app_commands
from typing import Optional
from datetime import datetime

class Settings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = bot.config
        
    @app_commands.command(
        name="settings",
        description="Configure bot settings (bot owner only)"
    )
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
        
    @app_commands.command(
        name="toggle-events",
        description="Toggle notifications for new event creation"
    )
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
        
    @app_commands.command(
        name="toggle-summary",
        description="Toggle daily summary notifications"
    )
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
            placeholder="Right-click channel → Copy ID",
            default=str(config.event_notification_channel_id) if config.event_notification_channel_id else "",
            required=True,
            min_length=17,
            max_length=20
        )
        self.add_item(self.channel)
        
        self.role = discord.ui.TextInput(
            label="Notification Role ID",
            placeholder="Right-click role → Copy ID",
            default=str(config.event_notification_role_id) if config.event_notification_role_id else "",
            required=True,
            min_length=17,
            max_length=20
        )
        self.add_item(self.role)
        
    async def on_submit(self, interaction: discord.Interaction):
        try:
            channel_id = int(self.channel.value)
            role_id = int(self.role.value)
            
            # Verify channel exists
            channel = interaction.guild.get_channel(channel_id)
            if not channel:
                await interaction.response.send_message(
                    "Channel ID not found! Make sure to use the channel's ID.",
                    ephemeral=True
                )
                return
                
            # Verify role exists
            role = interaction.guild.get_role(role_id)
            if not role:
                await interaction.response.send_message(
                    "Role ID not found! Make sure to use the role's ID.",
                    ephemeral=True
                )
                return
            
            self.config.event_notification_channel_id = channel_id
            self.config.event_notification_role_id = role_id
            self.config.save()
            
            await interaction.response.send_message(
                f"Event notification settings updated!\n"
                f"Channel: {channel.mention}\n"
                f"Role: {role.mention}",
                ephemeral=True
            )
        except ValueError:
            await interaction.response.send_message(
                "Please enter valid channel and role IDs! You can get these by:\n"
                "1. Enable Developer Mode in Discord Settings → App Settings → Advanced\n"
                "2. Right-click on the channel/role and select 'Copy ID'",
                ephemeral=True
            )

class DailySummarySettings(discord.ui.Modal, title="Daily Summary Settings"):
    def __init__(self, config):
        super().__init__()
        self.config = config
        
        self.channel = discord.ui.TextInput(
            label="Summary Channel ID",
            placeholder="Right-click channel → Copy ID",
            default=str(config.daily_summary_channel_id) if config.daily_summary_channel_id else "",
            required=True,
            min_length=17,
            max_length=20
        )
        self.add_item(self.channel)
        
        self.role = discord.ui.TextInput(
            label="Summary Role ID",
            placeholder="Right-click role → Copy ID",
            default=str(config.daily_summary_role_id) if config.daily_summary_role_id else "",
            required=True,
            min_length=17,
            max_length=20
        )
        self.add_item(self.role)
        
        self.time = discord.ui.TextInput(
            label="Summary Time (24h format)",
            placeholder="Example: 09:00",
            default=config.daily_summary_time,
            required=True,
            min_length=5,
            max_length=5
        )
        self.add_item(self.time)
        
        self.enabled = discord.ui.TextInput(
            label="Enabled (true/false)",
            placeholder="Type 'true' or 'false'",
            default=str(config.daily_summary_enabled).lower(),
            required=True,
            max_length=5
        )
        self.add_item(self.enabled)
        
    async def on_submit(self, interaction: discord.Interaction):
        try:
            channel_id = int(self.channel.value)
            role_id = int(self.role.value)
            
            # Validate time format
            try:
                datetime.strptime(self.time.value, "%H:%M")
            except ValueError:
                await interaction.response.send_message(
                    "Invalid time format! Please use HH:MM format (e.g., 09:00)",
                    ephemeral=True
                )
                return
                
            # Validate channel
            channel = interaction.guild.get_channel(channel_id)
            if not channel:
                await interaction.response.send_message(
                    "Channel ID not found! Make sure to use the channel's ID.",
                    ephemeral=True
                )
                return
                
            # Validate role
            role = interaction.guild.get_role(role_id)
            if not role:
                await interaction.response.send_message(
                    "Role ID not found! Make sure to use the role's ID.",
                    ephemeral=True
                )
                return
                
            # Validate enabled value
            if self.enabled.value.lower() not in ['true', 'false']:
                await interaction.response.send_message(
                    "Enabled value must be 'true' or 'false'",
                    ephemeral=True
                )
                return
            
            self.config.daily_summary_channel_id = channel_id
            self.config.daily_summary_role_id = role_id
            self.config.daily_summary_time = self.time.value
            self.config.daily_summary_enabled = self.enabled.value.lower() == 'true'
            self.config.save()
            
            await interaction.response.send_message(
                f"Daily summary settings updated!\n"
                f"Channel: {channel.mention}\n"
                f"Role: {role.mention}\n"
                f"Time: {self.time.value}\n"
                f"Enabled: {self.enabled.value.lower()}",
                ephemeral=True
            )
        except ValueError:
            await interaction.response.send_message(
                "Please enter valid channel and role IDs! You can get these by:\n"
                "1. Enable Developer Mode in Discord Settings → App Settings → Advanced\n"
                "2. Right-click on the channel/role and select 'Copy ID'",
                ephemeral=True
            )

class CalendarSettings(discord.ui.Modal, title="Calendar Settings"):
    def __init__(self, config):
        super().__init__()
        self.config = config
        
        self.calendar_id = discord.ui.TextInput(
            label="Google Calendar ID",
            placeholder="Enter calendar ID (looks like an email address)",
            default=config.google_calendar_id,
            required=True
        )
        self.add_item(self.calendar_id)
        
        self.check_interval = discord.ui.TextInput(
            label="Check Interval (minutes)",
            placeholder="Enter number of minutes (e.g., 5)",
            default=str(config.calendar_check_interval),
            required=True,
            max_length=3
        )
        self.add_item(self.check_interval)
        
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Validate check interval
            interval = int(self.check_interval.value)
            if interval < 1:
                await interaction.response.send_message(
                    "Check interval must be at least 1 minute!",
                    ephemeral=True
                )
                return
                
            self.config.google_calendar_id = self.calendar_id.value
            self.config.calendar_check_interval = interval
            self.config.save()
            
            await interaction.response.send_message(
                f"Calendar settings updated!\n"
                f"Calendar ID: {self.calendar_id.value}\n"
                f"Check Interval: {interval} minutes",
                ephemeral=True
            )
        except ValueError:
            await interaction.response.send_message(
                "Please enter a valid number for check interval!",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Settings(bot))