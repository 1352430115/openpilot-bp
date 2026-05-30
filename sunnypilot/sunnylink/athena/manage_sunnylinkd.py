#!/usr/bin/env python3
import time
from multiprocessing import Process

from openpilot.common.params import Params
from openpilot.common.swaglog import cloudlog
from openpilot.system.manager.process import launcher

SUNNYLINKD_PID_PARAM = "SunnylinkdPid"
SUNNYLINKD_TARGET = "sunnypilot.sunnylink.athena.sunnylinkd"


def main():
  params = Params()
  try:
    while True:
      if not params.get_bool("SunnylinkEnabled"):
        cloudlog.info("Sunnylink disabled, manage_sunnylinkd idle")
        time.sleep(10)
        continue

      cloudlog.info("starting sunnylinkd daemon")
      proc = Process(name="sunnylinkd", target=launcher, args=(SUNNYLINKD_TARGET, "sunnylinkd"))
      proc.start()
      proc.join()
      cloudlog.event("sunnylinkd exited", exitcode=proc.exitcode)
      if not params.get_bool("SunnylinkEnabled"):
        continue
      time.sleep(5)
  except Exception:
    cloudlog.exception("manage_sunnylinkd.exception")
  finally:
    params.remove(SUNNYLINKD_PID_PARAM)


if __name__ == '__main__':
  main()
