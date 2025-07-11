#!/usr/bin/env python3
"""Localized parameter descriptions for the BluePilot Portal."""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
PARAM_HELP_PATH = REPO_ROOT / "bluepilot" / "params" / "param_help.json"
PARAMS_JSON_PATH = REPO_ROOT / "bluepilot" / "params" / "params.json"
METADATA_PATH = REPO_ROOT / "sunnypilot" / "sunnylink" / "params_metadata.json"
PO_DIR = REPO_ROOT / "selfdrive" / "ui" / "translations"

SUPPORTED_LANGS = {"en", "de", "fr", "pt-BR", "es", "tr", "uk", "th", "zh-CHS", "zh-CHT", "ko", "ja"}


def normalize_language(code: str | None) -> str:
  if not code:
    return "en"
  cleaned = code.replace("main_", "").strip()
  return cleaned if cleaned in SUPPORTED_LANGS else "en"


def _humanize_key(key: str) -> str:
  text = re.sub(r"([a-z])([A-Z])", r"\1 \2", key)
  text = text.replace("_", " ").strip()
  return text or key


@lru_cache(maxsize=1)
def _load_param_help() -> dict[str, dict[str, str]]:
  if not PARAM_HELP_PATH.exists():
    return {}
  try:
    with PARAM_HELP_PATH.open(encoding="utf-8") as f:
      data = json.load(f)
    return data if isinstance(data, dict) else {}
  except Exception as e:
    logger.warning("Failed to load param_help.json: %s", e)
    return {}


@lru_cache(maxsize=1)
def _load_metadata() -> dict[str, Any]:
  if not METADATA_PATH.exists():
    return {}
  try:
    with METADATA_PATH.open(encoding="utf-8") as f:
      return json.load(f)
  except Exception as e:
    logger.warning("Failed to load params_metadata.json: %s", e)
    return {}


@lru_cache(maxsize=1)
def _load_ccprop_aliases() -> dict[str, str]:
  """Map storage param name -> ccProp alias from params.json."""
  aliases: dict[str, str] = {}
  if not PARAMS_JSON_PATH.exists():
    return aliases
  try:
    with PARAMS_JSON_PATH.open(encoding="utf-8") as f:
      data = json.load(f)
    for param in data.get("params", []):
      if not isinstance(param, dict):
        continue
      name = param.get("name")
      cc_prop = param.get("ccProp")
      if name and cc_prop:
        aliases[str(name)] = str(cc_prop)
  except Exception as e:
    logger.debug("Failed to load ccProp aliases: %s", e)
  return aliases


@lru_cache(maxsize=16)
def _load_po_translations(lang: str) -> dict[str, str]:
  if lang == "en":
    return {}
  po_path = PO_DIR / f"app_{lang}.po"
  if not po_path.exists():
    return {}
  try:
    from openpilot.system.ui.lib.multilang import load_translations
    translations, _ = load_translations(po_path)
    return translations
  except Exception as e:
    logger.debug("Failed to load PO translations for %s: %s", lang, e)
    return {}


def _pick_lang(entry: dict[str, str], lang: str) -> str:
  if lang in entry and entry[lang].strip():
    return entry[lang].strip()
  if entry.get("en", "").strip():
    return entry["en"].strip()
  for value in entry.values():
    if isinstance(value, str) and value.strip():
      return value.strip()
  return ""


def _metadata_english(key: str, metadata: dict[str, Any], cc_aliases: dict[str, str]) -> str:
  meta = metadata.get(key)
  if isinstance(meta, dict):
    desc = (meta.get("description") or "").strip()
    if desc:
      return desc
    title = (meta.get("title") or "").strip()
    if title:
      return title

  cc_prop = cc_aliases.get(key)
  if cc_prop:
    meta = metadata.get(cc_prop)
    if isinstance(meta, dict):
      desc = (meta.get("description") or "").strip()
      if desc:
        return desc
      title = (meta.get("title") or "").strip()
      if title:
        return title
  return ""


def get_param_description(key: str, lang: str = "en") -> str:
  """Return a localized description for a parameter key."""
  lang = normalize_language(lang)
  help_data = _load_param_help()

  if key in help_data:
    text = _pick_lang(help_data[key], lang)
    if text:
      return text

  cc_aliases = _load_ccprop_aliases()
  cc_prop = cc_aliases.get(key)
  if cc_prop and cc_prop in help_data:
    text = _pick_lang(help_data[cc_prop], lang)
    if text:
      return text

  metadata = _load_metadata()
  english = _metadata_english(key, metadata, cc_aliases)
  if not english and cc_prop:
    english = _metadata_english(cc_prop, metadata, {})

  if english:
    if lang == "en":
      return english
    translated = _load_po_translations(lang).get(english)
    if translated:
      return translated.strip()
    return english

  return _humanize_key(key)


def get_device_language(params: Any) -> str:
  """Read LanguageSetting from openpilot Params."""
  try:
    raw = params.get("LanguageSetting")
    if isinstance(raw, bytes):
      raw = raw.decode("utf-8", errors="replace").strip("\x00")
    return normalize_language(str(raw) if raw else None)
  except Exception:
    return "en"
