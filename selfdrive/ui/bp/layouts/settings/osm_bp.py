"""BluePilot: OSM settings with Amap Web Service key input."""
from openpilot.selfdrive.ui.sunnypilot.layouts.settings.osm import OSMLayout
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.multilang import tr
from openpilot.system.ui.sunnypilot.lib.utils import NoElideButtonAction
from openpilot.system.ui.sunnypilot.widgets.input_dialog import InputDialogSP
from openpilot.system.ui.sunnypilot.widgets.list_view import ListItemSP
from openpilot.system.ui.widgets import DialogResult


class OSMLayoutBP(OSMLayout):
  """Extends stock OSM settings with Amap Web Service API key configuration."""

  def _initialize_items(self):
    super()._initialize_items()
    self._amap_key_btn = ListItemSP(
      lambda: tr("Amap Web Service Key"),
      action_item=NoElideButtonAction(lambda: tr("EDIT"), enabled=True),
      callback=self._edit_amap_key,
    )
    self.items.append(self._amap_key_btn)
    self._update_amap_key_label()

  def _decode_key(self) -> str:
    raw = ui_state.params.get("BPAmapWebKey")
    if raw is None:
      return ""
    if isinstance(raw, bytes):
      return raw.decode("utf-8", errors="replace").strip("\x00").strip()
    return str(raw).strip()

  def _mask_key(self, key: str) -> str:
    if not key:
      return tr("Not set")
    if len(key) <= 8:
      return "*" * len(key)
    return key[:4] + "*" * (len(key) - 8) + key[-4:]

  def _update_amap_key_label(self):
    self._amap_key_btn.action_item.set_value(self._mask_key(self._decode_key()))

  def _edit_amap_key(self):
    dialog = InputDialogSP(
      title=tr("Amap Web Service Key"),
      sub_title=tr("Enter your Amap Web Service API key"),
      current_text=self._decode_key(),
      param="BPAmapWebKey",
      callback=self._on_amap_key_saved,
    )
    dialog.show()

  def _on_amap_key_saved(self, result: DialogResult, _text: str):
    if result == DialogResult.CONFIRM:
      self._update_amap_key_label()

  def _update_labels(self):
    super()._update_labels()
    self._update_amap_key_label()

  def show_event(self):
    super().show_event()
    self._update_amap_key_label()
