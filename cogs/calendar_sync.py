import discord
from discord.ext import commands, tasks
import asyncio  # Add this import
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from typing import List, Optional
import pytz
import json

class CalendarSync(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = bot.config
        self.last_sync_time = datetime.now(pytz.UTC)
        self.calendar_check.start()
        self.daily_summary.start()
        
    def cog_unload(self):
        self.calendar_check.cancel()
        self.daily_summary.cancel()
        
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
            
    @tasks.loop(hours=24)
    async def daily_summary(self):
        if not self.config.daily_summary_enabled:
            return
            
        try:
            # Get configured time
            est = pytz.timezone('US/Eastern')
            now = datetime.now(est)
            configured_time = datetime.strptime(self.config.daily_summary_time, "%H:%M").time()
            target_time = now.replace(
                hour=configured_time.hour,
                minute=configured_time.minute,
                second=0,
                microsecond=0
            )
            
            # Wait until configured time
            if now.time() > configured_time:
                target_time += timedelta(days=1)
            wait_seconds = (target_time - now).total_seconds()
            await asyncio.sleep(wait_seconds)
            
            await self.send_daily_summary()
            
        except Exception as e:
            print(f"Error in daily summary: {e}")
       
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
        today = datetime.now(est).replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)
        
        events_result = service.events().list(
            calendarId=self.config.google_calendar_id,
            timeMin=today.isoformat(),
            timeMax=tomorrow.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        return events_result.get('items', [])
        
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
                
        mention = ""
        if self.config.daily_summary_role_id:
            mention = f"<@&{self.config.daily_summary_role_id}> "
            
        await channel.send(mention, embed=embed)
        
    @commands.command(name="force-daily-summary")
    @commands.has_permissions(manage_messages=True)
    async def force_daily_summary(self, ctx):
        await self.send_daily_summary()
        await ctx.message.add_reaction('✅')
        
async def setup(bot):
    await bot.add_cog(CalendarSync(bot))