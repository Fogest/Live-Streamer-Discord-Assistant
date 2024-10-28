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
        super().__init__(
            command_prefix="!",
            intents=intents,
            description="A Discord bot for managing events with Google Calendar integration"
        )
        self.config = BotConfig.load()
        self.owner_id = int(os.getenv("OWNER_ID", "0"))
        
    async def setup_hook(self):
        await self.load_extension("cogs.calendar_sync")
        await self.load_extension("cogs.event_management")
        await self.load_extension("cogs.settings")
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