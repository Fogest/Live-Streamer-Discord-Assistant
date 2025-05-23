import discord
from discord.ext import commands
import asyncio
from config import BotConfig
import os
from dotenv import load_dotenv

load_dotenv()

class CalendarBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(
            command_prefix="!",
            intents=intents,
            description="A Discord bot for assisting live streamers with community management and stream notifications."
        )
        self.config = BotConfig.load()
        self.owner_id = int(os.getenv("OWNER_ID", "0"))
        
    async def setup_hook(self):
        # Load Core Cogs
        await self.load_extension("cogs.settings")
        await self.load_extension("cogs.role_buttons")
        await self.load_extension("cogs.message_management")
        await self.load_extension("cogs.youtube_monitor") # Load the new monitor cog
        # await self.load_extension("cogs.youtube_features") # Keep this commented unless needed

        # Set up persistent views
        from cogs.role_buttons import RolePersistentView
        if self.config.daily_summary_role_id:
            self.add_view(RolePersistentView(
                self.config.daily_summary_role_id,
                "Toggle Upcoming Events Notifications"
            ))
        if self.config.event_notification_role_id:
            self.add_view(RolePersistentView(
                self.config.event_notification_role_id,
                "Toggle Event Notifications",
                requires_mod=True
            ))
        
        await self.tree.sync()
        
    async def on_ready(self):
        print(f"Logged in as {self.user}")
        # If owner_id wasn't set in .env, fetch it from Discord
        if self.owner_id == 0:
            app = await self.application_info()
            self.owner_id = app.owner.id
            print(f"Bot owner ID: {self.owner_id}")

async def main():
    bot = CalendarBot()
    async with bot:
        await bot.start(os.getenv("DISCORD_TOKEN"))

if __name__ == "__main__":
    asyncio.run(main())
