"""Apply domestic NTP servers via systemd-timesyncd on AGNOS devices."""

import subprocess
from pathlib import Path

from openpilot.common.params import Params, UnknownKeyName
from openpilot.common.swaglog import cloudlog
from openpilot.system.hardware import AGNOS, PC

DROP_IN_DIR = Path("/etc/systemd/timesyncd.conf.d")
DROP_IN_FILE = DROP_IN_DIR / "bluepilot-ntp.conf"

NTP_SERVERS = (
  "ntp.aliyun.com",
  "cn.pool.ntp.org",
  "ntp.tencent.com",
)
FALLBACK_NTP = "ntp.ubuntu.com"


def desired_timesyncd_config() -> str:
  return (
    "# BluePilot domestic NTP servers\n"
    "[Time]\n"
    f"NTP={' '.join(NTP_SERVERS)}\n"
    f"FallbackNTP={FALLBACK_NTP}\n"
  )


def _use_domestic_ntp(params: Params) -> bool:
  try:
    params.check_key("BPUseDomesticNtp")
  except UnknownKeyName:
    return True
  return params.get_bool("BPUseDomesticNtp")


def _read_drop_in() -> str | None:
  try:
    return DROP_IN_FILE.read_text(encoding="utf-8")
  except (OSError, PermissionError):
    return None


def _run_sudo(args: list[str]) -> bool:
  try:
    subprocess.run(["sudo", *args], check=True, capture_output=True, text=True)
    return True
  except subprocess.CalledProcessError as e:
    cloudlog.error(f"ntp_setup: sudo {' '.join(args)} failed: {e.stderr or e}")
    return False


def _remount_root(read_write: bool) -> bool:
  mode = "rw" if read_write else "ro"
  return _run_sudo(["mount", "-o", f"remount,{mode}", "/"])


def ensure_domestic_ntp(params: Params) -> None:
  """Install or refresh BluePilot NTP drop-in on comma devices (idempotent)."""
  if not AGNOS or PC:
    return
  if not _use_domestic_ntp(params):
    cloudlog.info("ntp_setup: BPUseDomesticNtp disabled, skipping")
    return

  expected = desired_timesyncd_config()
  if _read_drop_in() == expected:
    return

  if not _remount_root(read_write=True):
    return

  try:
    if not _run_sudo(["mkdir", "-p", str(DROP_IN_DIR)]):
      return

    try:
      subprocess.run(
        ["sudo", "tee", str(DROP_IN_FILE)],
        input=expected,
        check=True,
        capture_output=True,
        text=True,
      )
    except subprocess.CalledProcessError as e:
      cloudlog.error(f"ntp_setup: failed to write {DROP_IN_FILE}: {e.stderr or e}")
      return

    if not _run_sudo(["systemctl", "restart", "systemd-timesyncd"]):
      return

    cloudlog.info(f"ntp_setup: configured domestic NTP in {DROP_IN_FILE}")
  finally:
    _remount_root(read_write=False)
