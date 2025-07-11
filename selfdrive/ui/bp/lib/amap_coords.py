"""BluePilot: Coordinate helpers for Gaode (Amap) map tiles."""
import math

_TILE_SIZE = 256
_EARTH_RADIUS = 6378137.0
_GCJ_A = 6378245.0
_GCJ_EE = 0.00669342162296594323


def _out_of_china(lat: float, lon: float) -> bool:
  return not (73.66 < lon < 135.05 and 3.86 < lat < 53.55)


def _transform_lat(lon: float, lat: float) -> float:
  ret = -100.0 + 2.0 * lon + 3.0 * lat + 0.2 * lat * lat + 0.1 * lon * lat + 0.2 * math.sqrt(abs(lon))
  ret += (20.0 * math.sin(6.0 * lon * math.pi) + 20.0 * math.sin(2.0 * lon * math.pi)) * 2.0 / 3.0
  ret += (20.0 * math.sin(lat * math.pi) + 40.0 * math.sin(lat / 3.0 * math.pi)) * 2.0 / 3.0
  ret += (160.0 * math.sin(lat / 12.0 * math.pi) + 320.0 * math.sin(lat * math.pi / 30.0)) * 2.0 / 3.0
  return ret


def _transform_lon(lon: float, lat: float) -> float:
  ret = 300.0 + lon + 2.0 * lat + 0.1 * lon * lon + 0.1 * lon * lat + 0.1 * math.sqrt(abs(lon))
  ret += (20.0 * math.sin(6.0 * lon * math.pi) + 20.0 * math.sin(2.0 * lon * math.pi)) * 2.0 / 3.0
  ret += (20.0 * math.sin(lon * math.pi) + 40.0 * math.sin(lon / 3.0 * math.pi)) * 2.0 / 3.0
  ret += (150.0 * math.sin(lon / 12.0 * math.pi) + 300.0 * math.sin(lon / 30.0 * math.pi)) * 2.0 / 3.0
  return ret


def wgs84_to_gcj02(lat: float, lon: float) -> tuple[float, float]:
  """Convert WGS84 GPS coordinates to GCJ-02 used by Gaode map tiles."""
  if _out_of_china(lat, lon):
    return lat, lon
  d_lat = _transform_lat(lon - 105.0, lat - 35.0)
  d_lon = _transform_lon(lon - 105.0, lat - 35.0)
  rad_lat = lat / 180.0 * math.pi
  magic = math.sin(rad_lat)
  magic = 1 - _GCJ_EE * magic * magic
  sqrt_magic = math.sqrt(magic)
  d_lat = (d_lat * 180.0) / ((_GCJ_A * (1 - _GCJ_EE)) / (magic * sqrt_magic) * math.pi)
  d_lon = (d_lon * 180.0) / (_GCJ_A / sqrt_magic * math.cos(rad_lat) * math.pi)
  return lat + d_lat, lon + d_lon


def latlon_to_pixel(lat: float, lon: float, zoom: int) -> tuple[float, float]:
  scale = _TILE_SIZE * (2 ** zoom)
  sin_lat = math.sin(lat * math.pi / 180.0)
  sin_lat = max(min(sin_lat, 0.9999), -0.9999)
  x = (lon + 180.0) / 360.0 * scale
  y = (0.5 - math.log((1 + sin_lat) / (1 - sin_lat)) / (4 * math.pi)) * scale
  return x, y


def latlon_to_tile(lat: float, lon: float, zoom: int) -> tuple[int, int]:
  px, py = latlon_to_pixel(lat, lon, zoom)
  return int(px // _TILE_SIZE), int(py // _TILE_SIZE)


def pixel_offset_for_latlon(lat: float, lon: float, ref_lat: float, ref_lon: float, zoom: int) -> tuple[float, float]:
  px, py = latlon_to_pixel(lat, lon, zoom)
  ref_px, ref_py = latlon_to_pixel(ref_lat, ref_lon, zoom)
  return px - ref_px, py - ref_py


def offset_latlon(lat: float, lon: float, bearing_deg: float, distance_m: float) -> tuple[float, float]:
  bearing = math.radians(bearing_deg)
  lat1 = math.radians(lat)
  lon1 = math.radians(lon)
  lat2 = math.asin(
    math.sin(lat1) * math.cos(distance_m / _EARTH_RADIUS) +
    math.cos(lat1) * math.sin(distance_m / _EARTH_RADIUS) * math.cos(bearing)
  )
  lon2 = lon1 + math.atan2(
    math.sin(bearing) * math.sin(distance_m / _EARTH_RADIUS) * math.cos(lat1),
    math.cos(distance_m / _EARTH_RADIUS) - math.sin(lat1) * math.sin(lat2),
  )
  return math.degrees(lat2), math.degrees(lon2)
