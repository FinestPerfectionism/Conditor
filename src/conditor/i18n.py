"""Lightweight internationalization helpers for Conditor.

Provides `Localizer` for JSON bundles, simple pluralization, and RTL detection.
"""
from pathlib import Path
import json
from typing import Dict


BASE = Path(__file__).parent.parent / "data" / "locales"


def is_rtl_locale(code: str) -> bool:
    if not code:
        return False
    return code.lower().startswith("ar")


def _plural_form_ar(n: int) -> str:
    # Arabic: zero, one, two, few (3-10), many (11-99), other
    if n == 0:
        return "zero"
    if n == 1:
        return "one"
    if n == 2:
        return "two"
    mod100 = n % 100
    if 3 <= mod100 <= 10:
        return "few"
    if 11 <= mod100 <= 99:
        return "many"
    return "other"


def _plural_form_ru(n: int) -> str:
    mod10 = n % 10
    mod100 = n % 100
    if mod10 == 1 and mod100 != 11:
        return "one"
    if 2 <= mod10 <= 4 and not (12 <= mod100 <= 14):
        return "few"
    return "many"


def _plural_form_en(n: int) -> str:
    return "one" if n == 1 else "other"


def select_plural_form(locale: str, n: int) -> str:
    lc = (locale or "").lower()
    if lc.startswith("ar"):
        return _plural_form_ar(n)
    if lc.startswith("ru"):
        return _plural_form_ru(n)
    # default English-like
    return _plural_form_en(n)


class Localizer:
    """Loads locale JSON and formats messages.

    Fallback order: exact code -> primary language -> 'en' -> key literal.
    Supports selecting plural forms by looking for keys like '<base>.one', '<base>.few', etc.
    Also provides `direction()` and `rtl_wrap()` helpers for RTL locales.
    """

    _cache: Dict[str, Dict[str, str]] = {}

    def __init__(self, locale: str = None):
        self.locale = (locale or "en").lower()
        self.bundle = self._load_bundle(self.locale)

    @classmethod
    def _load_bundle(cls, locale: str) -> Dict[str, str]:
        if locale in cls._cache:
            return cls._cache[locale]
        candidates = [locale, locale.split("-")[0], locale.split("_")[0], "en"]
        for cand in candidates:
            path = BASE / f"{cand}.json"
            if path.exists():
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    cls._cache[locale] = data
                    return data
                except Exception:
                    continue
        cls._cache[locale] = {}
        return {}

    def get(self, key: str, **kwargs) -> str:
        template = self.bundle.get(key)
        if template is None:
            # fallback to key if not found
            try:
                return key.format(**kwargs) if kwargs else key
            except Exception:
                return key
        try:
            return template.format(**kwargs) if kwargs else template
        except Exception:
            return template

    def get_plural(self, base_key: str, n: int, **kwargs) -> str:
        form = select_plural_form(self.locale, n)
        # Try specific form keys then common fallbacks
        for k in (f"{base_key}.{form}", f"{base_key}.other", base_key):
            if k in self.bundle:
                try:
                    return self.bundle[k].format(n=n, **kwargs)
                except Exception:
                    return self.bundle[k]
        # last resort
        return str(n)

    def direction(self) -> str:
        return "rtl" if is_rtl_locale(self.locale) else "ltr"

    def rtl_wrap(self, text: str) -> str:
        if is_rtl_locale(self.locale):
            # RLE (Right-to-Left Embedding) + PDF
            return "\u202B" + text + "\u202C"
        return text
