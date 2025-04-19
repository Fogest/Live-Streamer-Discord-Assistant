# cogs/role_buttons.py
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, Dict, List

class RoleButton(discord.ui.Button):
    def __init__(self, role_id: int, label: str, requires_mod: bool = False):
        super().__init__(
            style=discord.ButtonStyle.primary,
            label=label,
            custom_id=f"role_toggle_{role_id}"
        )
        self.role_id = role_id
        self.requires_mod = requires_mod

    async def callback(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message(
                "This button can only be used in a server!",
                ephemeral=True
            )
            return

        # Get the role
        role = interaction.guild.get_role(self.role_id)
        if not role:
            await interaction.response.send_message(
                "The configured role no longer exists!",
                ephemeral=True
            )
            return

        # Check if user has required permissions for restricted roles
        if self.requires_mod and not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message(
                "❌ You need Moderator permissions to toggle this role!",
                ephemeral=True
            )
            return

        # Toggle the role
        member = interaction.guild.get_member(interaction.user.id)
        if role in member.roles:
            await member.remove_roles(role)
            message = f"✅ Removed the {role.name} role"
        else:
            await member.add_roles(role)
            message = f"✅ Added the {role.name} role"

        await interaction.response.send_message(message, ephemeral=True)

class RolePersistentView(discord.ui.View):
    def __init__(self, role_id: int, label: str, requires_mod: bool = False):
        super().__init__(timeout=None)
        self.add_item(RoleButton(role_id, label, requires_mod))

class RoleButtons(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = bot.config
        
    # Removed cog_load and generate_button command as they related to removed features

async def setup(bot):
    await bot.add_cog(RoleButtons(bot))
