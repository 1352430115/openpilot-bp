#!/usr/bin/env bash

SP_C3_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null && pwd )"
DIR="$( cd "$SP_C3_DIR/../../../.." >/dev/null 2>&1 && pwd )"

source "$SP_C3_DIR/launch_env.sh"

# BluePilot: hwj dp260513 C3 panda MCU detection and env (TICI_HW / TICI_TRES)
set_tici_hw() {
  if grep -q "tici" /sys/firmware/devicetree/base/model 2>/dev/null; then
    echo "Querying panda MCU type..."
    MCU_OUTPUT=$(python -c "from panda_tici import Panda; p = Panda(cli=False); print(p.get_mcu_type()); p.close()" 2>/dev/null)

    if [[ "$MCU_OUTPUT" == *"McuType.F4"* ]]; then
      echo "TICI (DOS) detected"
      mount_nvme
    elif [[ "$MCU_OUTPUT" == *"McuType.H7"* ]]; then
      echo "TICI (red panda H7) detected"
      export TICI_TRES=1
    else
      echo "TICI (UNKNOWN) detected"
    fi
    export TICI_HW=1
  fi
}

mount_nvme() {
  for i in $(seq 1 10); do
    [ -b /dev/nvme0n1p1 ] && break
    sleep 1
  done

  if [ ! -b /dev/nvme0n1p1 ]; then
    return 0
  fi

  if ! mountpoint -q /data/media/0/realdata; then
    mount /dev/nvme0n1p1 /data/media/0/realdata
  fi

  if mountpoint -q /data/media/0/realdata; then
    OWNER="$(stat -c '%U' /data/media/0/realdata)"
    GROUP="$(stat -c '%G' /data/media/0/realdata)"
    PERM="$(stat -c '%a' /data/media/0/realdata)"

    if [ "$OWNER" != "comma" ] || [ "$GROUP" != "comma" ]; then
      chown comma:comma /data/media/0/realdata
    fi

    if [ "$PERM" != "755" ]; then
      chmod 755 /data/media/0/realdata
    fi
  fi
}

set_lite_hw() {
  if grep -q "tici" /sys/firmware/devicetree/base/model 2>/dev/null; then
    output=$(i2cget -y 0 0x10 0x00 2>/dev/null)

    if [ -z "$output" ]; then
      echo "Lite HW"
      export LITE=1
    fi
  fi
}
# End BluePilot

# BluePilot: C3 panda firmware setup — F4 copy for classic C3, H7 aliases for C3X
function ensure_c3_panda_firmware {
  mkdir -p "$DIR/panda/board/obj"
  mkdir -p "$DIR/panda_tici/board/obj"

  if [ "$TICI_TRES" = "1" ]; then
    for obj in "$DIR/panda/board/obj" "$DIR/panda_tici/board/obj"; do
      [ -d "$obj" ] || continue
      if [ -f "$obj/bootstub.panda_h7.bin" ] && [ ! -e "$obj/bootstub.panda.bin" ]; then
        ln -sf bootstub.panda_h7.bin "$obj/bootstub.panda.bin"
      fi
      if [ -f "$obj/panda_h7.bin.signed" ] && [ ! -e "$obj/panda.bin.signed" ]; then
        ln -sf panda_h7.bin.signed "$obj/panda.bin.signed"
      fi
    done
  else
    for name in panda.bin.signed bootstub.panda.bin; do
      src="$DIR/panda/board/obj/$name"
      dst="$DIR/panda_tici/board/obj/$name"
      if [ -f "$src" ] && [ ! -e "$dst" ]; then
        cp -f "$src" "$dst"
      fi

      # BluePilot: mirror back as well in case only panda_tici artifacts were deployed
      src="$DIR/panda_tici/board/obj/$name"
      dst="$DIR/panda/board/obj/$name"
      if [ -f "$src" ] && [ ! -e "$dst" ]; then
        cp -f "$src" "$dst"
      fi
    done
  fi
}
# End BluePilot

function agnos_init {
  # TODO: move this to agnos
  sudo rm -f /data/etc/NetworkManager/system-connections/*.nmmeta

  # set success flag for current boot slot
  sudo abctl --set_success

  # TODO: do this without udev in AGNOS
  # udev does this, but sometimes we startup faster
  sudo chgrp gpu /dev/adsprpc-smd /dev/ion /dev/kgsl-3d0
  sudo chmod 660 /dev/adsprpc-smd /dev/ion /dev/kgsl-3d0


  if [ $(< /VERSION) != "$AGNOS_VERSION" ]; then
    AGNOS_PY="$DIR/system/hardware/tici/agnos.py"
    # BluePilot: use AGNOS 16 manifest for upgraded C3 devices
    if [ "$AGNOS_VERSION" = "16" ]; then
      MANIFEST="$DIR/system/hardware/tici/agnos.json"
    else
      MANIFEST="$SP_C3_DIR/agnos.json"
    fi
    # End BluePilot
    if $AGNOS_PY --verify $MANIFEST; then
      sudo reboot
    fi
    $DIR/system/hardware/tici/updater $AGNOS_PY $MANIFEST
  fi
}

function launch {
  # Remove orphaned git lock if it exists on boot
  [ -f "$DIR/.git/index.lock" ] && rm -f $DIR/.git/index.lock

  # Check to see if there's a valid overlay-based update available. Conditions
  # are as follows:
  #
  # 1. The DIR init file has to exist, with a newer modtime than anything in
  #    the DIR Git repo. This checks for local development work or the user
  #    switching branches/forks, which should not be overwritten.
  # 2. The FINALIZED consistent file has to exist, indicating there's an update
  #    that completed successfully and synced to disk.

  if [ -f "${DIR}/.overlay_init" ]; then
    find ${DIR}/.git -newer ${DIR}/.overlay_init | grep -q '.' 2> /dev/null
    if [ $? -eq 0 ]; then
      echo "${DIR} has been modified, skipping overlay update installation"
    else
      if [ -f "${STAGING_ROOT}/finalized/.overlay_consistent" ]; then
        if [ ! -d /data/safe_staging/old_openpilot ]; then
          echo "Valid overlay update found, installing"
          LAUNCHER_LOCATION="${BASH_SOURCE[0]}"

          mv $DIR /data/safe_staging/old_openpilot
          mv "${STAGING_ROOT}/finalized" $DIR
          cd $DIR

          echo "Restarting launch script ${LAUNCHER_LOCATION}"
          unset AGNOS_VERSION
          exec "${LAUNCHER_LOCATION}"
        else
          echo "openpilot backup found, not updating"
          # TODO: restore backup? This means the updater didn't start after swapping
        fi
      fi
    fi
  fi

  # handle pythonpath
  ln -sfn $(pwd) /data/pythonpath
  export PYTHONPATH="$PWD"

  # hardware specific init
  if [ -f /AGNOS ]; then
    set_tici_hw
    set_lite_hw
    agnos_init
  fi

  # write tmux scrollback to a file
  tmux capture-pane -pq -S-1000 > /tmp/launch_log

  # BluePilot: ensure panda recovery images exist before manager starts pandad
  ensure_c3_panda_firmware
  # End BluePilot

  # start manager
  cd $DIR/system/manager
  if [ ! -f $DIR/prebuilt ]; then
    ./build.py
  fi
  ensure_c3_panda_firmware
  ./manager.py

  # if broken, keep on screen error
  while true; do sleep 1; done
}

launch
