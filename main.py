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
        super().__init__(command_prefix="!", intents=intents)
        self.config = BotConfig.load()
        
    async def setup_hook(self):
        await self.load_extension("cogs.calendar_sync")
        await self.load_extension("cogs.event_management")
        await self.load_extension("cogs.settings")
        await self.tree.sync()
        
    async def on_ready(self):
        print(f"Logged in as {self.user}")

async def main():
    bot = CalendarBot()
    async with bot:
        await bot.start(os.getenv("DISCORD_TOKEN"))

if __name__ == "__main__":
    asyncio.run(main())