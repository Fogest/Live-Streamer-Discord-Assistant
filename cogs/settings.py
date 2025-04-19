# cogs/settings.py
import json
import os
import sys
from discord.ext import commands, tasks
import discord
from discord import app_commands
from typing import Optional, Dict
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

        # Defer the response to prevent timeout
        await interaction.response.defer(ephemeral=True)

        view = SettingsView(self.bot)
        # Use followup.send after deferring
        await interaction.followup.send(
            "Bot Settings",
            view=view,
            ephemeral=True # Keep ephemeral for settings
        )
        
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
        super().__init__(timeout=180) # Add timeout
        self.bot = bot
        self.config = bot.config

    @discord.ui.button(label="Daily Summary", style=discord.ButtonStyle.primary, row=0)
    async def daily_summary(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = DailySummarySettings(self.config)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="YouTube Monitor", style=discord.ButtonStyle.secondary, row=0)
    async def youtube_monitor(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Ensure YouTube API key is set before allowing config
        api_key = os.getenv('YOUTUBE_API_KEY')
        if not api_key:
             await interaction.response.send_message(
                 "Error: `YOUTUBE_API_KEY` is not set in the bot's environment variables (`.env` file). "
                 "Please set it before configuring the YouTube Monitor.",
                 ephemeral=True
             )
             return

        modal = YouTubeMonitorSettings(self.config)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Platform Links", style=discord.ButtonStyle.secondary, row=1)
    async def platform_links(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = PlatformLinksSettings(self.config)
        await interaction.response.send_modal(modal)

# --- Daily Summary Modal ---
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
            
            # TODO: If daily summary logic is moved elsewhere, update restart logic here
            
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

# --- YouTube Monitor Modal ---
class YouTubeMonitorSettings(discord.ui.Modal, title="YouTube Monitor Settings"):
    def __init__(self, config):
        super().__init__(timeout=300) # Longer timeout for complex input
        self.config = config

        # Convert platform links dict to JSON string for TextInput
        platform_links_str = ""
        if config.youtube_monitor_platform_links:
            try:
                platform_links_str = json.dumps(config.youtube_monitor_platform_links, indent=2)
            except TypeError:
                platform_links_str = "{}" # Fallback

        self.enabled = discord.ui.TextInput(
            label="Enable Monitor (true/false)",
            placeholder="Type 'true' or 'false'",
            default=str(config.youtube_monitor_enabled).lower(),
            required=True,
            max_length=5,
            row=0
        )
        self.add_item(self.enabled)

        self.youtube_channel_id = discord.ui.TextInput(
            label="YouTube Channel ID",
            placeholder="e.g., UCXXXXXXXXXXXXXXXXXXXXXX",
            default=config.youtube_channel_id or "",
            required=False, # Required only if enabled=true, validated in on_submit
            max_length=30,
            row=1
        )
        self.add_item(self.youtube_channel_id)

        self.discord_channel_id = discord.ui.TextInput(
            label="Discord Announcement Channel ID",
            placeholder="Right-click channel → Copy ID",
            default=str(config.youtube_monitor_discord_channel_id) if config.youtube_monitor_discord_channel_id else "",
            required=False, # Required only if enabled=true, validated in on_submit
            min_length=17,
            max_length=20,
            row=2
        )
        self.add_item(self.discord_channel_id)

        self.check_interval = discord.ui.TextInput(
            label="Check Interval (minutes, min 1)",
            placeholder="e.g., 5",
            default=str(config.youtube_monitor_check_interval_minutes),
            required=True,
            max_length=4,
            row=3
        )
        self.add_item(self.check_interval)

        # platform_links removed to stay within 5 component limit. Configure via config.json if needed.

        self.announcement_message = discord.ui.TextInput(
            label='Announcement Message Template',
            placeholder='Variables: {streamer_name}, {stream_url}, {other_links}', # Corrected indentation
            default=config.youtube_monitor_announcement_message, # Corrected indentation
            style=discord.TextStyle.paragraph, # Corrected indentation
            required=True, # Corrected indentation
            row=4 # Rows are 0-4, this should be the last row # Corrected indentation
        )
        # Add the item to the modal
        self.add_item(self.announcement_message) # Corrected indentation

    # Correct indentation for the method definition
    async def on_submit(self, interaction: discord.Interaction):
        is_enabled = self.enabled.value.lower() == 'true'
        errors = []

        # --- Validation ---
        if self.enabled.value.lower() not in ['true', 'false']:
            errors.append("Enable Monitor value must be 'true' or 'false'.")

        yt_channel_id = self.youtube_channel_id.value.strip() or None
        if is_enabled and not yt_channel_id:
            errors.append("YouTube Channel ID is required when the monitor is enabled.")

        discord_ch_id_str = self.discord_channel_id.value.strip()
        discord_ch_id = None
        if discord_ch_id_str:
            try:
                discord_ch_id = int(discord_ch_id_str)
                channel = interaction.guild.get_channel(discord_ch_id) if interaction.guild else None
                if not channel:
                    errors.append("Discord Announcement Channel ID not found in this server.")
                elif not isinstance(channel, discord.TextChannel):
                     errors.append("Discord Announcement Channel must be a Text Channel.")
                elif not channel.permissions_for(interaction.guild.me).send_messages:
                     errors.append(f"I don't have permission to send messages in {channel.mention}.")

            except ValueError:
                errors.append("Discord Announcement Channel ID must be a valid number.")
        elif is_enabled:
             errors.append("Discord Announcement Channel ID is required when the monitor is enabled.")


        interval_minutes = None
        try:
            interval_minutes = int(self.check_interval.value)
            if interval_minutes < 1:
                errors.append("Check Interval must be at least 1 minute.")
        except ValueError:
            errors.append("Check Interval must be a valid number.")

        # Platform links are not edited via this modal anymore.
        platform_links_dict = self.config.youtube_monitor_platform_links # Keep existing value

        announcement_msg = self.announcement_message.value.strip()
        if not announcement_msg:
             errors.append("Announcement Message Template cannot be empty.")
        # Basic check for required placeholders if enabled
        elif is_enabled and ("{stream_url}" not in announcement_msg):
             errors.append("Announcement Message Template must include `{stream_url}`.")


        if errors:
            await interaction.response.send_message(
                "**Configuration errors:**\n- " + "\n- ".join(errors),
                ephemeral=True
            )
            return

        # --- Save Config ---
        try:
            self.config.youtube_monitor_enabled = is_enabled
            self.config.youtube_channel_id = yt_channel_id
            self.config.youtube_monitor_discord_channel_id = discord_ch_id
            self.config.youtube_monitor_check_interval_minutes = interval_minutes
            self.config.youtube_monitor_platform_links = platform_links_dict
            self.config.youtube_monitor_announcement_message = announcement_msg
            self.config.save()

            # Find the cog instance to potentially restart its task
            monitor_cog = interaction.client.get_cog('YouTubeMonitor')
            restart_needed = False
            if monitor_cog:
                # Check if the task needs restarting (enabled status changed or interval changed)
                if hasattr(monitor_cog, 'monitor_loop'):
                     current_interval = monitor_cog.monitor_loop.minutes
                     if monitor_cog.monitor_loop.is_running() != is_enabled or current_interval != interval_minutes:
                         restart_needed = True
                         monitor_cog.monitor_loop.restart() # Restart task with new settings

            message = "YouTube Monitor settings updated!"
            if restart_needed:
                 message += "\nThe monitoring task has been updated/restarted."
            elif is_enabled and not monitor_cog:
                 message += "\n**Note:** The YouTube Monitor cog doesn't seem to be loaded. You might need to reload it or restart the bot."
            elif not is_enabled and monitor_cog and hasattr(monitor_cog, 'monitor_loop') and monitor_cog.monitor_loop.is_running():
                 message += "\n**Note:** The monitor is now disabled, but the background task might need a manual stop/restart if it was running."


            await interaction.response.send_message(message, ephemeral=True)

        except Exception as e:
            print(f"Error saving YouTube Monitor config: {e}") # Log error server-side
            await interaction.response.send_message(
                f"An unexpected error occurred while saving the settings: {e}",
                ephemeral=True
            )


# --- Platform Links Modal ---
class PlatformLinksSettings(discord.ui.Modal, title="Platform Links Settings"):
    def __init__(self, config):
        super().__init__(timeout=300) # Longer timeout for complex input
        self.config = config

        # Get current values or empty string if not set
        platform_links = config.youtube_monitor_platform_links or {}
        twitch_url = platform_links.get("Twitch", "")
        kick_url = platform_links.get("Kick", "")
        tiktok_url = platform_links.get("TikTok", "")

        self.twitch_url = discord.ui.TextInput(
            label="Twitch Stream URL",
            placeholder="e.g., https://www.twitch.tv/yourchannel",
            default=twitch_url,
            required=False,
            max_length=200,
            row=0
        )
        self.add_item(self.twitch_url)

        self.kick_url = discord.ui.TextInput(
            label="Kick Stream URL",
            placeholder="e.g., https://kick.com/yourchannel",
            default=kick_url,
            required=False,
            max_length=200,
            row=1
        )
        self.add_item(self.kick_url)

        self.tiktok_url = discord.ui.TextInput(
            label="TikTok Stream URL",
            placeholder="e.g., https://www.tiktok.com/@yourchannel/live",
            default=tiktok_url,
            required=False,
            max_length=200,
            row=2
        )
        self.add_item(self.tiktok_url)

    async def on_submit(self, interaction: discord.Interaction):
        errors = []

        # --- Validation (basic URL format check if provided) ---
        def is_valid_url(url):
            if not url:
                return True  # Empty is allowed
            # Basic check for URL-like structure
            return url.startswith(('http://', 'https://')) and '.' in url

        twitch_url = self.twitch_url.value.strip()
        if twitch_url and not is_valid_url(twitch_url):
            errors.append("Twitch Stream URL seems invalid. It should start with http:// or https:// and contain a domain.")

        kick_url = self.kick_url.value.strip()
        if kick_url and not is_valid_url(kick_url):
            errors.append("Kick Stream URL seems invalid. It should start with http:// or https:// and contain a domain.")

        tiktok_url = self.tiktok_url.value.strip()
        if tiktok_url and not is_valid_url(tiktok_url):
            errors.append("TikTok Stream URL seems invalid. It should start with http:// or https:// and contain a domain.")

        if errors:
            await interaction.response.send_message(
                "**Configuration errors:**\n- " + "\n- ".join(errors),
                ephemeral=True
            )
            return

        # --- Save Config ---
        try:
            # Build new platform links dictionary, only including non-empty URLs
            platform_links_dict = {}
            if twitch_url:
                platform_links_dict["Twitch"] = twitch_url
            if kick_url:
                platform_links_dict["Kick"] = kick_url
            if tiktok_url:
                platform_links_dict["TikTok"] = tiktok_url

            self.config.youtube_monitor_platform_links = platform_links_dict
            self.config.save()

            message = "Platform Links updated!"
            if platform_links_dict:
                message += "\nConfigured platforms:\n" + "\n".join([f"- {name}: {url}" for name, url in platform_links_dict.items()])
            else:
                message += "\nNo platform links are currently configured."

            await interaction.response.send_message(message, ephemeral=True)

        except Exception as e:
            print(f"Error saving Platform Links config: {e}") # Log error server-side
            await interaction.response.send_message(
                f"An unexpected error occurred while saving the settings: {e}",
                ephemeral=True
            )

async def setup(bot):
    # Ensure config is loaded before adding cog
    if not hasattr(bot, 'config'):
        print("Error: Bot config not loaded before Settings cog setup.")
        # Handle appropriately, maybe raise an exception or load config here
        from config import BotConfig # Avoid circular import if possible
        bot.config = BotConfig.load()

    await bot.add_cog(Settings(bot))
