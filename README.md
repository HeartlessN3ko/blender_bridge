# Blender Game Bridge

Game-style control layer on top of Blender. Three parts, one port.

```
addon/blender_game_bridge/   Blender add-on: big-button panel, W/E/R hotkeys, socket server
controller/controller.html   Browser controller: nudge pad, sliders, joystick, WASD fly
client/bridge_client.py      Python library + CLI (script Blender from a terminal or from Claude)
```

## Install (Blender 3.3+ / 4.x)

1. Zip the add-on: `cd addon && zip -r blender_game_bridge.zip blender_game_bridge` (or use the prebuilt `blender_game_bridge.zip`).
2. Blender > Edit > Preferences > Add-ons > Install > pick the zip > enable **Game Bridge**.
3. The server starts on `127.0.0.1:8765` automatically. Sidebar tab **Game Bridge** shows status.

Hotkeys in Object mode (edit `tunables.py` to change):

| Key | Does |
|---|---|
| Q / W / E / R | Select / Move / Rotate / Scale tool |
| F | Walk/fly navigation (WASD + mouse look, Esc to exit) |
| Z | Frame selected |
| + / - (hold) | Gentle grow/shrink, 2% per tick |

### Arrow scheme (Blender and the browser controller, same keys)

| Keys | Does |
|---|---|
| Arrows | Pan the camera left/right/up/down |
| Shift + Up/Down | Camera forward/back |
| Ctrl + arrows | Use the active tool on the selected object |
| Ctrl + Alt + arrows | Same tool, the other axis |

What Ctrl + arrows does per tool:

| Tool | Ctrl | Ctrl + Alt |
|---|---|---|
| Move / Select | Nudge in the view plane | Up/Down: nudge world Z |
| Rotate | Left/Right: yaw (Z). Up/Down: tilt (X) | Left/Right: roll (Y) |
| Scale | Up/Down: grow/shrink. Left/Right: stretch Y | Left/Right: stretch X. Up/Down: stretch Z |

Steps live in tunables: `ARROW_PAN`, `ARROW_ROTATE_STEP`, `SCALE_GENTLE_STEP`, `NUDGE_STEP`.

## Browser controller

Open `controller/controller.html` in any browser. It connects to `ws://127.0.0.1:8765`.
Hotbar across the top: 1-8 keys for Select, Move, Rotate, Scale, Add, Dupe, Frame, Delete.
Size control is a spring slider: drag away from center to grow or shrink at a rate, let go to stop.
Arrows follow the scheme above. Pick an object from the dropdown, drag dimension and position
sliders, drag the joystick or hold Shift+WASD to fly the viewport.
Readout updates after every command. Works on a phone on the same LAN if you set
`HOST` in tunables to `0.0.0.0` (then it's open to your network; your call).

## CLI / scripting

```
python3 client/bridge_client.py state
python3 client/bridge_client.py select Cube
python3 client/bridge_client.py move --dx 1 --dz 0.5
python3 client/bridge_client.py rotate --axis z --degrees 45
python3 client/bridge_client.py dims --x 2 --y 2 --z 0.5
python3 client/bridge_client.py add cylinder --name Pillar --x 3
python3 client/bridge_client.py cam --forward 2 --yaw -1
python3 client/bridge_client.py exec "bpy.ops.object.shade_smooth()"
python3 client/bridge_client.py repl        # type: move dx=1   or   {"cmd":"snap","on":true}
```

From Python:

```python
from bridge_client import Bridge
with Bridge() as b:
    b.select("Cube")
    b.set_dimensions(x=2, y=1, z=0.25)
    b.rotate("z", 30)
    print(b.state()["active"])
```

## Protocol

One JSON object per message, `{"cmd": "...", "id": n, ...args}`. Reply:
`{"ok": true, "id": n, "result": ..., "state": {...}}` or `{"ok": false, "error": "..."}`.
Raw clients send newline-delimited JSON; browsers use WebSocket text frames. Same port.

| cmd | args |
|---|---|
| `ping`, `state`, `list_objects` | |
| `select` | `name`, `extend` |
| `select_all`, `deselect` | |
| `set_mode` | `mode`: select, move, rotate, scale |
| `move` | `dx dy dz`, `space`: world or view |
| `set_location`, `set_rotation`, `set_scale`, `set_dimensions` | any of `x y z` (rotation in degrees) |
| `rotate` | `axis`, `degrees`, `local` |
| `scale` | `factor` or `sx sy sz` |
| `snap` | `on` (omit to toggle) |
| `camera` | `forward right up yaw pitch zoom` (units scaled by tunables) |
| `pan` | `right up forward` in ARROW_PAN units |
| `arrow` | `dir` left/right/up/down, `ctrl`, `alt`, `shift` (tool-aware, see Arrow scheme) |
| `frame`, `fly`, `undo`, `redo`, `delete`, `duplicate` | |
| `view_axis` | `axis`: TOP, FRONT, RIGHT, ... |
| `add` | `type` cube/sphere/cylinder/cone/plane/torus/monkey, `name`, `x y z` |
| `rename` | `name` |
| `select_group` | `by`: prefix / collection / type / children / all, `value`, `extend` |
| `mirror` | `axis`, `clone` (keep original), `pivot`: cursor / origin / active / center |
| `flip` | `which`: upside_down / left_right / around |
| `drop_to_floor`, `center`, `copy`, `paste`, `apply`, `group`, `ungroup` | `center` takes `pivot`, `z` |
| `list_macros` | |
| `macro` | `name` from macros.py, or inline `steps`: [{cmd...}, ...] |

## One-click actions and macros

The panel and the controller both have a "Do to selection" block: clone to the other side,
mirror, flip, drop to floor, center, copy/paste, group/ungroup. Mirror and center pivot on the
3D cursor (Shift+right-click in Blender to place it), so "clone to other side" means
"across the cursor."

`addon/blender_game_bridge/macros.py` holds named command sequences. Each becomes a button.
Steps can use `$width`, `$depth`, `$height` (active object's dimensions) and `$step`:

```python
"row_of_3": {
    "label": "Row of 3",
    "hint": "Two more copies along X",
    "steps": [{"cmd": "duplicate"}, {"cmd": "move", "dx": "$width"},
              {"cmd": "duplicate"}, {"cmd": "move", "dx": "$width"}],
},
```

Edit the file, hit the controller's refresh button. No add-on reload needed for macros.
| `save` | `path` (optional) |
| `exec` | `code`, `eval` (set `ALLOW_EXEC = 0` in tunables to disable) |

## Tunables

Everything adjustable lives in `addon/blender_game_bridge/tunables.py`: port, step sizes,
snap increments, camera speeds, hotkeys, panel scale, exec permission.
Edit, then disable/re-enable the add-on.

## Limits

* Snapping applies to bridge commands only. Blender's own gizmo snapping is its own setting (the panel toggle sets both).
* `fly` and `frame` need a 3D viewport visible. Multiple viewports: the first one wins.
* Browser `exec` is loopback only by default. Don't expose port 8765 beyond localhost with exec on.
