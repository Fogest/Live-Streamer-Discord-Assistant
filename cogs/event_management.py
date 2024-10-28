# cogs/event_management.py
import discord
from discord import app_commands
from discord.ext import commands
import datetime
from datetime import timedelta
import pytz
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from typing import List, Optional
import json

class EventModal(discord.ui.Modal, title="Schedule Game/Event"):
    def __init__(self, cog: 'EventManagement'):
        super().__init__()
        self.cog = cog
        
        self.title_input = discord.ui.TextInput(
            label="Title",
            placeholder="Enter game/event title",
            max_length=100,
            required=True
        )
        self.add_item(self.title_input)
        
        self.time_input = discord.ui.TextInput(
            label="Start Time (EST)",
            placeholder="YYYY-MM-DD HH:MM (e.g., 2024-10-28 15:00)",
            required=True
        )
        self.add_item(self.time_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Parse time in EST
            est = pytz.timezone('US/Eastern')
            naive_time = datetime.datetime.strptime(self.time_input.value, "%Y-%m-%d %H:%M")
            start_time = est.localize(naive_time)
            
            if start_time < datetime.datetime.now(est):
                await interaction.response.send_message(
                    "Event time must be in the future!",
                    ephemeral=True
                )
                return
            
            # Get nearby events
            nearby_events = await self.cog.get_nearby_events(start_time)
            
            # Create confirmation view
            view = EventConfirmationView(
                self.cog,
                self.title_input.value,
                start_time,
                nearby_events
            )
            
            # Create preview embed
            embed = discord.Embed(
                title="Event Preview",
                color=discord.Color.yellow()
            )
            
            embed.add_field(
                name="New Event",
                value=f"**{self.title_input.value}**\n"
                      f"Start: <t:{int(start_time.timestamp())}:F>\n"
                      f"End: <t:{int((start_time + timedelta(hours=8)).timestamp())}:F>",
                inline=False
            )
            
            if nearby_events:
                embed.add_field(
                    name="Nearby Events",
                    value=self.cog.format_nearby_events(nearby_events, start_time),
                    inline=False
                )
                
                # Check for overlaps
                overlaps = self.cog.check_overlaps(start_time, nearby_events)
                if overlaps:
                    embed.add_field(
                        name="⚠️ Warning",
                        value="This event overlaps with existing events!",
                        inline=False
                    )
            
            await interaction.response.send_message(
                embed=embed,
                view=view,
                ephemeral=True
            )
            
        except ValueError:
            await interaction.response.send_message(
                "Invalid time format! Use YYYY-MM-DD HH:MM (e.g., 2024-10-28 15:00)",
                ephemeral=True
            )

class EventConfirmationView(discord.ui.View):
    def __init__(self, cog: 'EventManagement', title: str, start_time: datetime.datetime, nearby_events: List[dict]):
        super().__init__()
        self.cog = cog
        self.title = title
        self.start_time = start_time
        self.nearby_events = nearby_events
    
    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            event = await self.cog.create_calendar_event(self.title, self.start_time)
            
            # Get the event URL
            event_url = event.get('htmlLink', '')
            
            embed = discord.Embed(
                title="✅ Event Created Successfully",
                color=discord.Color.green(),
                timestamp=self.start_time
            )
            
            embed.add_field(
                name="Event Details",
                value=(
                    f"**[{self.title}]({event_url})**\n"
                    f"Start: <t:{int(self.start_time.timestamp())}:F>\n"
                    f"End: <t:{int((self.start_time + timedelta(hours=8)).timestamp())}:F>"
                ),
                inline=False
            )
            
            embed.add_field(
                name="Note",
                value="Staff will be notified of this event within 5 minutes.",
                inline=False
            )
            
            if event_url:
                embed.add_field(
                    name="Calendar Link",
                    value=f"[View in Google Calendar]({event_url})",
                    inline=False
                )

            await interaction.response.edit_message(
                embed=embed,
                view=None
            )
        except Exception as e:
            await interaction.response.edit_message(
                content=f"Error creating event: {str(e)}",
                embed=None,
                view=None
            )
    
    @discord.ui.button(label="Edit", style=discord.ButtonStyle.primary)
    async def edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = EventModal(self.cog)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="Event creation cancelled.",
            embed=None,
            view=None
        )

class EventManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = bot.config
    
    @app_commands.command(
        name="add-game",
        description="Schedule a new game/event"
    )
    async def add_game(self, interaction: discord.Interaction):
        modal = EventModal(self)
        await interaction.response.send_modal(modal)
    
    @app_commands.command(
        name="add-event",
        description="Schedule a new game/event"
    )
    async def add_event(self, interaction: discord.Interaction):
        modal = EventModal(self)
        await interaction.response.send_modal(modal)
    
    @app_commands.command(
        name="upcoming",
        description="Show the next 5 upcoming events"
    )
    async def upcoming_events(self, interaction: discord.Interaction):
        await interaction.response.defer()  # For longer processing time

        try:
            creds = await self.get_credentials()
            if not creds:
                await interaction.followup.send(
                    "Unable to access calendar. Please contact the bot owner.",
                    ephemeral=True
                )
                return

            service = build('calendar', 'v3', credentials=creds)
            
            # Get current time in EST
            est = pytz.timezone('US/Eastern')
            now = datetime.datetime.now(est)

            # Get the next 5 events
            events_result = service.events().list(
                calendarId=self.config.google_calendar_id,
                timeMin=now.isoformat(),
                maxResults=5,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])

            if not events:
                await interaction.followup.send(
                    "No upcoming events found.",
                    ephemeral=True
                )
                return

            # Create the main embed
            embed = discord.Embed(
                title="📅 Upcoming Events",
                description="The next 5 scheduled events",
                color=discord.Color.blue(),
                timestamp=now
            )

            # Add events to the embed
            for i, event in enumerate(events, 1):
                start = datetime.datetime.fromisoformat(
                    event['start'].get('dateTime', event['start'].get('date'))
                )
                end = datetime.datetime.fromisoformat(
                    event['end'].get('dateTime', event['end'].get('date'))
                )
                event_url = event.get('htmlLink', '')

                is_now = start <= now <= end
                
                time_until = int(start.timestamp()) - int(now.timestamp())
                if time_until > 0:
                    relative_time = f"Starts <t:{int(start.timestamp())}:R>"
                else:
                    relative_time = "Happening now!"

                status_emoji = "🟢" if is_now else "⏳"
                field_name = f"{status_emoji} Event {i}"

                field_value = (
                    f"**Title:** [{event['summary']}]({event_url})\n"
                    f"**Start:** <t:{int(start.timestamp())}:F>\n"
                    f"**End:** <t:{int(end.timestamp())}:F>\n"
                    f"**Status:** {relative_time}"
                )

                if 'description' in event and event['description'].strip():
                    desc = event['description']
                    if len(desc) > 100:
                        desc = desc[:97] + "..."
                    field_value += f"\n**Details:** {desc}"

                embed.add_field(
                    name=field_name,
                    value=field_value,
                    inline=False
                )

            # Add footer with timezone info
            embed.set_footer(text=f"All times shown in your local timezone • {len(events)} events found")

            # Always create a view, and it will handle if there are more events
            view = UpcomingEventsView(self, events_result.get('nextPageToken'))

            await interaction.followup.send(
                embed=embed,
                view=view
            )

        except Exception as e:
            print(f"Error fetching upcoming events: {e}")
            await interaction.followup.send(
                "An error occurred while fetching events. Please try again later.",
                ephemeral=True
            )
    
    async def get_credentials(self):
        try:
            with open('token.json', 'r') as token:
                token_data = json.load(token)
                return Credentials.from_authorized_user_info(token_data)
        except Exception as e:
            print(f"Error loading credentials: {e}")
            return None
    
    async def get_nearby_events(self, start_time: datetime.datetime) -> List[dict]:
        try:
            creds = await self.get_credentials()
            if not creds:
                return []
            
            service = build('calendar', 'v3', credentials=creds)
            
            time_min = (start_time - timedelta(hours=8)).isoformat()
            time_max = (start_time + timedelta(hours=8)).isoformat()
            
            events_result = service.events().list(
                calendarId=self.config.google_calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            return events_result.get('items', [])
        except Exception as e:
            print(f"Error getting nearby events: {e}")
            return []
    
    def format_nearby_events(self, events: List[dict], new_event_time: datetime.datetime) -> str:
        formatted = []
        for event in sorted(events, key=lambda x: x['start'].get('dateTime', x['start'].get('date'))):
            start = datetime.datetime.fromisoformat(
                event['start'].get('dateTime', event['start'].get('date'))
            )
            end = datetime.datetime.fromisoformat(
                event['end'].get('dateTime', event['end'].get('date'))
            )
            formatted.append(
                f"**{event['summary']}**\n"
                f"Start: <t:{int(start.timestamp())}:F>\n"
                f"End: <t:{int(end.timestamp())}:F>"
            )
        return "\n\n".join(formatted) if formatted else "No nearby events"
    
    def check_overlaps(self, new_time: datetime.datetime, events: List[dict]) -> bool:
        new_end = new_time + timedelta(hours=8)
        for event in events:
            event_start = datetime.datetime.fromisoformat(
                event['start'].get('dateTime', event['start'].get('date'))
            )
            event_end = event_start + timedelta(hours=8)
            
            if (new_time <= event_end and new_end >= event_start):
                return True
        return False
    
    async def create_calendar_event(self, title: str, start_time: datetime.datetime):
        creds = await self.get_credentials()
        if not creds:
            raise Exception("Unable to load credentials")
        
        service = build('calendar', 'v3', credentials=creds)
        
        end_time = start_time + timedelta(hours=8)
        
        event = {
            'summary': title,
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': 'America/New_York',
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': 'America/New_York',
            }
        }
        
        return service.events().insert(
            calendarId=self.config.google_calendar_id,
            body=event
        ).execute()

class UpcomingEventsView(discord.ui.View):
    def __init__(self, cog: 'EventManagement', next_page_token: str = None):
        super().__init__()
        self.cog = cog
        self.current_page = 0
        self.next_page_token = next_page_token
        
        # Disable the "Next" button if there's no next page
        if not next_page_token:
            self.next_page.disabled = True
        
        # Disable the "Previous" button on the first page
        self.prev_page.disabled = True

    @discord.ui.button(label="Previous 5", style=discord.ButtonStyle.secondary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            await self.update_events(interaction)
        else:
            await interaction.response.send_message(
                "You're already on the first page!",
                ephemeral=True
            )

    @discord.ui.button(label="Next 5", style=discord.ButtonStyle.primary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page += 1
        await self.update_events(interaction)

    async def update_events(self, interaction: discord.Interaction):
        try:
            creds = await self.cog.get_credentials()
            if not creds:
                await interaction.response.send_message(
                    "Unable to access calendar. Please contact the bot owner.",
                    ephemeral=True
                )
                return

            service = build('calendar', 'v3', credentials=creds)
            
            est = pytz.timezone('US/Eastern')
            now = datetime.datetime.now(est)

            # Get events using the page token
            events_result = service.events().list(
                calendarId=self.cog.config.google_calendar_id,
                timeMin=now.isoformat(),
                maxResults=5,
                pageToken=self.next_page_token,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])
            self.next_page_token = events_result.get('nextPageToken')

            if not events:
                await interaction.response.edit_message(
                    content="No more events found.",
                    embed=None,
                    view=None
                )
                return

            embed = discord.Embed(
                title=f"📅 Upcoming Events (Page {self.current_page + 1})",
                description="Next 5 scheduled events",
                color=discord.Color.blue(),
                timestamp=now
            )

            for i, event in enumerate(events, 1):
                start = datetime.datetime.fromisoformat(
                    event['start'].get('dateTime', event['start'].get('date'))
                )
                end = datetime.datetime.fromisoformat(
                    event['end'].get('dateTime', event['end'].get('date'))
                )

                is_now = start <= now <= end
                
                time_until = int(start.timestamp()) - int(now.timestamp())
                if time_until > 0:
                    relative_time = f"Starts <t:{int(start.timestamp())}:R>"
                else:
                    relative_time = "Happening now!"

                status_emoji = "🟢" if is_now else "⏳"
                field_name = f"{status_emoji} Event {i}: {event['summary']}"

                field_value = (
                    f"**Start:** <t:{int(start.timestamp())}:F>\n"
                    f"**End:** <t:{int(end.timestamp())}:F>\n"
                    f"**Status:** {relative_time}"
                )

                if 'description' in event and event['description'].strip():
                    desc = event['description']
                    if len(desc) > 100:
                        desc = desc[:97] + "..."
                    field_value += f"\n**Details:** {desc}"

                embed.add_field(
                    name=field_name,
                    value=field_value,
                    inline=False
                )

            embed.set_footer(text=f"All times shown in your local timezone • Page {self.current_page + 1}")

            # Update button states
            self.prev_page.disabled = self.current_page == 0
            self.next_page.disabled = not self.next_page_token

            await interaction.response.edit_message(
                embed=embed,
                view=self
            )

        except Exception as e:
            print(f"Error updating events: {e}")
            await interaction.response.send_message(
                "An error occurred while fetching events. Please try again later.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(EventManagement(bot))