"""BluePilot: Onroad display mode cycling (full / map / sidebar)."""
from enum import IntEnum


class OnroadDisplayMode(IntEnum):
  FULL = 0      # Original full-screen driving view
  MAP = 1       # Driving view + Amap overlay
  SIDEBAR = 2   # Driving view + sidebar menu


class OnroadDisplayState:
  _mode = OnroadDisplayMode.FULL

  @classmethod
  def mode(cls) -> OnroadDisplayMode:
    return cls._mode

  @classmethod
  def set_mode(cls, mode: OnroadDisplayMode) -> None:
    cls._mode = mode

  @classmethod
  def cycle(cls) -> OnroadDisplayMode:
    cls._mode = OnroadDisplayMode((int(cls._mode) + 1) % 3)
    return cls._mode

  @classmethod
  def reset(cls) -> None:
    cls.reset_to_default(map_available=False)

  @classmethod
  def reset_to_default(cls, map_available: bool) -> None:
    """Idle/onroad entry default: map overlay when tiles are ready, else full screen."""
    cls._mode = OnroadDisplayMode.MAP if map_available else OnroadDisplayMode.FULL

  @classmethod
  def show_map(cls) -> bool:
    return cls._mode == OnroadDisplayMode.MAP

  @classmethod
  def show_sidebar(cls) -> bool:
    return cls._mode == OnroadDisplayMode.SIDEBAR
