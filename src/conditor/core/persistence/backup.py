import json
from pathlib import Path
from typing import Any, List, Dict
import asyncio
import discord
from ..planner.models import BuildPlan, BuildStep, StepType


def export_plan(plan: BuildPlan, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2), encoding='utf-8')


def import_plan(path: Path) -> BuildPlan:
    data = json.loads(path.read_text(encoding='utf-8'))
    plan = BuildPlan(name=data.get('name', 'imported'))
    for s in data.get('steps', []):
        stype = StepType(s.get('type'))
        step = BuildStep(id=s.get('id'), type=stype, payload=s.get('payload', {}), retry_policy=s.get('retry_policy', {}), estimated_delay=s.get('estimated_delay', 0.0))
        plan.add_step(step)
    return plan


def snapshot_guild_to_plan(guild: Any, name: str = None) -> BuildPlan:
    """Create a replayable BuildPlan from a guild's current structure.

    This is a shallow snapshot: roles, categories, channels, and permissions placeholders.
    """
    if name is None:
        name = f"backup-{guild.id}"
    plan = BuildPlan(name=name)

    # roles (ordered by position)
    for r in sorted(guild.roles, key=lambda x: x.position):
        payload = {"name": r.name}
        plan.add_step(BuildStep(id=f"role-{r.id}", type=StepType.CREATE_ROLE, payload=payload, estimated_delay=0.2))

    # categories
    for c in guild.categories:
        plan.add_step(BuildStep(id=f"cat-{c.id}", type=StepType.CREATE_CATEGORY, payload={"name": c.name}, estimated_delay=0.3))

    # channels
    for ch in guild.channels:
        # map minimal channel info
        payload = {"name": ch.name, "category": ch.category.name if ch.category else None, "type": "text" if getattr(ch, 'type', None) is None else 'text'}
        plan.add_step(BuildStep(id=f"chan-{ch.id}", type=StepType.CREATE_CHANNEL, payload=payload, estimated_delay=0.2))

    # add a metadata registration
    plan.add_step(BuildStep(id=f"meta-{guild.id}", type=StepType.REGISTER_METADATA, payload={"guild_id": guild.id, "name": guild.name}, estimated_delay=0.0))

    return plan


async def snapshot_guild_to_plan_async(guild: discord.Guild, name: str = None, messages_per_channel: int = 10) -> BuildPlan:
    """Create a more complete, replayable BuildPlan from a guild's current structure.

    This async variant gathers recent messages from text channels and includes channel permission overwrites.
    """
    if name is None:
        name = f"backup-{guild.id}"
    plan = BuildPlan(name=name)

    # roles (ordered by position)
    for r in sorted(guild.roles, key=lambda x: x.position):
        payload = {"name": r.name, "color": f"#{r.colour.value:06x}" if getattr(r, 'colour', None) else None}
        plan.add_step(BuildStep(id=f"role-{r.id}", type=StepType.CREATE_ROLE, payload=payload, estimated_delay=0.2))

    # categories
    for c in guild.categories:
        plan.add_step(BuildStep(id=f"cat-{c.id}", type=StepType.CREATE_CATEGORY, payload={"name": c.name}, estimated_delay=0.3))

    # channels and overwrites
    for ch in guild.channels:
        ch_type = 'text'
        if isinstance(ch, discord.VoiceChannel):
            ch_type = 'voice'
        elif isinstance(ch, discord.StageChannel):
            ch_type = 'stage'
        elif getattr(ch, 'is_news', False):
            ch_type = 'announcement'

        payload = {"name": ch.name, "category": ch.category.name if ch.category else None, "type": ch_type}

        # collect overwrites as role_name -> {allow:[perm], deny:[perm]}
        overwrites: Dict[str, Dict[str, List[str]]] = {}
        for target, ow in ch.overwrites.items():
            if isinstance(target, discord.Role):
                allow, deny = [], []
                for attr, val in vars(ow).items():
                    if attr.startswith('_'):
                        continue
                    if val is True:
                        allow.append(attr)
                    elif val is False:
                        deny.append(attr)
                overwrites[target.name] = {"allow": allow, "deny": deny}
        if overwrites:
            payload['overwrites'] = overwrites

        plan.add_step(BuildStep(id=f"chan-{ch.id}", type=StepType.CREATE_CHANNEL, payload=payload, estimated_delay=0.2))

        # capture recent messages for text channels
        if getattr(ch, 'history', None) and ch_type == 'text':
            messages = []
            try:
                async for m in ch.history(limit=messages_per_channel, oldest_first=True):
                    # avoid attachments for now; capture author and content
                    messages.append({
                        'author_name': getattr(m.author, 'display_name', str(m.author)),
                        'content': m.content,
                        'created_at': m.created_at.isoformat() if getattr(m, 'created_at', None) else None,
                    })
            except Exception:
                messages = []

            for idx, msg in enumerate(messages):
                payload_msg = {"channel": ch.name, "content": msg['content'], "use_webhook": True, "author_name": msg['author_name']}
                plan.add_step(BuildStep(id=f"msg-{ch.id}-{idx}", type=StepType.POST_MESSAGE, payload=payload_msg, estimated_delay=0.05))

    # add a metadata registration
    plan.add_step(BuildStep(id=f"meta-{guild.id}", type=StepType.REGISTER_METADATA, payload={"guild_id": guild.id, "name": guild.name}, estimated_delay=0.0))

    return plan
