import json
from pathlib import Path
from typing import Optional
import discord
from discord.ext import commands

from src.conditor.core.intent.models import load_template, discover_and_merge
from src.conditor.core.planner import compile_spec_to_plan, compile_from_files
from src.conditor.core.executor import Executor, default_noop_handler
from src.conditor.core.safety import validate_plan, permission_sanity_checks


class EngineCog(commands.Cog):
    """Cog exposing commands to compile and run plans (safe simulation using noop handler)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        base = Path(__file__).parent.parent.parent
        self.base_path = base
        self.executor = Executor(storage_dir=base / 'data' / 'runtime')

    @commands.command(name="plan_preview")
    @commands.has_guild_permissions(administrator=True)
    async def plan_preview(self, ctx: commands.Context, template_name: Optional[str] = None):
        """Compile a plan from templates/questionnaires and preview its steps."""
        if template_name:
            tpl_path = self.base_path / 'data' / 'templates' / f"{template_name}.json"
            if not tpl_path.exists():
                await ctx.send(f"Template not found: {template_name}")
                return
            spec = discover_and_merge(self.base_path)
            # merge template into spec extras for deterministic plan
            try:
                tpl = load_template(tpl_path)
                spec.extras.setdefault('templates', []).append(tpl)
            except Exception:
                pass
        else:
            spec = discover_and_merge(self.base_path)

        plan = compile_spec_to_plan(spec, name=f"preview-{template_name or 'auto'}")
        ok, errs = validate_plan(plan)
        if not ok:
            await ctx.send(f"Plan validation failed: {errs}")
            return

        # prepare human readable summary
        lines = [f"Plan: {plan.name} (steps={len(plan.steps)})"]
        for i, s in enumerate(plan.steps):
            lines.append(f"{i+1}. {s.type.value} -> {s.payload}")
        blob = "\n".join(lines)
        # send a code block with the plan
        await ctx.send(f"```\n{blob}\n```")

    @commands.command(name="plan_run_sample")
    @commands.has_guild_permissions(administrator=True)
    async def plan_run_sample(self, ctx: commands.Context, template_name: Optional[str] = None):
        """Compile a plan and execute it locally with a noop handler (no Discord API calls)."""
        spec = discover_and_merge(self.base_path)
        if template_name:
            tpl_path = self.base_path / 'data' / 'templates' / f"{template_name}.json"
            if tpl_path.exists():
                try:
                    tpl = load_template(tpl_path)
                    spec.extras.setdefault('templates', []).append(tpl)
                except Exception:
                    pass
        plan = compile_spec_to_plan(spec, name=f"sample-{template_name or 'auto'}")

        ok, errs = validate_plan(plan)
        if not ok:
            await ctx.send(f"Plan validation failed: {errs}")
            return
        ok2, errs2 = permission_sanity_checks(plan)
        if not ok2:
            await ctx.send(f"Permission sanity failed: {errs2}")
            return

        # run plan using the noop handler and report summary
        state = self.executor.run_plan(plan, default_noop_handler, resume=False)
        # return summary
        successes = sum(1 for s in state.get('steps', {}).values() if s.get('status') == 'success')
        fails = sum(1 for s in state.get('steps', {}).values() if s.get('status') == 'failed')
        await ctx.send(f"Sample plan executed. successes={successes} failed={fails}")


async def setup(bot: commands.Bot):
    await bot.add_cog(EngineCog(bot))
