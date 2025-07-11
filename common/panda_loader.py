"""BluePilot: load panda or panda_tici per hwj dp260513 C3 logic (TICI_HW / TICI_TRES)."""
import importlib
import os


def _ensure_tici_env() -> None:
  """Set TICI_HW / TICI_TRES when manager was not started via launch_chffrplus.sh."""
  if os.environ.get("TICI_HW") or os.environ.get("TICI_TRES"):
    return
  try:
    with open("/sys/firmware/devicetree/base/model") as f:
      if "tici" not in f.read().lower():
        return
  except OSError:
    return

  os.environ.setdefault("TICI_HW", "1")
  try:
    panda_tici = importlib.import_module("panda_tici")
    p = panda_tici.Panda(cli=False)
    mcu = str(p.get_mcu_type())
    p.close()
    if "H7" in mcu:
      os.environ["TICI_TRES"] = "1"
  except Exception:
    pass


def load_panda_module():
  _ensure_tici_env()
  if os.environ.get("TICI_HW") and os.environ.get("TICI_TRES") != "1":
    return importlib.import_module("panda_tici")
  return importlib.import_module("panda")
