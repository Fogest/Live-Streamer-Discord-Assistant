# cogs/event_management.py
import discord
from discord import app_commands
from discord.ext import commands
import datetime
from datetime import timedelta
import pytz
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from typing import List, Optional  # Added List import

class EventManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = bot.config
        
    @app_commands.command(name="add-game", description="Schedule a new game/event")
    @app_commands.describe(
        title="The title of the game/event",
        time="Start time in EST (format: YYYY-MM-DD HH:MM)"
    )
    async def add_game(self, interaction: discord.Interaction, title: str, time: str):
        await self.show_event_modal(interaction, title, time)
        
    @app_commands.command(name="add-event")
    async def add_event(self, interaction: discord.Interaction, title: str, time: str):
        await self.add_game(interaction, title, time)
        
    async def show_event_modal(self, interaction: discord.Interaction, title: str, time: str):
        class EventModal(discord.ui.Modal):
            def __init__(self):
                super().__init__(title="Schedule Game/Event")
                self.add_item(discord.ui.TextInput(
                    label="Title",
                    placeholder="Enter game/event title",
                    default=title,
                    max_length=100
                ))
                self.add_item(discord.ui.TextInput(
                    label="Start Time (EST)",
                    placeholder="YYYY-MM-DD HH:MM",
                    default=time
                ))
                
            async def on_submit(self, interaction: discord.Interaction):
                try:
                    est = pytz.timezone('US/Eastern')
                    start_time = datetime.datetime.strptime(
                        self.children[1].value,
                        "%Y-%m-%d %H:%M"
                    ).replace(tzinfo=est)
                    
                    if start_time < datetime.datetime.now(est):
                        await interaction.response.send_message(
                            "Event time must be in the future!",
                            ephemeral=True
                        )
                        return
                        
                    # Get nearby events
                    nearby_events = await self.get_nearby_events(start_time)
                    
                    # Create confirmation view
                    view = EventConfirmationView(
                        self.children[0].value,
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
                        value=f"**{self.children[0].value}**\n"
                              f"<t:{int(start_time.timestamp())}:F>",
                        inline=False
                    )
                    
                    if nearby_events:
                        embed.add_field(
                            name="Nearby Events",
                            value=self.format_nearby_events(nearby_events, start_time),
                            inline=False
                        )
                        
                        # Check for overlaps
                        overlaps = self.check_overlaps(start_time, nearby_events)
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
                        "Invalid time format! Use YYYY-MM-DD HH:MM",
                        ephemeral=True
                    )
                    
            async def get_nearby_events(self, start_time):
                creds = Credentials.from_authorized_user_file('token.json')
                service = build('calendar', 'v3', credentials=creds)
                
                time_min = (start_time - timedelta(hours=8)).isoformat()
                time_max = (start_time + timedelta(hours=8)).isoformat()
                
                events_result = service.events().list(
                    calendarId=self.bot.config.google_calendar_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()
                
                return events_result.get('items', [])
                
            def format_nearby_events(self, events, new_event_time):
                formatted = []
                for event in events:
                    start = datetime.datetime.fromisoformat(
                        event['start'].get('dateTime', event['start'].get('date'))
                    )
                    formatted.append(
                        f"**{event['summary']}**\n"
                        f"<t:{int(start.timestamp())}:F>"
                    )
                return "\n\n".join(formatted)
                
            def check_overlaps(self, new_time, events):
                new_end = new_time + timedelta(hours=8)
                for event in events:
                    event_start = datetime.datetime.fromisoformat(
                        event['start'].get('dateTime', event['start'].get('date'))
                    )
                    event_end = event_start + timedelta(hours=8)
                    
                    if (new_time <= event_end and new_end >= event_start):
                        return True
                return False
                
        await interaction.response.send_modal(EventModal())

class EventConfirmationView(discord.ui.View):
    def __init__(self, title: str, start_time: datetime.datetime, nearby_events: List[dict]):
        super().__init__()
        self.title = title
        self.start_time = start_time
        self.nearby_events = nearby_events
        
    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            creds = Credentials.from_authorized_user_file('token.json')
            service = build('calendar', 'v3', credentials=creds)
            
            end_time = self.start_time + timedelta(hours=8)
            
            event = {
                'summary': self.title,
                'start': {
                    'dateTime': self.start_time.isoformat(),
                    'timeZone': 'America/New_York',
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': 'America/New_York',
                }
            }
            
            event = service.events().insert(
                calendarId=self.bot.config.google_calendar_id,
                body=event
            ).execute()
            
            await interaction.response.edit_message(
                content="Event has been created!",
                embed=None,
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
        await self.show_event_modal(
            interaction,
            self.title,
            self.start_time.strftime("%Y-%m-%d %H:%M")
        )
        
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="Event creation cancelled.",
            embed=None,
            view=None
        )

async def setup(bot):
    await bot.add_cog(EventManagement(bot))