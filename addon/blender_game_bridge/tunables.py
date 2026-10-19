"""Game Bridge tunables. Edit these, reload the add-on. No other file needs touching.

Integers unless stated. Ranges are documented per value.
"""

# ---- Network -------------------------------------------------------------
HOST = "127.0.0.1"          # Bind address. Keep loopback unless you know why.
PORT = 8765                 # 1024-65535. Controller + CLI must match.
AUTOSTART_SERVER = 1        # 0/1. Start the socket server when the add-on loads.
TICK_MS = 16                # 5-100. How often Blender drains the command queue.
MAX_MESSAGE_BYTES = 1_000_000  # Reject single messages above this size.

# ---- Safety --------------------------------------------------------------
ALLOW_EXEC = 1              # 0/1. Allow the "exec" command (arbitrary Python). Loopback only anyway.
PUSH_STATE_AFTER_COMMAND = 1  # 0/1. Send selection/transform readout after every command.

# ---- Transform defaults --------------------------------------------------
NUDGE_STEP = 0.1            # float, meters. Panel nudge buttons and default move delta.
ROTATE_STEP = 15            # 1-180 degrees. Panel rotate buttons.
SCALE_STEP = 10             # 1-100 percent. Panel scale buttons.
SCALE_GENTLE_STEP = 2       # 1-20 percent. Hold +/- keys for a slow, smooth resize.
ARROW_ROTATE_STEP = 5       # 1-90 degrees per arrow press in Rotate mode (Ctrl/Alt + arrows).
ARROW_PAN = 8               # 1-50 percent of view distance per arrow press (camera pan).
SNAP_INCREMENT = 0.25       # float, meters. Grid increment when snap is on.
SNAP_ANGLE = 15             # 1-90 degrees. Rotation increment when snap is on.

# ---- Camera --------------------------------------------------------------
CAM_MOVE_SPEED = 0.25       # float, meters per camera command unit.
CAM_TURN_SPEED = 3          # 1-45 degrees per camera command unit.
CAM_ZOOM_SPEED = 10         # 1-100 percent of view distance per zoom unit.

# ---- Hotkeys (3D viewport, Object mode) ----------------------------------
ENABLE_HOTKEYS = 1          # 0/1. Register the game-style keys below.
KEY_MOVE = "W"              # Tool: move
KEY_ROTATE = "E"            # Tool: rotate
KEY_SCALE = "R"             # Tool: scale
KEY_SELECT = "Q"            # Tool: select box
KEY_FLY = "F"               # Toggle walk/fly navigation (WASD + mouse look)
KEY_FRAME = "Z"             # Frame selected object
KEY_BIGGER = "EQUAL"        # Hold for gentle grow (also NUMPAD_PLUS)
KEY_SMALLER = "MINUS"       # Hold for gentle shrink (also NUMPAD_MINUS)
# Arrow keys are always bound:
#   plain        pan the camera left/right/up/down, Ctrl+Shift up/down = forward/back
#   Ctrl         act on the selected object using the active tool (see README "Arrow scheme")
#   Alt          the "other axis" variant of the same tool

# ---- Panel ---------------------------------------------------------------
PANEL_CATEGORY = "Game Bridge"  # N-panel tab name.
BIG_BUTTON_SCALE = 1.6      # float 1.0-3.0. Vertical scale of the main buttons.
