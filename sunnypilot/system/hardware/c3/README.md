# C3 specific hardware code

`c3` is known as `tici` and comma three by comma. Not to confuse it with `c3x` which is known as `tizi`.

## BluePilot notes (C3 vs C3X)

- **Launch**: `launch_openpilot.sh` routes `comma tici` devices to this directory.
- **Panda**: C3 uses the H7 red panda (classic CAN). C3X (`tizi`) uses cuatro with CAN-FD. Firmware recovery uses `bootstub.panda_h7.bin` / `panda_h7.bin.signed`; F4-named files are symlinks for DFU compatibility.
- **CAN-FD**: Disabled on connect in `panda/python/__init__.py` (`set_canfd_auto(False)`). Ford CAN-FD platforms require C3X hardware.