# Changelog

## 0.3.0 (2026-10-19)
- One-click actions: clone to other side, mirror L/R and F/B, flip upside down, turn around, drop to floor, center on cursor, copy, paste, group, ungroup, apply.
- Pick-many: same name, same collection, same kind, children, all.
- Macros: `macros.py` defines named command sequences with `$width/$depth/$height` substitution. Hot-reloaded on each run. Ships with 9 starters.
- Controller: rebuilt as numbered plain-English cards (pick, do, macros, move, rotate, size, camera, add). Rotate buttons say spin/tilt/roll. Cheat sheet collapsed.
- Panel: Pick many, Do to selection, and Macros boxes.

## 0.2.0 (2026-10-19)
- Arrow keys pan the camera in Blender and in the controller. Shift+Up/Down moves forward/back.
- Ctrl+arrows act on the selected object with the active tool. Ctrl+Alt+arrows hit the other axis (rotate: yaw/tilt/roll, scale: per-axis stretch).
- Hold + / - for gentle 2% resize. New `SCALE_GENTLE_STEP`, `ARROW_ROTATE_STEP`, `ARROW_PAN` tunables.
- Controller: hotbar with 1-8 quick keys, spring-back size slider, key cheat sheet, -2%/+2% buttons.
- New commands: `pan`, `arrow`.

## 0.1.0 (2026-10-19)
- Add-on: stdlib WebSocket + JSON-lines server on one port, drained on Blender's main thread via timer.
- Add-on: 27 commands (select, move/rotate/scale deltas and absolutes, dimensions, snap, camera fly, primitives, undo/redo, exec).
- Add-on: Game Bridge sidebar panel with big mode buttons, nudge/rotate/scale pads, dimension fields, snap/frame/fly.
- Add-on: Q/W/E/R tool hotkeys, F walk/fly, Z frame. All in tunables.py.
- Controller: single-file browser UI with mode buttons, nudge pad, dimension/position sliders, joystick, Shift+WASD fly, readout.
- Client: Python library + CLI with repl mode.
- Verified: server handshake and framing against a raw client and a hand-rolled WebSocket client. Not yet run inside Blender.
