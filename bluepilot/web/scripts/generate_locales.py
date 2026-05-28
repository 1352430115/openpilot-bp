#!/usr/bin/env python3
"""Generate portal locale JSON files for the web UI build."""

from __future__ import annotations

import json
import sys
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parent.parent
OPENPILOT_ROOT = WEB_DIR.parent.parent
LOCALES_DIR = WEB_DIR / "locales"
OVERRIDES_DIR = LOCALES_DIR / "overrides"
OUTPUT_DIR = WEB_DIR / "public" / "locales"
LANGUAGES_FILE = OPENPILOT_ROOT / "selfdrive" / "ui" / "translations" / "languages.json"
PO_DIR = OPENPILOT_ROOT / "selfdrive" / "ui" / "translations"


def load_po_translations(lang: str) -> dict[str, str]:
    try:
        from openpilot.system.ui.lib.multilang import load_translations
    except ImportError:
        sys.path.insert(0, str(OPENPILOT_ROOT))
        from openpilot.system.ui.lib.multilang import load_translations

    po_path = PO_DIR / f"app_{lang}.po"
    if not po_path.exists():
        return {}
    translations, _ = load_translations(po_path)
    return translations


def merge_locale(lang: str, en_strings: dict[str, str]) -> dict[str, str]:
    result = dict(en_strings)
    po = load_po_translations(lang)

    for key, english in en_strings.items():
        if key in result and result[key] != english:
            continue
        if english in po and po[english]:
            result[key] = po[english]

    override_path = OVERRIDES_DIR / f"{lang}.json"
    if override_path.exists():
        with override_path.open(encoding="utf-8") as f:
            overrides = json.load(f)
        result.update(overrides)

    return result


def main() -> int:
    with (LOCALES_DIR / "en.json").open(encoding="utf-8") as f:
        en_strings = json.load(f)

    with LANGUAGES_FILE.open(encoding="utf-8") as f:
        languages = json.load(f)

    lang_codes = sorted(set(languages.values()) | {"en"})
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for lang in lang_codes:
        if lang == "en":
            merged = en_strings
        else:
            merged = merge_locale(lang, en_strings)

        out_path = OUTPUT_DIR / f"{lang}.json"
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"Wrote {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
