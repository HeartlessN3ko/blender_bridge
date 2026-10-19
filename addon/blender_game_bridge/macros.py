"""One-click macros. Each entry is a label plus a list of bridge commands run in order.
Add your own here. They show up as buttons in the Blender panel and the browser controller.

Any command from commands.py works as a step. Steps run on the current selection.
"""

MACROS = {
    "stand_up": {
        "label": "Stand up",
        "hint": "Rotate 90 on X so a flat thing stands upright",
        "steps": [{"cmd": "rotate", "axis": "x", "degrees": 90}],
    },
    "lay_flat": {
        "label": "Lay flat",
        "hint": "Rotate -90 on X",
        "steps": [{"cmd": "rotate", "axis": "x", "degrees": -90}],
    },
    "turn_around": {
        "label": "Turn around",
        "hint": "Spin 180 so it faces the other way",
        "steps": [{"cmd": "rotate", "axis": "z", "degrees": 180}],
    },
    "quarter_turn": {
        "label": "Quarter turn",
        "hint": "Spin 90 on Z",
        "steps": [{"cmd": "rotate", "axis": "z", "degrees": 90}],
    },
    "row_of_3": {
        "label": "Row of 3",
        "hint": "Two more copies along X, spaced by the object's width",
        "steps": [
            {"cmd": "duplicate"}, {"cmd": "move", "dx": "$width"},
            {"cmd": "duplicate"}, {"cmd": "move", "dx": "$width"},
        ],
    },
    "stack_of_3": {
        "label": "Stack of 3",
        "hint": "Two more copies stacked upward",
        "steps": [
            {"cmd": "duplicate"}, {"cmd": "move", "dz": "$height"},
            {"cmd": "duplicate"}, {"cmd": "move", "dz": "$height"},
        ],
    },
    "double_size": {"label": "Double size", "hint": "", "steps": [{"cmd": "scale", "factor": 2}]},
    "half_size": {"label": "Half size", "hint": "", "steps": [{"cmd": "scale", "factor": 0.5}]},
    "reset": {
        "label": "Reset transform",
        "hint": "Rotation 0, scale 1, keep position",
        "steps": [{"cmd": "set_rotation", "x": 0, "y": 0, "z": 0}, {"cmd": "set_scale", "x": 1, "y": 1, "z": 1}],
    },
}
