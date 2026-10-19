# Changelog

## 0.1.0 (2026-10-19)
- Add-on: stdlib WebSocket + JSON-lines server on one port, drained on Blender's main thread via timer.
- Add-on: 27 commands (select, move/rotate/scale deltas and absolutes, dimensions, snap, camera fly, primitives, undo/redo, exec).
- Add-on: Game Bridge sidebar panel with big mode buttons, nudge/rotate/scale pads, dimension fields, snap/frame/fly.
- Add-on: Q/W/E/R tool hotkeys, F walk/fly, Z frame. All in tunables.py.
- Controller: single-file browser UI with mode buttons, nudge pad, dimension/position sliders, joystick, Shift+WASD fly, readout.
- Client: Python library + CLI with repl mode.
- Verified: server handshake and framing against a raw client and a hand-rolled WebSocket client. Not yet run inside Blender.
