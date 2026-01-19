from typing import List
from pathlib import Path
import uuid

from .models import BuildPlan, BuildStep, StepType
from ..intent.models import ServerSpec


def _make_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def compile_spec_to_plan(spec: ServerSpec, name: str = 'plan') -> BuildPlan:
    plan = BuildPlan(name=name)

    # Inspect template metadata for heuristic guidance and overrides
    templates = spec.extras.get('templates', []) if getattr(spec, 'extras', None) else []
    chosen_tpl = None
    for t in templates:
        meta = t.get('meta', {})
        if meta.get('official_style'):
            chosen_tpl = t
            break
    if chosen_tpl is None and templates:
        chosen_tpl = templates[0]

    overrides = chosen_tpl.get('overrides', {}) if chosen_tpl else {}
    official = bool(chosen_tpl and chosen_tpl.get('meta', {}).get('official_style'))

    # Roles - allow overrides from template; otherwise use heuristics
    role_defs = overrides.get('roles') if overrides.get('roles') is not None else None
    if role_defs is None:
        if official:
            role_defs = [
                {"name": "Administrator", "profile": "admin", "position": 100},
                {"name": "Moderator", "profile": "moderation", "position": 90},
                {"name": "Member", "profile": "member", "position": 10},
                {"name": "Bots", "profile": "bot", "position": 5},
            ]
            if spec.community_type:
                role_defs.append({"name": f"{spec.community_type.title()}", "position": 50})
            for g in spec.games or []:
                role_defs.append({"name": f"{g.title()} Player", "position": 20})
            if spec.size and spec.size.lower() in ("large", "very large", "huge"):
                role_defs.append({"name": "Veteran", "position": 30})
        else:
            role_defs = []
            if spec.community_type:
                role_defs.append({"name": f"{spec.community_type.title()}"})
            role_defs.extend([{"name": r} for r in (["Admin", "Moderator"] if spec.moderation else ["Admin"])])
            if spec.size == 'large':
                role_defs.append({"name": "Veteran"})

    # create role steps
    for rd in sorted(role_defs, key=lambda r: -r.get("position", 0)):
        payload = {"name": rd.get("name")}
        if rd.get("profile"):
            payload["profile"] = rd.get("profile")
        if rd.get("position"):
            payload["position"] = rd.get("position")
        if rd.get("color"):
            payload["color"] = rd.get("color")
        else:
            # small heuristic color hints
            if payload["name"] and "admin" in payload["name"].lower():
                payload["color"] = "#b02e0c"
            elif payload["name"] and "moderator" in payload["name"].lower():
                payload["color"] = "#0b6e4f"
        plan.add_step(BuildStep(id=_make_id('role'), type=StepType.CREATE_ROLE, payload=payload, estimated_delay=0.25))

    # Categories & Channels - allow template overrides
    cat_defs = overrides.get('categories') if overrides.get('categories') is not None else None
    if cat_defs is None:
        # default categories depending on official flag
        if official:
            cat_defs = [
                {"name": "Information", "channels": [
                    {"name": "welcome", "type": "text", "starter": "Welcome to the server! Please read the rules."},
                    {"name": "rules", "type": "text", "starter": "Be kind. No harassment. Follow Discord TOS."},
                    {"name": "announcements", "type": "announcement", "starter": "Server announcements will appear here."},
                ]},
                {"name": "Community", "channels": [
                    {"name": "general", "type": "text", "starter": "Say hi!"},
                    {"name": "introductions", "type": "text", "starter": "Introduce yourself!"},
                    {"name": "off-topic", "type": "text"},
                ]},
            ]
            if spec.games:
                game_cat = {"name": "Games", "channels": []}
                for g in spec.games:
                    game_cat["channels"].append({"name": f"{g.lower()}-chat", "type": "text"})
                    game_cat["channels"].append({"name": f"{g.lower()}-voice", "type": "voice"})
                cat_defs.append(game_cat)
        else:
            cat_defs = [{"name": "Community"}, {"name": "Info"}]
            if spec.games:
                for g in spec.games:
                    cat_defs.append({"name": f"{g.title()}"})

    # add category/channel steps
    for c in cat_defs:
        cat_id = _make_id('cat')
        plan.add_step(BuildStep(id=cat_id, type=StepType.CREATE_CATEGORY, payload={"name": c.get("name")}, estimated_delay=0.35))
        for ch in c.get("channels", []):
            ch_payload = {"name": ch.get("name"), "category": c.get("name"), "type": ch.get("type", "text")}
            ch_id = _make_id('chan')
            plan.add_step(BuildStep(id=ch_id, type=StepType.CREATE_CHANNEL, payload=ch_payload, estimated_delay=0.25))
            if ch.get("starter"):
                plan.add_step(BuildStep(id=_make_id('post'), type=StepType.POST_MESSAGE, payload={"channel": ch.get("name"), "content": ch.get("starter"), "use_webhook": True}, estimated_delay=0.05))

    # Permissions: default conservative announce channel rule (allow override)
    perm_override = overrides.get('permissions')
    if perm_override is not None:
        plan.add_step(BuildStep(id=_make_id('perm'), type=StepType.APPLY_PERMISSIONS, payload=perm_override, estimated_delay=0.1))
    else:
        overwrites = {"@everyone": {"allow": [], "deny": ["send_messages"]}}
        plan.add_step(BuildStep(id=_make_id('perm'), type=StepType.APPLY_PERMISSIONS, payload={"channel": "announcements", "overwrites": overwrites}, estimated_delay=0.1))

    # Metadata registration
    plan.add_step(BuildStep(id=_make_id('meta'), type=StepType.REGISTER_METADATA, payload={"spec_summary": spec.__dict__, "template_meta": (chosen_tpl.get('meta') if chosen_tpl else {})}, estimated_delay=0.0))

    return plan
