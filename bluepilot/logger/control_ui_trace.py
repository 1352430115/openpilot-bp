#!/usr/bin/env python3
"""
Trace root variables that drive lateral/longitudinal control — not UI border colors.

Logs state transitions and the underlying signals/events that cause them.
"""
from __future__ import annotations

from typing import Any

from openpilot.common.swaglog import cloudlog

# Lateral/longitudinal control trace logging. Set True when actively debugging.
_CONTROL_TRACE_ENABLED = False

MADS_STATE_NAMES = {
  0: "disabled",
  1: "enabled",
  2: "softDisabling",
  3: "paused",
  4: "overriding",
}


def _event(name: str, **kwargs: Any) -> None:
  if not _CONTROL_TRACE_ENABLED:
    return
  cloudlog.event(f"bp_control_trace.{name}", **kwargs)


def _mads_state_name(state: Any) -> str:
  try:
    return MADS_STATE_NAMES.get(int(state), str(state))
  except Exception:
    return str(state)


def _event_names(events) -> list[str]:
  try:
    if hasattr(events, "get_event_name"):
      return sorted(str(events.get_event_name(e)) for e in events.names)
    return sorted(str(e) for e in events.names)
  except Exception:
    return []


class ControlUiTracer:
  """Transition-only logging of root control variables."""

  _ss_enabled: bool | None = None
  _ss_active: bool | None = None
  _ss_state: str | None = None
  _mads_enabled: bool | None = None
  _mads_active: bool | None = None
  _mads_state: str | None = None
  _lat_active: bool | None = None
  _long_active: bool | None = None
  _events_sp_names: frozenset[str] | None = None
  _onroad_event_names: frozenset[str] | None = None

  @classmethod
  def on_vehicle_started(cls, *, ignition: bool, started: bool) -> None:
    _event("vehicle_started", ignition=ignition, started=started)

  @classmethod
  def on_selfdrive_state(
    cls,
    *,
    enabled: bool,
    active: bool,
    state: str,
    experimental_mode: bool,
    op_long: bool,
  ) -> None:
    if cls._ss_enabled == enabled and cls._ss_active == active and cls._ss_state == state:
      return
    _event(
      "selfdrive_state",
      enabled=enabled,
      active=active,
      state=state,
      prev_enabled=cls._ss_enabled,
      prev_active=cls._ss_active,
      prev_state=cls._ss_state,
      experimental_mode=experimental_mode,
      openpilot_longitudinal=op_long,
    )
    cls._ss_enabled = enabled
    cls._ss_active = active
    cls._ss_state = state

  @classmethod
  def on_mads_events_sp(cls, events_sp, *, cruise_available: bool, cruise_enabled: bool, cruise_edge: bool) -> None:
    names = frozenset(_event_names(events_sp))
    added = sorted(names - (cls._events_sp_names or frozenset()))
    removed = sorted((cls._events_sp_names or frozenset()) - names)
    if not added and not removed:
      return
    cls._events_sp_names = names
    _event(
      "mads_events_sp",
      added=added,
      removed=removed,
      active=sorted(names),
      cruise_available=cruise_available,
      cruise_enabled=cruise_enabled,
      cruise_available_edge=cruise_edge,
    )
    for ev in added:
      if "lkas" in ev.lower() or "silent" in ev.lower():
        _event("mads_lkas_signal", event=ev, cruise_edge=cruise_edge, cruise_enabled=cruise_enabled)

  @classmethod
  def on_onroad_events(cls, events, events_sp) -> None:
    op_names = frozenset(_event_names(events))
    sp_names = frozenset(_event_names(events_sp))
    combined = op_names | sp_names
    if combined == cls._onroad_event_names:
      return
    added = sorted(combined - (cls._onroad_event_names or frozenset()))
    cls._onroad_event_names = combined
    blocking = [n for n in added if n in (
      "commIssue", "commIssueAvgFreq", "processNotRunning", "canBusMissing", "canError",
      "wrongGear", "doorOpen", "seatbeltNotLatched", "parkingBrake", "wrongCarMode",
    )]
    if added:
      _event("onroad_events", added=added, blocking=blocking, op_events=sorted(op_names), sp_events=sorted(sp_names))

  @classmethod
  def on_mads_state_machine(
    cls,
    *,
    prev_state: Any,
    new_state: Any,
    enabled: bool,
    active: bool,
    events,
    events_sp,
    cs,
  ) -> None:
    prev_name = _mads_state_name(prev_state)
    new_name = _mads_state_name(new_state)
    if prev_name == new_name and cls._mads_enabled == enabled and cls._mads_active == active:
      return

    from cereal import log
    from openpilot.selfdrive.selfdrived.events import ET as ET_OP

    ctx = {
      "prev_state": prev_name,
      "new_state": new_name,
      "enabled": enabled,
      "active": active,
      "prev_enabled": cls._mads_enabled,
      "prev_active": cls._mads_active,
      "has_enable": events.contains(ET_OP.ENABLE),
      "has_no_entry": events.contains(ET_OP.NO_ENTRY),
      "has_soft_disable": events.contains(ET_OP.SOFT_DISABLE),
      "has_immediate_disable": events.contains(ET_OP.IMMEDIATE_DISABLE),
      "has_user_disable": events.contains(ET_OP.USER_DISABLE),
      "has_override_lateral": events.contains(ET_OP.OVERRIDE_LATERAL),
      "has_pcm_enable": events.has(log.OnroadEvent.EventName.pcmEnable),
      "has_button_enable": events.has(log.OnroadEvent.EventName.buttonEnable),
      "events_sp": _event_names(events_sp),
      "gear": str(cs.gearShifter),
      "door_open": bool(cs.doorOpen),
      "seatbelt_unlatched": bool(cs.seatbeltUnlatched),
      "standstill": bool(cs.standstill),
      "cruise_available": bool(cs.cruiseState.available),
      "cruise_enabled": bool(cs.cruiseState.enabled),
      "v_ego_mph": round(cs.vEgo * 2.237, 1),
    }
    _event("mads_state", **ctx)

    if new_name == "paused" and prev_name != "paused":
      _event("mads_root_paused", reason="NO_ENTRY_or_silent_preconditions", **ctx)
    elif new_name == "enabled" and active and (prev_name != "enabled" or not cls._mads_active):
      _event("mads_root_lateral_armed", reason="MADS active — latActive can become true", **ctx)

    cls._mads_enabled = enabled
    cls._mads_active = active
    cls._mads_state = new_name

  @classmethod
  def on_lat_decision(
    cls,
    *,
    lat_active: bool,
    lat_requested: bool,
    lat_gates_failed: list[str],
    mads_available: bool,
    mads_active: bool,
    mads_enabled: bool,
    mads_state: str,
    ss_active: bool,
    curvature: float,
    desired_curvature: float,
  ) -> None:
    if cls._lat_active == lat_active and lat_requested == getattr(cls, "_lat_requested", None):
      return
    prev = cls._lat_active
    cls._lat_active = lat_active
    cls._lat_requested = lat_requested  # type: ignore[attr-defined]

    _event(
      "lat_decision",
      lat_active=lat_active,
      prev_lat_active=prev,
      lat_requested=lat_requested,
      lat_gates_failed=lat_gates_failed,
      mads_available=mads_available,
      mads_active=mads_active,
      mads_enabled=mads_enabled,
      mads_state=mads_state,
      ss_active_fallback=ss_active,
      curvature=round(curvature, 6),
      desired_curvature=round(desired_curvature, 6),
    )

  @classmethod
  def on_long_decision(
    cls,
    *,
    long_active: bool,
    cc_enabled: bool,
    override_longitudinal: bool,
    op_long: bool,
    pcm_cruise_speed: bool,
    accel: float,
    long_control_state: str,
    cruise_enabled: bool,
    v_ego_mph: float,
  ) -> None:
    if cls._long_active == long_active:
      return
    prev = cls._long_active
    cls._long_active = long_active
    _event(
      "long_decision",
      long_active=long_active,
      prev_long_active=prev,
      cc_enabled=cc_enabled,
      override_longitudinal=override_longitudinal,
      openpilot_longitudinal=op_long,
      pcm_cruise_speed=pcm_cruise_speed,
      long_via_op_can=op_long,
      long_via_pcm_icbm=pcm_cruise_speed and not op_long,
      accel=round(accel, 3),
      long_control_state=str(long_control_state),
      cruise_enabled=cruise_enabled,
      v_ego_mph=round(v_ego_mph, 1),
    )
