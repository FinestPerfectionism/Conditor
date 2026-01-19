from dataclasses import dataclass, field
from typing import List, Dict, Any, Iterable
import json
from pathlib import Path

@dataclass
class ServerSpec:
    community_type: str = ''
    games: List[str] = field(default_factory=list)
    moderation: str = ''
    language: str = ''
    size: str = ''
    extras: Dict[str, Any] = field(default_factory=dict)


def load_questionnaire(path: Path) -> ServerSpec:
    data = json.loads(path.read_text(encoding='utf-8'))
    spec = ServerSpec(
        community_type = data.get('community_type') or data.get('type') or data.get('community', ''),
        games = data.get('games', []),
        moderation = data.get('moderation') or data.get('moderation_strictness') or data.get('moderation_level',''),
        language = data.get('language') or data.get('lang', ''),
        size = data.get('size') or data.get('size_expectation',''),
        extras = {k:v for k,v in data.items() if k not in ('community_type','type','community','games','moderation','moderation_strictness','moderation_level','language','lang','size','size_expectation')}
    )
    return spec


def load_template(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def merge_spec_from_files(
    questionnaire_paths: Iterable[Path],
    template_paths: Iterable[Path]
) -> ServerSpec:
    spec = ServerSpec()
    # merge questionnaires (first writer wins for core fields)
    for p in questionnaire_paths:
        try:
            s = load_questionnaire(p)
        except Exception:
            continue
        if s.community_type and not spec.community_type:
            spec.community_type = s.community_type
        if s.games and not spec.games:
            spec.games = s.games
        if s.moderation and not spec.moderation:
            spec.moderation = s.moderation
        if s.language and not spec.language:
            spec.language = s.language
        if s.size and not spec.size:
            spec.size = s.size
        spec.extras.update(s.extras)

    # attach templates into extras for now
    templates = []
    for tpath in template_paths:
        try:
            templates.append(load_template(tpath))
        except Exception:
            continue
    if templates:
        spec.extras.setdefault('templates', []).extend(templates)
    return spec


def discover_and_merge(base_path: Path) -> ServerSpec:
    qdir = base_path / 'data' / 'questionnaire'
    tdir = base_path / 'data' / 'templates'
    qfiles = list(qdir.glob('*.json')) if qdir.exists() else []
    tfiles = list(tdir.glob('*.json')) if tdir.exists() else []
    return merge_spec_from_files(qfiles, tfiles)
