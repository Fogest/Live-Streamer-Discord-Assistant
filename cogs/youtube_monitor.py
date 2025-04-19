# cogs/youtube_monitor.py
import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands, tasks
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Configure logging
log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s:%(levelname)s:%(name)s: %(message)s')

YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

class YouTubeMonitor(commands.Cog):
    """
    Monitors a specified YouTube channel for new vertical live streams
    and announces them in a designated Discord channel.
    """
    def __init__(self, bot):
        self.bot = bot
        self.config = bot.config
        self.api_key = os.getenv('YOUTUBE_API_KEY')
        self.youtube = None # YouTube API client, initialized later
        self.last_checked_video_id = None # Store the ID of the latest processed live stream
        self.last_check_time = None # Track the time of the last successful check
        self.is_first_run = True # Flag to avoid announcing old streams on first start

        if not self.api_key:
            log.error("YOUTUBE_API_KEY not found in environment variables. YouTube Monitor will not function.")
            # Optionally, unload the cog or prevent the task from starting
            # raise commands.ExtensionFailed("YouTubeMonitor", "Missing YOUTUBE_API_KEY") # Or handle gracefully

    def cog_load(self):
        log.info("YouTubeMonitor Cog Loaded.")
        if self.api_key and self.config.youtube_monitor_enabled:
            self.monitor_loop.change_interval(minutes=self.config.youtube_monitor_check_interval_minutes)
            self.monitor_loop.start()
            log.info(f"YouTube monitor task started. Interval: {self.config.youtube_monitor_check_interval_minutes} minutes.")
        elif not self.api_key:
             log.warning("YouTube monitor task NOT started: Missing API Key.")
        else:
             log.info("YouTube monitor task NOT started: Disabled in config.")


    def cog_unload(self):
        self.monitor_loop.cancel()
        log.info("YouTube monitor task stopped.")

    def _build_youtube_client(self):
        """Builds the YouTube API client."""
        try:
            # Use context manager if available or handle closing manually if needed
            self.youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=self.api_key)
            log.debug("YouTube API client built successfully.")
        except Exception as e:
            log.error(f"Failed to build YouTube API client: {e}")
            self.youtube = None # Ensure client is None on failure

    @tasks.loop(minutes=5) # Default interval, will be updated in cog_load
    async def monitor_loop(self):
        """Periodically checks the YouTube channel for new vertical live streams."""
        if not self.config.youtube_monitor_enabled or not self.config.youtube_channel_id or not self.api_key:
            # log.debug("YouTube monitor disabled or channel ID/API Key not set, skipping check.")
            # Stop the loop if it shouldn't be running
            if self.monitor_loop.is_running() and not self.config.youtube_monitor_enabled:
                 log.info("Disabling YouTube monitor task as per config.")
                 self.monitor_loop.stop()
            return

        if not self.youtube:
            self._build_youtube_client()
            if not self.youtube:
                log.error("YouTube client not available, skipping check.")
                # Consider adding a backoff mechanism here
                await asyncio.sleep(60) # Wait a minute before retrying build
                return

        log.info(f"Checking YouTube channel {self.config.youtube_channel_id} for live streams...")
        self.last_check_time = datetime.now(timezone.utc)

        try:
            # Use search.list to find live streams for the channel
            search_response = self.youtube.search().list(
                part="snippet,id",
                channelId=self.config.youtube_channel_id,
                eventType="live",
                type="video",
                order="date", # Get the latest first
                maxResults=5 # Check a few recent ones in case of API delays
            ).execute()

            live_streams = search_response.get("items", [])
            log.debug(f"Found {len(live_streams)} potential live stream(s).")

            if not live_streams:
                log.info("No active live streams found.")
                self.is_first_run = False # Mark first run as complete even if no streams found
                return

            # Process streams from oldest to newest to handle multiple new streams correctly
            for item in reversed(live_streams):
                video_id = item["id"]["videoId"]
                snippet = item["snippet"]
                published_at_str = snippet["publishedAt"]
                title = snippet["title"]
                description = snippet["description"]
                channel_title = snippet["channelTitle"] # Streamer name

                # --- State Management: Avoid re-announcing ---
                # On the very first run after bot start, store the latest ID found without announcing
                if self.is_first_run:
                    log.info(f"First run: Setting initial last_checked_video_id to {video_id}")
                    self.last_checked_video_id = video_id
                    # Don't process further on the very first item of the first run
                    continue # Move to the next item in this first run check if any

                # If we have seen this video ID before, skip
                if video_id == self.last_checked_video_id:
                    log.debug(f"Skipping already processed video ID: {video_id}")
                    continue

                # Heuristic: Check if stream started *after* the last check time (with some buffer)
                # This helps avoid announcing streams that started long ago but were missed
                try:
                    published_at = datetime.fromisoformat(published_at_str.replace('Z', '+00:00'))
                    # Add a buffer slightly larger than the check interval to avoid race conditions
                    buffer_minutes = self.config.youtube_monitor_check_interval_minutes + 2
                    if self.last_check_time and published_at < (self.last_check_time - timedelta(minutes=buffer_minutes)):
                         log.info(f"Skipping old stream '{title}' (ID: {video_id}) published at {published_at_str}")
                         # Update last_checked_id even for skipped old streams to prevent re-processing
                         self.last_checked_video_id = video_id
                         continue
                except (ValueError, TypeError) as e:
                     log.warning(f"Could not parse publishedAt date '{published_at_str}': {e}")
                     # Decide whether to proceed or skip if date is unparseable

                log.info(f"Found new potential live stream: '{title}' (ID: {video_id})")

                # --- Vertical Stream Detection (Heuristic) ---
                # Simple check: Look for keywords in title or description
                # TODO: Refine this - API might offer aspect ratio in video details (requires extra API call)
                is_vertical = True # don't worry if it's vertical or not, just announce it right now
                # vertical_keywords = ["#shorts", "vertical stream", "portrait mode", "9:16"] # Case-insensitive check needed
                # if any(keyword.lower() in title.lower() for keyword in vertical_keywords) or \
                #    any(keyword.lower() in description.lower() for keyword in vertical_keywords):
                #     is_vertical = True
                #     log.info(f"Stream '{title}' detected as potentially vertical based on keywords.")
                # else:
                #     log.info(f"Stream '{title}' not detected as vertical based on keywords. Skipping announcement.")
                #     # Update last_checked_id even for non-vertical streams to prevent re-processing
                #     self.last_checked_video_id = video_id
                #     continue # Skip non-vertical streams

                # --- Announce Vertical Stream ---
                if is_vertical:
                    await self.announce_stream(video_id, title, channel_title)
                    self.last_checked_video_id = video_id # Update state *after* successful announcement attempt

            # Mark first run as complete after processing all initial streams
            if self.is_first_run:
                log.info("First run check complete.")
                self.is_first_run = False


        except HttpError as e:
            log.error(f"An HTTP error occurred during YouTube API call: {e}")
            # Handle specific errors (e.g., quota exceeded) if necessary
            if e.resp.status == 403:
                 log.error("Potential Quota Exceeded or API Key issue.")
                 # Consider stopping the loop or increasing interval temporarily
                 # self.monitor_loop.change_interval(minutes=self.config.youtube_monitor_check_interval_minutes * 2) # Example: Double interval
                 # self.monitor_loop.restart()
            # Reset client to force rebuild on next attempt?
            self.youtube = None
        except Exception as e:
            log.exception(f"An unexpected error occurred in the monitor loop: {e}")
            # Reset client to force rebuild on next attempt?
            self.youtube = None


    async def announce_stream(self, video_id, title, channel_title):
        """Formats and sends the announcement message to the configured Discord channel."""
        if not self.config.youtube_monitor_discord_channel_id:
            log.warning("Cannot announce stream: Discord announcement channel ID not set.")
            return

        channel = self.bot.get_channel(self.config.youtube_monitor_discord_channel_id)
        if not channel:
            log.error(f"Cannot announce stream: Discord channel ID {self.config.youtube_monitor_discord_channel_id} not found.")
            # Maybe disable the feature in config automatically?
            # self.config.youtube_monitor_enabled = False
            # self.config.save()
            # self.monitor_loop.stop()
            return

        if not isinstance(channel, discord.TextChannel):
            log.error(f"Cannot announce stream: Channel {channel.name} (ID: {channel.id}) is not a text channel.")
            return

        # Check permissions
        if not channel.permissions_for(channel.guild.me).send_messages:
             log.error(f"Cannot announce stream: Missing 'Send Messages' permission in channel {channel.mention}.")
             return


        stream_url = f"https://www.youtube.com/watch?v={video_id}"

        # Format other platform links
        other_links_str = ""
        if self.config.youtube_monitor_platform_links:
            links = []
            for name, url in self.config.youtube_monitor_platform_links.items():
                links.append(f"<{url}> ({name})") # Format as Discord links
            if links:
                other_links_str = "Also live on:\n" + "\n".join(links)

        # Format the announcement message using the template from config
        message_content = self.config.youtube_monitor_announcement_message.format(
            streamer_name=channel_title,
            stream_url=stream_url,
            other_links=other_links_str
        ).strip() # Use strip() to remove potential trailing newlines if other_links is empty

        try:
            log.info(f"Announcing vertical stream '{title}' (ID: {video_id}) to channel {channel.id}")
            await channel.send(message_content)
        except discord.Forbidden:
            log.error(f"Failed to send announcement to {channel.mention}: Missing Permissions")
        except discord.HTTPException as e:
            log.error(f"Failed to send announcement to {channel.mention}: HTTPException: {e}")
        except Exception as e:
            log.exception(f"An unexpected error occurred while sending announcement: {e}")


    @monitor_loop.before_loop
    async def before_monitor_loop(self):
        """Wait until the bot is ready before starting the loop."""
        await self.bot.wait_until_ready()
        log.info("Bot is ready, YouTube monitor loop starting...")
        # Initialize the client once before the first run
        if not self.youtube and self.api_key:
             self._build_youtube_client()


async def setup(bot):
    # Ensure config is loaded and API key exists before adding cog
    if not hasattr(bot, 'config'):
        log.error("Bot config not found during YouTubeMonitor setup.")
        # Optionally load config here if needed, but ideally it's loaded in main.py
        # from config import BotConfig
        # bot.config = BotConfig.load()
        raise commands.ExtensionFailed("YouTubeMonitor", "Bot config not loaded.")

    api_key = os.getenv('YOUTUBE_API_KEY')
    if not api_key:
         log.warning("YOUTUBE_API_KEY not set. YouTubeMonitor cog will load but the monitor task will not run.")
         # Allow loading so settings can still be accessed, but log the warning.

    await bot.add_cog(YouTubeMonitor(bot))
