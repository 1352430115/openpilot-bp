"""BluePilot: Gaode (Amap) map overlay for onroad view."""
from __future__ import annotations

import math
import ssl
import threading
import urllib.request

import pyray as rl

from openpilot.common.gps import get_gps_location_service
from openpilot.common.params import Params
from openpilot.common.swaglog import cloudlog
from openpilot.selfdrive.ui.bp.lib.amap_coords import latlon_to_pixel, latlon_to_tile, wgs84_to_gcj02
from openpilot.selfdrive.ui.bp.lib.onroad_display import OnroadDisplayState
from openpilot.selfdrive.ui.ui_state import ui_state

TILE_SIZE = 256
MAP_HEIGHT_FRAC = 0.5
PERSPECTIVE_STRIPS = 24
H_SEGMENTS = 10
CENTER_TRANSPARENCY = 0.50
BOUNDARY_TRANSPARENCY = 1.00
FAR_WIDTH_SCALE = 0.40
NEAR_WIDTH_SCALE = 1.00
DEFAULT_ZOOM = 17
TILES_RADIUS = 3
MIN_READY_TILES = 2
MAP_BG_COLOR = rl.Color(12, 16, 22, 255)
TILE_URL = (
  "https://wprd0{server}.is.autonavi.com/appmaptile"
  "?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}"
)
_SSL_CTX = ssl.create_default_context()
_SSL_CTX_UNVERIFIED = ssl.create_default_context()
_SSL_CTX_UNVERIFIED.check_hostname = False
_SSL_CTX_UNVERIFIED.verify_mode = ssl.CERT_NONE


class _TileCache:
  def __init__(self):
    self._lock = threading.Lock()
    self._textures: dict[tuple[int, int, int], rl.Texture] = {}
    self._pending: set[tuple[int, int, int]] = set()
    self._failed: set[tuple[int, int, int]] = set()
    # BluePilot: decode PNG on UI thread — Raylib textures must not be created from worker threads
    self._queued_bytes: dict[tuple[int, int, int], bytes] = {}
    # End BluePilot

  def get(self, z: int, x: int, y: int) -> rl.Texture | None:
    with self._lock:
      return self._textures.get((z, x, y))

  def has(self, z: int, x: int, y: int) -> bool:
    with self._lock:
      return (z, x, y) in self._textures

  def count_loaded_around(self, z: int, center_x: int, center_y: int, radius: int) -> int:
    with self._lock:
      count = 0
      for dx in range(-radius, radius + 1):
        for dy in range(-radius, radius + 1):
          if (z, center_x + dx, center_y + dy) in self._textures:
            count += 1
      return count

  def request(self, z: int, x: int, y: int) -> None:
    key = (z, x, y)
    with self._lock:
      if key in self._textures or key in self._pending or key in self._queued_bytes:
        return
      if key in self._failed:
        return
      self._pending.add(key)
    threading.Thread(target=self._download, args=(z, x, y), daemon=True).start()

  def flush_uploads(self) -> None:
    """Upload queued tile PNGs to GPU textures (call from UI render thread only)."""
    with self._lock:
      queued = dict(self._queued_bytes)
      self._queued_bytes.clear()
    for key, data in queued.items():
      try:
        image = rl.load_image_from_memory(".png", data, len(data))
        if image.width <= 0 or image.height <= 0:
          rl.unload_image(image)
          raise ValueError("invalid tile image")
        texture = rl.load_texture_from_image(image)
        rl.unload_image(image)
        rl.set_texture_filter(texture, rl.TextureFilter.TEXTURE_FILTER_BILINEAR)
        with self._lock:
          self._textures[key] = texture
      except Exception as exc:
        cloudlog.debug(f"Amap tile GPU upload failed {key}: {exc}")
        with self._lock:
          self._failed.add(key)

  def _download(self, z: int, x: int, y: int) -> None:
    key = (z, x, y)
    server = (x + y) % 4 + 1
    url = TILE_URL.format(server=server, x=x, y=y, z=z)
    req = urllib.request.Request(url, headers={"User-Agent": "BluePilot/1.0"})
    data = None
    for ctx in (_SSL_CTX, _SSL_CTX_UNVERIFIED):
      try:
        with urllib.request.urlopen(req, timeout=8, context=ctx) as resp:
          data = resp.read()
        break
      except ssl.SSLError as exc:
        if ctx is _SSL_CTX:
          cloudlog.warning(f"Amap tile SSL failed (retry unverified) z={z} x={x} y={y}: {exc}")
          continue
        cloudlog.debug(f"Amap tile download SSL failed z={z} x={x} y={y}: {exc}")
      except Exception as exc:
        cloudlog.debug(f"Amap tile download failed z={z} x={x} y={y}: {exc}")
        break
    try:
      if data is None:
        raise ValueError("no tile data")
      if len(data) < 128:
        raise ValueError("tile payload too small")
      with self._lock:
        self._queued_bytes[key] = data
    except Exception as exc:
      cloudlog.debug(f"Amap tile download failed z={z} x={x} y={y}: {exc}")
      with self._lock:
        self._failed.add(key)
    finally:
      with self._lock:
        self._pending.discard(key)

  def clear(self) -> None:
    with self._lock:
      for texture in self._textures.values():
        rl.unload_texture(texture)
      self._textures.clear()
      self._pending.clear()
      self._failed.clear()
      self._queued_bytes.clear()


def _rotation_cover_factor(bearing_deg: float) -> float:
  """Axis-aligned bounding box growth when a square tile grid is rotated."""
  rad = math.radians(bearing_deg)
  return abs(math.cos(rad)) + abs(math.sin(rad))


def _effective_tile_radius(bearing_deg: float) -> int:
  """Fetch extra tiles on diagonals so rotated views stay covered."""
  return min(5, int(math.ceil(TILES_RADIUS * _rotation_cover_factor(bearing_deg))))


def _layout_scale_for_rotation(bearing_deg: float, rt_w: float, rt_h: float, tile_radius: int) -> float:
  """Scale mercator tile offsets so the rotated grid fills the render target."""
  grid_extent = (2 * tile_radius + 1) * TILE_SIZE
  cover = _rotation_cover_factor(bearing_deg)
  half_extent = grid_extent * cover * 0.5
  # Vehicle anchor sits near the bottom; reserve more vertical space for road ahead.
  fit_w = rt_w * 0.49
  fit_h = rt_h * 0.78
  if half_extent <= 1.0:
    return 1.0
  return min(fit_w, fit_h) / half_extent


def _map_opacity(u: float, v: float) -> float:
  """Opacity from bottom-center anchor: 50% opaque at center, 0% at boundaries."""
  dist_h = abs(u - 0.5) * 2.0
  dist_v = 1.0 - v
  edge = min(1.0, max(dist_h, dist_v))
  transparency = CENTER_TRANSPARENCY + (BOUNDARY_TRANSPARENCY - CENTER_TRANSPARENCY) * edge
  return 1.0 - transparency


def _strip_width_scale(t: float) -> float:
  """Trapezoid width: linear ramp from far/top to near/bottom."""
  return FAR_WIDTH_SCALE + (NEAR_WIDTH_SCALE - FAR_WIDTH_SCALE) * t


class AmapRendererBP:
  """Renders Gaode night-mode map in the bottom half with trapezoid perspective."""

  def __init__(self):
    self._params = Params()
    self._tiles = _TileCache()
    self._render_target: rl.RenderTexture | None = None
    self._rt_size = (0, 0)
    self._cached_key = ""
    self._gps_service = get_gps_location_service(self._params)

  def close(self) -> None:
    if self._render_target is not None:
      rl.unload_render_texture(self._render_target)
      self._render_target = None
    self._tiles.clear()

  def update(self) -> None:
    """Prefetch tiles for the current GPS position while onroad."""
    self._sync_key_state()
    self._tiles.flush_uploads()
    self._prefetch_tiles()

  def tiles_ready(self) -> bool:
    """True when enough map tiles for the current position are loaded."""
    grid = self._current_tile_grid()
    if grid is None:
      return False
    bearing, zoom, center_tx, center_ty = grid[2], grid[3], grid[4], grid[5]
    if not self._tiles.has(zoom, center_tx, center_ty):
      return False
    return self._tiles.count_loaded_around(zoom, center_tx, center_ty, radius=1) >= MIN_READY_TILES

  def display_available(self) -> bool:
    return self.tiles_ready()

  def should_render(self) -> bool:
    return OnroadDisplayState.show_map() and self.tiles_ready()

  def render(self, content_rect: rl.Rectangle) -> None:
    self._tiles.flush_uploads()
    grid = self._current_tile_grid()
    if grid is None:
      return

    lat, lon, bearing, zoom, center_tx, center_ty = grid
    tile_radius = _effective_tile_radius(bearing)
    self._prefetch_for_grid(zoom, center_tx, center_ty, tile_radius)

    map_h = content_rect.height * MAP_HEIGHT_FRAC
    map_w = content_rect.width
    map_x = content_rect.x
    map_y = content_rect.y + content_rect.height * (1.0 - MAP_HEIGHT_FRAC)

    rt_w = max(64, int(map_w))
    rt_h = max(64, int(map_h))
    self._ensure_render_target(rt_w, rt_h)

    center_px, center_py = latlon_to_pixel(lat, lon, zoom)
    vehicle_screen_x = rt_w * 0.5
    vehicle_screen_y = rt_h * 0.90
    layout_scale = _layout_scale_for_rotation(bearing, rt_w, rt_h, tile_radius)
    rad = math.radians(-bearing)
    cos_b, sin_b = math.cos(rad), math.sin(rad)

    rl.begin_texture_mode(self._render_target)
    rl.clear_background(MAP_BG_COLOR)
    for dx in range(-tile_radius, tile_radius + 1):
      for dy in range(-tile_radius, tile_radius + 1):
        tx, ty = center_tx + dx, center_ty + dy
        texture = self._tiles.get(zoom, tx, ty)
        if texture is None:
          continue
        tile_px = tx * TILE_SIZE
        tile_py = ty * TILE_SIZE
        rel_x = (tile_px - center_px) * layout_scale
        rel_y = (tile_py - center_py) * layout_scale
        rot_x = rel_x * cos_b - rel_y * sin_b
        rot_y = rel_x * sin_b + rel_y * cos_b
        rl.draw_texture(texture, int(vehicle_screen_x + rot_x), int(vehicle_screen_y + rot_y), rl.WHITE)
    rl.end_texture_mode()

    strip_y = map_y
    src_y = 0.0
    strip_h = map_h / PERSPECTIVE_STRIPS
    src_strip_h = rt_h / PERSPECTIVE_STRIPS
    rl.begin_scissor_mode(int(map_x), int(map_y), int(map_w), int(map_h) + 1)
    for i in range(PERSPECTIVE_STRIPS):
      t = i / max(PERSPECTIVE_STRIPS - 1, 1)
      width_scale = _strip_width_scale(t)
      dest_w = map_w * width_scale
      dest_x = map_x + (map_w - dest_w) * 0.5
      v_center = (strip_y + strip_h * 0.5 - map_y) / map_h

      for j in range(H_SEGMENTS):
        u0 = j / H_SEGMENTS
        u1 = (j + 1) / H_SEGMENTS
        u_center = (u0 + u1) * 0.5
        opacity = _map_opacity(u_center, v_center)
        if opacity <= 0.01:
          continue

        col_dest_w = dest_w / H_SEGMENTS
        col_dest_x = dest_x + col_dest_w * j
        col_src_w = rt_w / H_SEGMENTS
        col_src_x = col_src_w * j
        src_rect = rl.Rectangle(col_src_x, src_y, col_src_w, -src_strip_h)
        dest_rect = rl.Rectangle(col_dest_x, strip_y, col_dest_w, strip_h + 1)
        tint = rl.Color(255, 255, 255, int(255 * opacity))
        rl.draw_texture_pro(
          self._render_target.texture,
          src_rect,
          dest_rect,
          rl.Vector2(0, 0),
          0.0,
          tint,
        )

      strip_y += strip_h
      src_y += src_strip_h
    rl.end_scissor_mode()

  def _get_gps_fix(self):
    """Return GPS message with fix, preferring the active location service for this device."""
    sm = ui_state.sm
    service = get_gps_location_service(self._params)
    if service != self._gps_service:
      self._gps_service = service
    if sm.valid.get(service, False):
      gps = sm[service]
      if gps.hasFix:
        return gps
    # BluePilot: fallback when SubMaster has the alternate GPS topic (e.g. during Ublox transition)
    for alt in ("gpsLocationExternal", "gpsLocation"):
      if alt == service:
        continue
      if sm.valid.get(alt, False):
        gps = sm[alt]
        if gps.hasFix:
          return gps
    return None

  def _current_tile_grid(self) -> tuple[float, float, float, int, int, int] | None:
    gps = self._get_gps_fix()
    if gps is None:
      return None

    lat, lon = wgs84_to_gcj02(gps.latitude, gps.longitude)
    bearing = gps.bearingDeg if math.isfinite(gps.bearingDeg) else 0.0
    zoom = DEFAULT_ZOOM
    center_tx, center_ty = latlon_to_tile(lat, lon, zoom)
    return lat, lon, bearing, zoom, center_tx, center_ty

  def _prefetch_tiles(self) -> None:
    grid = self._current_tile_grid()
    if grid is None:
      return
    bearing, zoom, center_tx, center_ty = grid[2], grid[3], grid[4], grid[5]
    self._prefetch_for_grid(zoom, center_tx, center_ty, _effective_tile_radius(bearing))

  def _prefetch_for_grid(self, zoom: int, center_tx: int, center_ty: int, tile_radius: int = TILES_RADIUS) -> None:
    for dx in range(-tile_radius, tile_radius + 1):
      for dy in range(-tile_radius, tile_radius + 1):
        self._tiles.request(zoom, center_tx + dx, center_ty + dy)

  def _ensure_render_target(self, width: int, height: int) -> None:
    if self._render_target is not None and self._rt_size == (width, height):
      return
    if self._render_target is not None:
      rl.unload_render_texture(self._render_target)
    self._render_target = rl.load_render_texture(width, height)
    self._rt_size = (width, height)

  def _get_key(self) -> str:
    raw = self._params.get("BPAmapWebKey")
    if raw is None:
      return ""
    if isinstance(raw, bytes):
      return raw.decode("utf-8", errors="replace").strip("\x00").strip()
    return str(raw).strip()

  def _sync_key_state(self) -> None:
    key = self._get_key()
    if key != self._cached_key:
      self._cached_key = key
      self._tiles.clear()
