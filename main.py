import discord
from discord import app_commands, ui
from discord.ext import commands

TOKEN = "MTQ2MDc3OTgyMDY2ODU1MTI2MQ.GbvWL9.CfZqk63rwQL7rOim95rIhjrpBGrr4aquuiDjV8"

INTENTS = discord.Intents.none()
INTENTS.guilds = True

class Conditor(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=INTENTS,
        )

    async def setup_hook(self) -> None:
        await self.tree.sync()


bot = Conditor()

def guild_owner_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True,
            )
            return False

        if interaction.user.id != guild.owner_id:
            await interaction.response.send_message(
                "Only the server owner can run this command.",
                ephemeral=True,
            )
            return False

        return True

    return app_commands.check(predicate)

class SetupModal(ui.Modal, title="Conditor Server Setup"):
    server_type = ui.TextInput(
        label="Server type",
        placeholder="Community / Gaming / Development / Private",
    )
    roles = ui.TextInput(
        label="Roles (comma-separated)",
        placeholder="Admin, Moderator, Member",
    )
    channels = ui.TextInput(
        label="Channels (comma-separated)",
        placeholder="general, announcements, rules",
    )
    theme = ui.TextInput(
        label="General theme",
        placeholder="Professional, Casual, Minimal",
        required=False,
    )

    def __init__(self) -> None:
        super().__init__()
        self.answers: dict[str, list[str] | str] = {}

    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.answers = {
            "server_type": self.server_type.value,
            "roles": [r.strip() for r in self.roles.value.split(",") if r.strip()],
            "channels": [c.strip() for c in self.channels.value.split(",") if c.strip()],
            "theme": self.theme.value or "Default",
        }

        await interaction.response.send_message(
            "Setup information received.",
            ephemeral=True,
        )

class ConfirmView(ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=120)
        self.confirmed: bool = False

    @ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(
        self, interaction: discord.Interaction, _: ui.Button
    ) -> None:
        self.confirmed = True
        self.stop()
        await interaction.response.send_message(
            "Confirmed. Conditor will proceed.",
            ephemeral=True,
        )

    @ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(
        self, interaction: discord.Interaction, _: ui.Button
    ) -> None:
        self.confirmed = False
        self.stop()
        await interaction.response.send_message(
            "Cancelled. No changes were made.",
            ephemeral=True,
        )

@bot.tree.command(
    name="create",
    description="Configure this server using Conditor.",
)
@guild_owner_only()
async def create(interaction: discord.Interaction) -> None:
    if interaction.guild is None:
        await interaction.response.send_message(
            "This command must be used in a server.",
            ephemeral=True,
        )
        return

    guild: discord.Guild = interaction.guild

    modal = SetupModal()
    await interaction.response.send_modal(modal)
    await modal.wait()

    if not modal.answers:
        return

    answers = modal.answers

    explanation = (
        "**Conditor will perform the following actions:**\n\n"
        "• Delete all existing channels\n"
        "• Delete all existing roles (except @everyone and bot-managed roles)\n"
        "• Create new roles based on your input\n"
        "• Create new text channels based on your input\n\n"
        "**Your choices:**\n"
        f"• Server type: `{answers['server_type']}`\n"
        f"• Theme: `{answers['theme']}`\n"
        f"• Roles: `{', '.join(answers['roles'])}`\n"
        f"• Channels: `{', '.join(answers['channels'])}`\n\n"
        "**Proceed?**"
    )

    view = ConfirmView()
    await interaction.followup.send(
        explanation,
        view=view,
        ephemeral=True,
    )
    await view.wait()

    if not view.confirmed:
        return

    await interaction.followup.send(
        "Applying configuration.",
        ephemeral=True,
    )

    for channel in list(guild.channels):
        try:
            await channel.delete()
        except discord.Forbidden:
            pass

    for role in list(guild.roles):
        if role.is_default() or role.managed:
            continue
        try:
            await role.delete()
        except discord.Forbidden:
            pass
            
    for role_name in answers["roles"]:
        await guild.create_role(
            name=role_name,
            reason="Conditor server setup",
        )

    for channel_name in answers["channels"]:
        await guild.create_text_channel(
            name=channel_name,
            reason="Conditor server setup",
        )

    await interaction.followup.send(
        "Server configuration complete.",
        ephemeral=True,
    )

bot.run(TOKEN)

# This is very, VERY, minimal code -- if it's the worst thing you've ever seen, I don't blame you. Don't worry, obviously improvements are going to be made.
