"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import pyray as rl

from openpilot.system.ui.lib.application import gui_app
from openpilot.system.ui.lib.multilang import tr
from openpilot.system.ui.widgets import DialogResult
from openpilot.system.ui.widgets.button import Button, ButtonStyle
from openpilot.system.ui.widgets.html_render import HtmlModal


class HtmlModalSP(HtmlModal):
  def __init__(self, file_path=None, text=None, callback=None, show_clear_button: bool = False):
    super().__init__(file_path=file_path, text=text)
    self._callback = callback
    self._dialog_result = DialogResult.NO_ACTION
    self._show_clear_button = show_clear_button
    self._ok_button._click_callback = self._on_ok_clicked
    self._clear_button = Button(tr("CLEAR"), click_callback=self._on_clear_clicked, button_style=ButtonStyle.NORMAL)

  def _on_ok_clicked(self):
    self._dialog_result = DialogResult.CONFIRM
    gui_app.pop_widget()
    if self._callback:
      self._callback(self._dialog_result)

  def _on_clear_clicked(self):
    self._dialog_result = DialogResult.CLEAR
    gui_app.pop_widget()
    if self._callback:
      self._callback(self._dialog_result)

  def reset(self):
    self._dialog_result = DialogResult.NO_ACTION

  def _render(self, rect: rl.Rectangle):
    margin = 50
    content_rect = rl.Rectangle(rect.x + margin, rect.y + margin, rect.width - (margin * 2), rect.height - (margin * 2))

    button_height = 160
    button_spacing = 20
    scrollable_height = content_rect.height - button_height - button_spacing

    scrollable_rect = rl.Rectangle(content_rect.x, content_rect.y, content_rect.width, scrollable_height)

    total_height = self._content.get_total_height(int(scrollable_rect.width))
    scroll_content_rect = rl.Rectangle(scrollable_rect.x, scrollable_rect.y, scrollable_rect.width, total_height)
    scroll_offset = self._scroll_panel.update(scrollable_rect, scroll_content_rect)
    scroll_content_rect.y += scroll_offset

    rl.begin_scissor_mode(int(scrollable_rect.x), int(scrollable_rect.y), int(scrollable_rect.width), int(scrollable_rect.height))
    self._content.render(scroll_content_rect)
    rl.end_scissor_mode()

    button_y = content_rect.y + content_rect.height - button_height
    if self._show_clear_button:
      button_width = (content_rect.width - button_spacing) // 2
      clear_rect = rl.Rectangle(content_rect.x, button_y, button_width, button_height)
      ok_rect = rl.Rectangle(content_rect.x + content_rect.width - button_width, button_y, button_width, button_height)
      self._clear_button.render(clear_rect)
      self._ok_button.render(ok_rect)
    else:
      button_width = (rect.width - 3 * 50) // 3
      ok_rect = rl.Rectangle(content_rect.x + content_rect.width - button_width, button_y, button_width, button_height)
      self._ok_button.render(ok_rect)

    return -1
