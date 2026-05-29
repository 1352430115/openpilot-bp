"""Onroad alert string registration and localization for BluePilot UI."""

import re

from openpilot.system.ui.lib.multilang import tr, tr_noop

# Register static alert strings for translation catalog extraction.
tr_noop("Calibrating")
tr_noop("Recalibrating")
tr_noop("Drive Above %s")
tr_noop("Drive above %s to engage")
tr_noop("Drive on a marked road with visible lane lines")
tr_noop("WARNING: This branch is not tested")
tr_noop("openpilot Unavailable")
tr_noop("Calibration in Progress")
tr_noop("Calibration Incomplete")
tr_noop("Calibration Invalid")
tr_noop("System Initializing")
tr_noop("Be ready to take over at any time")
tr_noop("Always keep hands on wheel and eyes on road")
tr_noop("Remount Detected: Recalibrating")
tr_noop("Device Remount Detected: Recalibrating")
tr_noop("Calibration Invalid: Remount Device & Recalibrate")

_CALIBRATING_RE = re.compile(r"^(Calibrating|Recalibrating): (\d+)%$")
_DRIVE_ABOVE_RE = re.compile(r"^Drive Above (.+)$")
_DRIVE_ABOVE_ENGAGE_RE = re.compile(r"^Drive above (.+) to engage$", re.IGNORECASE)


def localize_onroad_alert_text(text: str) -> str:
  if not text:
    return ""

  translated = tr(text)
  if translated != text:
    return translated

  match = _CALIBRATING_RE.match(text)
  if match:
    label = tr("Recalibrating") if match.group(1) == "Recalibrating" else tr("Calibrating")
    return f"{label}: {match.group(2)}%"

  match = _DRIVE_ABOVE_RE.match(text)
  if match:
    return _format_template("Drive Above %s", match.group(1))

  match = _DRIVE_ABOVE_ENGAGE_RE.match(text)
  if match:
    return _format_template("Drive above %s to engage", match.group(1))

  return text


def _format_template(template_key: str, value: str) -> str:
  template = tr(template_key)
  if "%s" in template:
    return template % value
  return f"{template} {value}"
