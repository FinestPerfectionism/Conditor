from typing import Any, Dict, Optional
import json
from pathlib import Path
import discord
from ...rate_limiter import run_with_rate_limit
from ...permissions import apply_channel_overwrites, ensure_bot_role_position
from ..planner.models import BuildStep, StepType


def _parse_color_int(s: str):
    if not s:
        return None
    try:
        if isinstance(s, int):
            return s
        if s.startswith('#'):
            s = s[1:]
        return int(s, 16)
    except Exception:
        return None


def make_discord_handler(bot: discord.Client, guild: discord.Guild, storage_dir: Optional[Path] = None, namespace: Optional[str] = None):
    """Return an async handler that executes BuildSteps against `guild`.

    The handler keeps internal maps of created resources keyed by step id and by name
    so subsequent steps can reliably reference them.
    """
    created_roles = {}
    created_categories = {}
    created_channels = {}

    # persistent resource map
    storage_dir = None
    map_path = None
    persistent: Dict[str, Dict[str, Dict[str, Any]]] = {"roles": {}, "categories": {}, "channels": {}}

    def _init_persistent(sd: Optional[Path], ns: Optional[str] = None):
        nonlocal storage_dir, map_path, persistent
        if sd is None:
            return
        storage_dir = Path(sd)
        storage_dir.mkdir(parents=True, exist_ok=True)
        # sanitize namespace for filename
        safe_ns = None
        if ns:
            safe_ns = ''.join(c for c in ns if c.isalnum() or c in ('_', '-')).strip()
            if safe_ns == '':
                safe_ns = None
        name_part = f"_{safe_ns}" if safe_ns else ''
        map_path = storage_dir / f"resource_map_{guild.id}{name_part}.json"
        if map_path.exists():
            try:
                persistent = json.loads(map_path.read_text(encoding='utf-8'))
            except Exception:
                persistent = {"roles": {}, "categories": {}, "channels": {}}

    # initialize persistent store from provided args
    _init_persistent(storage_dir, namespace)
    

    async def handler(step: BuildStep) -> Dict[str, Any]:
        t = step.type
        payload = step.payload or {}
        gid = guild.id

        # helpers to resolve references
        def resolve_role(key):
            # key may be role name or a step id
            if key is None:
                return None
            # try step id mapping
            if key in created_roles:
                return created_roles[key]
            # try by name in guild
            role = discord.utils.get(guild.roles, name=key)
            return role

        def resolve_category(key):
            if key is None:
                return None
            if key in created_categories:
                return created_categories[key]
            cat = discord.utils.get(guild.categories, name=key)
            return cat

        if t == StepType.CREATE_ROLE:
            name = payload.get('name')
            color = payload.get('color') or payload.get('colour') or payload.get('colour_int')
            parsed = _parse_color_int(color) if color else None

            # if persisted mapping exists for this step, return it
            if step.id in persistent.get('roles', {}):
                entry = persistent['roles'][step.id]
                return {'role_id': entry.get('id'), 'name': entry.get('name')}

            async def _create():
                kwargs = {'name': name, 'reason': 'Conditor build'}
                if parsed is not None:
                    kwargs['colour'] = discord.Colour(parsed)
                return await guild.create_role(**kwargs)

            role = await run_with_rate_limit(gid, _create)
            # register mappings
            created_roles[step.id] = role
            created_roles[role.name] = role

            # persist mapping with richer metadata (color, permissions)
            role_meta = {'id': getattr(role, 'id', None), 'name': getattr(role, 'name', None)}
            try:
                col = getattr(role, 'colour', None) or getattr(role, 'color', None)
                if col is not None and hasattr(col, 'value'):
                    role_meta['color'] = f"#{int(col.value):06x}"
            except Exception:
                pass
            try:
                perms = getattr(role, 'permissions', None)
                if perms is not None and hasattr(perms, 'value'):
                    role_meta['permissions'] = int(perms.value)
            except Exception:
                pass
            persistent.setdefault('roles', {})[step.id] = role_meta
            if map_path:
                try:
                    map_path.write_text(json.dumps(persistent, ensure_ascii=False, indent=2), encoding='utf-8')
                except Exception:
                    pass

            return {'role_id': getattr(role, 'id', None), 'name': getattr(role, 'name', None)}

        if t == StepType.CREATE_CATEGORY:
            name = payload.get('name')

            # if persisted mapping exists for this step, return it
            if step.id in persistent.get('categories', {}):
                entry = persistent['categories'][step.id]
                return {'category_id': entry.get('id'), 'name': entry.get('name')}

            async def _create():
                return await guild.create_category(name)

            cat = await run_with_rate_limit(gid, _create)
            created_categories[step.id] = cat
            created_categories[cat.name] = cat

            # persist category with metadata
            cat_meta = {'id': getattr(cat, 'id', None), 'name': getattr(cat, 'name', None)}
            try:
                topic = getattr(cat, 'topic', None)
                if topic:
                    cat_meta['topic'] = topic
            except Exception:
                pass
            persistent.setdefault('categories', {})[step.id] = cat_meta
            if map_path:
                try:
                    map_path.write_text(json.dumps(persistent, ensure_ascii=False, indent=2), encoding='utf-8')
                except Exception:
                    pass

            return {'category_id': getattr(cat, 'id', None), 'name': getattr(cat, 'name', None)}

        if t == StepType.CREATE_CHANNEL:
            name = payload.get('name')
            ctype = payload.get('type', 'text')
            cat_key = payload.get('category')
            # resolve category by step id or name
            category = resolve_category(cat_key)

            async def _create():
                if ctype == 'text':
                    return await guild.create_text_channel(name, category=category)
                elif ctype == 'voice':
                    return await guild.create_voice_channel(name, category=category)
                elif ctype == 'announcement' or ctype == 'news':
                    return await guild.create_text_channel(name, category=category, news=True)
                else:
                    return await guild.create_text_channel(name, category=category)

            # if persisted mapping exists for this step, return it
            if step.id in persistent.get('channels', {}):
                entry = persistent['channels'][step.id]
                return {'channel_id': entry.get('id'), 'name': entry.get('name')}

            ch = await run_with_rate_limit(gid, _create)
            created_channels[step.id] = ch
            created_channels[ch.name] = ch

            # apply overwrites if payload provides them (resolve role references)
            overwrites = payload.get('overwrites') or payload.get('overrides')
            if overwrites:
                # map role references: if role key references a step id, replace with actual role name
                resolved = {}
                for role_key, od in overwrites.items():
                    role_obj = resolve_role(role_key)
                    if role_obj:
                        resolved[role_obj.name] = od
                try:
                    await apply_channel_overwrites(guild, ch, resolved)
                except Exception:
                    pass

            # persist channel metadata (type, topic, overwrites)
            ch_meta = {'id': getattr(ch, 'id', None), 'name': getattr(ch, 'name', None)}
            try:
                ctype_val = payload.get('type') or ('text' if getattr(ch, 'send', None) else 'channel')
                ch_meta['type'] = ctype_val
            except Exception:
                pass
            try:
                topic = getattr(ch, 'topic', None)
                if topic:
                    ch_meta['topic'] = topic
            except Exception:
                pass
            try:
                if overwrites:
                    ch_meta['overwrites'] = overwrites
            except Exception:
                pass
            persistent.setdefault('channels', {})[step.id] = ch_meta
            if map_path:
                try:
                    map_path.write_text(json.dumps(persistent, ensure_ascii=False, indent=2), encoding='utf-8')
                except Exception:
                    pass
            return {'channel_id': getattr(ch, 'id', None), 'name': getattr(ch, 'name', None)}

        if t == StepType.APPLY_PERMISSIONS:
            overwrites = payload.get('overwrites') or []
            channel_key = payload.get('channel')
            target = None
            if channel_key:
                # channel_key may be step id or name
                if channel_key in created_channels:
                    target = created_channels[channel_key]
                else:
                    target = discord.utils.get(guild.channels, name=channel_key)

            if target:
                # resolve overwrites role keys similarly
                resolved = {}
                for role_key, od in (overwrites.items() if isinstance(overwrites, dict) else enumerate(overwrites)):
                    # if overwrites is a list of dicts
                    if isinstance(overwrites, dict):
                        rkey = role_key
                        odict = od
                    else:
                        # skip unexpected format
                        continue
                    role_obj = resolve_role(rkey)
                    if role_obj:
                        resolved[role_obj.name] = odict
                await apply_channel_overwrites(guild, target, resolved)
                return {'applied_to': getattr(target, 'id', None)}
            else:
                applied = []
                for ch in guild.channels:
                    try:
                        await apply_channel_overwrites(guild, ch, overwrites)
                        applied.append(ch.id)
                    except Exception:
                        continue
                return {'applied_count': len(applied)}

        if t == StepType.POST_MESSAGE:
            channel_key = payload.get('channel')
            content = payload.get('content', '')
            use_webhook = payload.get('use_webhook', False)

            target = None
            if channel_key in created_channels:
                target = created_channels[channel_key]
            else:
                target = discord.utils.get(guild.text_channels, name=channel_key) if channel_key else None
            if not target and channel_key:
                try:
                    cid = int(channel_key)
                    target = guild.get_channel(cid)
                except Exception:
                    target = None

            if target:
                async def _send():
                    return await target.send(content)

                if use_webhook:
                    # attempt to send via webhook for author preservation - best effort
                    try:
                        webhooks = await target.webhooks()
                        if webhooks:
                            wh = webhooks[0]
                            return await run_with_rate_limit(gid, lambda: wh.send(content, username=payload.get('author_name', '')))
                    except Exception:
                        pass
                msg = await run_with_rate_limit(gid, _send)
                return {'message_id': getattr(msg, 'id', None)}
            return {'ok': False, 'reason': 'channel not found'}

        if t == StepType.REGISTER_METADATA:
            return {'metadata': payload}

        return {'ok': False, 'reason': 'unknown step type'}

    return handler
