# cogs/message_management.py
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional

class MessageManagement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @app_commands.command(
        name="say",
        description="Make the bot say something"
    )
    @app_commands.default_permissions(manage_messages=True)
    async def say(
        self,
        interaction: discord.Interaction,
        message: str,
        channel: Optional[discord.TextChannel] = None
    ):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message(
                "❌ You need Moderator permissions to use this command!",
                ephemeral=True
            )
            return
            
        # Use current channel if none specified
        target_channel = channel or interaction.channel
        
        # Check if bot has permission to send messages in target channel
        if not target_channel.permissions_for(interaction.guild.me).send_messages:
            await interaction.response.send_message(
                f"❌ I don't have permission to send messages in {target_channel.mention}!",
                ephemeral=True
            )
            return
            
        try:
            await target_channel.send(message)
            
            # Send confirmation as ephemeral message
            if target_channel != interaction.channel:
                await interaction.response.send_message(
                    f"✅ Message sent in {target_channel.mention}!",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "✅ Message sent!",
                    ephemeral=True
                )
                
        except discord.HTTPException as e:
            await interaction.response.send_message(
                f"❌ Failed to send message: {str(e)}",
                ephemeral=True
            )
            
    @app_commands.command(
        name="announce",
        description="Send an announcement message with optional ping and embed"
    )
    @app_commands.default_permissions(manage_messages=True)
    async def announce(
        self,
        interaction: discord.Interaction,
        message: str,
        channel: Optional[discord.TextChannel] = None,
        title: Optional[str] = None,
        ping_role: Optional[discord.Role] = None,
        color: Optional[str] = None
    ):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message(
                "❌ You need Moderator permissions to use this command!",
                ephemeral=True
            )
            return
          
        if interaction.user.id != self.bot.owner_id:
            await interaction.response.send_message(
                "❌ You need to be the bot owner to use this command!",
                ephemeral=True
            )
            return
            
        # Use current channel if none specified
        target_channel = channel or interaction.channel
        
        # Check if bot has permission to send messages in target channel
        if not target_channel.permissions_for(interaction.guild.me).send_messages:
            await interaction.response.send_message(
                f"❌ I don't have permission to send messages in {target_channel.mention}!",
                ephemeral=True
            )
            return
            
        try:
            # Create embed
            embed = discord.Embed(description=message)
            
            # Add optional title if provided
            if title:
                embed.title = title
                
            # Set color if provided, otherwise use default blue
            if color:
                try:
                    # Handle hex color codes
                    if color.startswith('#'):
                        color_value = int(color[1:], 16)
                    else:
                        color_value = int(color.replace('0x', ''), 16)
                    embed.color = color_value
                except ValueError:
                    embed.color = discord.Color.blue()
            else:
                embed.color = discord.Color.blue()
                
            # Add footer with author info
            embed.set_footer(
                text=f"Announcement by {interaction.user.display_name}",
                icon_url=interaction.user.display_avatar.url
            )
            
            # Prepare ping message if role is provided
            ping_content = f"{ping_role.mention} " if ping_role else ""
            
            # Send the announcement
            await target_channel.send(ping_content, embed=embed)
            
            # Send confirmation as ephemeral message
            if target_channel != interaction.channel:
                await interaction.response.send_message(
                    f"✅ Announcement sent in {target_channel.mention}!",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "✅ Announcement sent!",
                    ephemeral=True
                )
                
        except discord.HTTPException as e:
            await interaction.response.send_message(
                f"❌ Failed to send announcement: {str(e)}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(MessageManagement(bot))