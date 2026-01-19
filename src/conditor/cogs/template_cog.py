import json
import difflib
from pathlib import Path
from datetime import datetime
from discord.ext import commands
import discord

from .. import storage

ROOT = Path(__file__).resolve().parents[3]
AUDIT_DIR = ROOT / "data" / "audit"
AUDIT_DIR.mkdir(parents=True, exist_ok=True)


class TemplateEditModal(discord.ui.Modal):
    def __init__(self, name: str, initial: str = ""):
        super().__init__(title=f"Edit Template — {name}")
        self.template_name = name
        self.content = discord.ui.TextInput(label="Template JSON", style=discord.TextStyle.long,
                                            default=initial, placeholder="Paste template JSON here...",
                                            required=True, max_length=20000)
        self.add_item(self.content)

    async def on_submit(self, interaction: discord.Interaction):
        new_text = self.content.value
        try:
            json.loads(new_text)
        except Exception as exc:
            await interaction.response.send_message(f"Invalid JSON: {exc}", ephemeral=True)
            return

        # load existing for diff
        existing = storage.load_template(self.template_name) or ""
        diff_lines = list(difflib.unified_diff(
            existing.splitlines(keepends=True), new_text.splitlines(keepends=True),
            fromfile="existing", tofile="new"))
        diff_text = "".join(diff_lines)
        if not diff_text:
            await interaction.response.send_message("No changes detected.", ephemeral=True)
            return

        if len(diff_text) > 1500:
            diff_text = diff_text[:1500] + "\n...truncated..."

        # present a confirm/cancel view with the diff
        view = ConfirmSaveView(self.template_name, new_text, existing, initiator_id=interaction.user.id)
        await interaction.response.send_message(content=f"Preview diff for `{self.template_name}`:\n```diff\n{diff_text}\n```",
                                                ephemeral=True, view=view)


class ConfirmSaveView(discord.ui.View):
    def __init__(self, name: str, new_text: str, existing_text: str, initiator_id: int, timeout: float = 300.0):
        super().__init__(timeout=timeout)
        self.template_name = name
        self.new_text = new_text
        self.existing_text = existing_text
        self.initiator_id = initiator_id

    async def _log_audit(self, user: discord.User, guild_id: int, action: str):
        rec = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "user_id": user.id,
            "user_name": str(user),
            "guild_id": guild_id,
            "template": self.template_name,
            "action": action,
        }
        f = AUDIT_DIR / "templates.log"
        with f.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    @discord.ui.button(label="Confirm Save", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.initiator_id:
            await interaction.response.send_message("Only the editor may confirm this save.", ephemeral=True)
            return
        # save and acknowledge
        storage.save_template(self.template_name, self.new_text)
        await self._log_audit(interaction.user, interaction.guild.id if interaction.guild else None, "save")
        await interaction.response.send_message(f"Template '{self.template_name}' saved.", ephemeral=True)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.initiator_id:
            await interaction.response.send_message("Only the editor may cancel.", ephemeral=True)
            return
        await interaction.response.send_message(f"Edit cancelled for '{self.template_name}'.", ephemeral=True)
        self.stop()


class TemplateCog(commands.Cog):
    """Manage templates stored in the sqlite DB via commands and a modal editor."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="template_list")
    @commands.has_guild_permissions(administrator=True)
    async def template_list(self, ctx: commands.Context):
        names = storage.list_templates()
        if not names:
            await ctx.send("No templates in database.")
            return
        await ctx.send("Templates:\n" + "\n".join(names))

    @commands.command(name="template_save")
    @commands.has_guild_permissions(administrator=True)
    async def template_save(self, ctx: commands.Context, name: str, *, file_path: str = None):
        """Save a template into the DB. Usage: !template_save name data/templates/file.json"""
        content = None
        if file_path:
            p = Path(file_path)
            if not p.exists():
                await ctx.send(f"File not found: {file_path}")
                return
            content = p.read_text(encoding="utf-8")
        else:
            await ctx.send("No file path provided. Attach a file or pass a path.")
            return

        try:
            # validate JSON
            json.loads(content)
        except Exception as exc:
            await ctx.send(f"Invalid JSON: {exc}")
            return

        storage.save_template(name, content)
        await ctx.send(f"Template '{name}' saved to DB.")

    @commands.command(name="template_get")
    @commands.has_guild_permissions(administrator=True)
    async def template_get(self, ctx: commands.Context, name: str):
        content = storage.load_template(name)
        if not content:
            await ctx.send("Template not found.")
            return
        import io

        bio = io.BytesIO()
        bio.write(content.encode("utf-8"))
        bio.seek(0)
        await ctx.send(file=discord.File(fp=bio, filename=f"{name}.json"))

    @commands.hybrid_command(name="template_edit", with_app_command=True)
    @commands.has_guild_permissions(administrator=True)
    async def template_edit(self, ctx: commands.Context, name: str):
        """Open an in-Discord modal to edit a template's JSON (slash/hybrid compatible)."""
        content = storage.load_template(name) or ""
        modal = TemplateEditModal(name, initial=content)
        # `send_modal` is available on both contexts and interactions
        await ctx.send_modal(modal)


async def setup(bot: commands.Bot):
    storage.init_db()
    await bot.add_cog(TemplateCog(bot))
