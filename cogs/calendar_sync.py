import discord
from discord.ext import commands, tasks
import asyncio
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from typing import List, Optional
import pytz
import json
import hashlib

class DailySummaryView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # No timeout since this is persistent
        
    @discord.ui.button(
        label="Toggle Daily Summaries",
        style=discord.ButtonStyle.secondary,
        custom_id="toggle_daily_summaries"
    )
    async def toggle_summaries(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild:
            await interaction.response.send_message(
                "This button can only be used in a server.",
                ephemeral=True
            )
            return
            
        config = interaction.client.config
        if not config.daily_summary_role_id:
            await interaction.response.send_message(
                "Daily summary role is not configured!",
                ephemeral=True
            )
            return
            
        role = interaction.guild.get_role(config.daily_summary_role_id)
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

class CalendarSync(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = bot.config
        self.last_sync_time = datetime.now(pytz.UTC)
        self.calendar_check.start()
        self._daily_summary_task = None
        self._daily_summary_stop = asyncio.Event()
        self._last_summary_hash = self.get_last_summary_hash()
        self.start_daily_summary()
        
        # Add the persistent view when the cog loads
        self.bot.add_view(DailySummaryView())
        
    def get_last_summary_hash(self) -> str:
        """Generate a hash of the last summary time to prevent duplicates"""
        est = pytz.timezone('US/Eastern')
        now = datetime.now(est)
        configured_time = datetime.strptime(self.config.daily_summary_time, "%H:%M").time()
        target_time = now.replace(
            hour=configured_time.hour,
            minute=configured_time.minute,
            second=0,
            microsecond=0
        )
        
        # If we've passed today's time, use tomorrow's date
        if now.time() > configured_time:
            target_time += timedelta(days=1)
            
        # Create a unique hash for this summary time
        hash_input = f"{target_time.isoformat()}"
        return hashlib.md5(hash_input.encode()).hexdigest()

    def cog_unload(self):
        self.calendar_check.cancel()
        self.stop_daily_summary()

    def start_daily_summary(self):
        """Start the daily summary background task"""
        if self._daily_summary_task is not None:
            self.stop_daily_summary()
        self._daily_summary_stop.clear()
        self._daily_summary_task = asyncio.create_task(self.daily_summary_loop())
        self._last_summary_hash = self.get_last_summary_hash()

    def stop_daily_summary(self):
        """Stop the daily summary background task"""
        if self._daily_summary_task is not None:
            self._daily_summary_stop.set()
            self._daily_summary_task.cancel()
            self._daily_summary_task = None

    def restart_daily_summary(self):
        """Restart the daily summary task (called when settings change)"""
        self.start_daily_summary()

    async def daily_summary_loop(self):
        """Background task that handles daily summary posting"""
        while not self._daily_summary_stop.is_set():
            try:
                if not self.config.daily_summary_enabled:
                    # If disabled, check again in 1 minute
                    await asyncio.sleep(60)
                    continue

                # Calculate time until next summary
                est = pytz.timezone('US/Eastern')
                now = datetime.now(est)
                configured_time = datetime.strptime(self.config.daily_summary_time, "%H:%M").time()
                target_time = now.replace(
                    hour=configured_time.hour,
                    minute=configured_time.minute,
                    second=0,
                    microsecond=0
                )

                # If we've passed the time today, schedule for tomorrow
                if now.time() > configured_time:
                    target_time += timedelta(days=1)

                # Check if we've already sent this summary
                current_hash = hashlib.md5(target_time.isoformat().encode()).hexdigest()
                if current_hash == self._last_summary_hash:
                    # We've already handled this time slot, wait until next one
                    target_time += timedelta(days=1)
                    current_hash = hashlib.md5(target_time.isoformat().encode()).hexdigest()

                wait_seconds = (target_time - now).total_seconds()

                # Wait until either the target time is reached or we're interrupted
                try:
                    await asyncio.wait_for(
                        self._daily_summary_stop.wait(),
                        timeout=wait_seconds
                    )
                    # If we get here, we were interrupted
                    continue
                except asyncio.TimeoutError:
                    # If we get here, it's time to send the summary
                    await self.send_daily_summary()
                    self._last_summary_hash = current_hash

            except Exception as e:
                print(f"Error in daily summary loop: {e}")
                # Wait a minute before retrying on error
                await asyncio.sleep(60)

    @tasks.loop(minutes=5)
    async def calendar_check(self):
        minutes = self.config.calendar_check_interval
        self.calendar_check.change_interval(minutes=minutes)
        
        try:
            events = await self.get_new_events()
            for event in events:
                await self.notify_new_event(event)
        except Exception as e:
            print(f"Error checking calendar: {e}")
       
    async def get_credentials(self):
        try:
            with open('token.json', 'r', encoding='utf-8') as token_file:
                token_data = json.load(token_file)
                return Credentials.from_authorized_user_info(token_data)
        except Exception as e:
            print(f"Error loading credentials: {e}")
            return None
        
    async def get_new_events(self) -> List[dict]:
        try:
            creds = await self.get_credentials()
            if not creds:
                return []
                
            service = build('calendar', 'v3', credentials=creds)
            
            events_result = service.events().list(
                calendarId=self.config.google_calendar_id,
                timeMin=self.last_sync_time.isoformat(),
                updatedMin=self.last_sync_time.isoformat(),
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            self.last_sync_time = datetime.now(pytz.UTC)
            return events_result.get('items', [])
        except Exception as e:
            print(f"Error getting new events: {e}")
            return []
        
    async def get_days_events(self) -> List[dict]:
        creds = Credentials.from_authorized_user_file('token.json')
        service = build('calendar', 'v3', credentials=creds)
        
        est = pytz.timezone('US/Eastern')
        now = datetime.now(est)
        
        # Set up the search window
        today_8am = now.replace(hour=8, minute=0, second=0, microsecond=0)
        tomorrow_4am = (now + timedelta(days=1)).replace(hour=4, minute=0, second=0, microsecond=0)
        
        # If it's between midnight and 4am, adjust the window to look at previous day 8am to today 4am
        if now.hour < 4:
            today_8am = (now - timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
            tomorrow_4am = now.replace(hour=4, minute=0, second=0, microsecond=0)
        
        events_result = service.events().list(
            calendarId=self.config.google_calendar_id,
            timeMin=today_8am.isoformat(),
            timeMax=tomorrow_4am.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        # Filter events to only include those starting within our window
        events = events_result.get('items', [])
        filtered_events = []
        
        for event in events:
            event_start = datetime.fromisoformat(event['start'].get('dateTime', event['start'].get('date')))
            # Convert to EST if the datetime is timezone-aware
            if event_start.tzinfo is not None:
                event_start = event_start.astimezone(est)
                
            # Only include events that start within our window
            if today_8am <= event_start <= tomorrow_4am:
                filtered_events.append(event)
        
        return filtered_events
        
    async def notify_new_event(self, event: dict):
        if not self.config.event_notification_channel_id:
            return
            
        channel = self.bot.get_channel(self.config.event_notification_channel_id)
        if not channel:
            return
            
        # Create embed
        embed = discord.Embed(
            title="New Event Created",
            color=discord.Color.green()
        )
        
        start_time = datetime.fromisoformat(event['start'].get('dateTime', event['start'].get('date')))
        event_url = event.get('htmlLink', '')
        
        embed.add_field(
            name="Event",
            value=f"**[{event['summary']}]({event_url})**",
            inline=False
        )
        embed.add_field(
            name="Time",
            value=f"<t:{int(start_time.timestamp())}:F>",
            inline=False
        )
        
        mention = ""
        if self.config.event_notification_role_id:
            mention = f"<@&{self.config.event_notification_role_id}> "
            
        await channel.send(mention, embed=embed)
        
    async def send_daily_summary(self):
        if not self.config.daily_summary_channel_id:
            return
            
        channel = self.bot.get_channel(self.config.daily_summary_channel_id)
        if not channel:
            return
            
        events = await self.get_days_events()
        
        embed = discord.Embed(
            title="Today's Events",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        mention = ""
        
        if not events:
            embed.description = "No events scheduled for today!"
        else:
            for event in events:
                start_time = datetime.fromisoformat(event['start'].get('dateTime', event['start'].get('date')))
                embed.add_field(
                    name=event['summary'],
                    value=f"Starting at <t:{int(start_time.timestamp())}:t>",
                    inline=False
                )
            mention = f"<@&{self.config.daily_summary_role_id}> " if self.config.daily_summary_role_id else ""          
            
        await channel.send(mention, embed=embed, view=DailySummaryView())
        
    @commands.command(name="force-daily-summary")
    @commands.has_permissions(manage_messages=True)
    async def force_daily_summary(self, ctx):
        await self.send_daily_summary()
        self._last_summary_hash = self.get_last_summary_hash()
        await ctx.message.add_reaction('✅')
        
async def setup(bot):
    await bot.add_cog(CalendarSync(bot))