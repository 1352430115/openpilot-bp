"""Read device UI language from Params (matches openpilot multilang)."""

from __future__ import annotations

SUPPORTED_LANGUAGES = frozenset({
    "en", "de", "fr", "pt-BR", "es", "tr", "uk", "th", "zh-CHT", "zh-CHS", "ko", "ja",
})


def parse_language_setting(raw) -> str:
    if raw is None:
        return "en"
    if isinstance(raw, bytes):
        lang = raw.decode("utf-8", errors="replace")
    else:
        lang = str(raw)
    lang = lang.removeprefix("main_").strip("\x00").strip()
    if lang in SUPPORTED_LANGUAGES:
        return lang
    return "en"


def get_device_language(params) -> str:
    try:
        return parse_language_setting(params.get("LanguageSetting"))
    except Exception:
        return "en"
