"""Command dispatch. Every command is a dict with "cmd" plus arguments.
Returns {"ok": True, "result": ...} or {"ok": False, "error": "..."}.
Runs on Blender's main thread only.
"""
import math

import bpy
from mathutils import Matrix, Vector

from . import tunables as T

TOOL_IDS = {
    "select": "builtin.select_box",
    "move": "builtin.move",
    "rotate": "builtin.rotate",
    "scale": "builtin.scale",
}


# ---- context helpers -------------------------------------------------------
def _view3d():
    """Return (window, area, region, space) for the first 3D viewport, or Nones."""
    wm = bpy.context.window_manager
    for window in wm.windows:
        for area in window.screen.areas:
            if area.type != "VIEW_3D":
                continue
            for region in area.regions:
                if region.type == "WINDOW":
                    return window, area, region, area.spaces.active
    return None, None, None, None


def _override():
    window, area, region, space = _view3d()
    if not area:
        return None
    return dict(window=window, area=area, region=region, screen=window.screen)


def _run_in_view(fn):
    ov = _override()
    if ov is None:
        raise RuntimeError("no 3D viewport open")
    with bpy.context.temp_override(**ov):
        return fn()


def _active():
    obj = bpy.context.view_layer.objects.active
    if obj is None or not obj.select_get():
        sel = bpy.context.selected_objects
        if not sel:
            raise RuntimeError("nothing selected")
        obj = sel[0]
    return obj


def _selected():
    sel = bpy.context.selected_objects
    if not sel:
        raise RuntimeError("nothing selected")
    return sel


def _f(msg, key, default=0.0):
    try:
        return float(msg.get(key, default))
    except (TypeError, ValueError):
        raise RuntimeError(f"{key} must be a number")


def _snap_val(v, inc):
    return round(v / inc) * inc if inc else v


def _view_axes():
    """World-space right/up/forward vectors of the viewport camera."""
    _, _, _, space = _view3d()
    if not space:
        return Vector((1, 0, 0)), Vector((0, 0, 1)), Vector((0, 1, 0))
    rot = space.region_3d.view_rotation
    right = rot @ Vector((1, 0, 0))
    up = rot @ Vector((0, 1, 0))
    fwd = rot @ Vector((0, 0, -1))
    return right, up, fwd


# ---- state readout ---------------------------------------------------------
def object_state(obj):
    return {
        "name": obj.name,
        "type": obj.type,
        "location": [round(v, 4) for v in obj.location],
        "rotation_deg": [round(math.degrees(v), 2) for v in obj.rotation_euler],
        "scale": [round(v, 4) for v in obj.scale],
        "dimensions": [round(v, 4) for v in obj.dimensions],
    }


def scene_state():
    ts = bpy.context.scene.tool_settings
    act = bpy.context.view_layer.objects.active
    return {
        "active": object_state(act) if act and act.select_get() else None,
        "selected": [o.name for o in bpy.context.selected_objects],
        "mode": bpy.context.mode,
        "snap": bool(ts.use_snap),
        "tool": _current_tool(),
        "objects": [o.name for o in bpy.context.scene.objects],
    }


def _current_tool():
    try:
        from bl_ui.space_toolsystem_common import ToolSelectPanelHelper
        tool = ToolSelectPanelHelper.tool_active_from_context(bpy.context)
        return tool.idname if tool else None
    except Exception:
        return None


# ---- commands --------------------------------------------------------------
def cmd_ping(msg):
    return "pong"


def cmd_state(msg):
    return scene_state()


def cmd_list_objects(msg):
    return [object_state(o) for o in bpy.context.scene.objects]


def cmd_select(msg):
    name = msg.get("name")
    obj = bpy.context.scene.objects.get(name)
    if obj is None:
        raise RuntimeError(f"no object named {name!r}")
    if not msg.get("extend"):
        for o in bpy.context.selected_objects:
            o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    return object_state(obj)


def cmd_select_all(msg):
    for o in bpy.context.scene.objects:
        o.select_set(True)
    return len(bpy.context.selected_objects)


def cmd_deselect(msg):
    for o in bpy.context.selected_objects:
        o.select_set(False)
    return 0


def cmd_set_mode(msg):
    mode = msg.get("mode", "move")
    if mode not in TOOL_IDS:
        raise RuntimeError(f"mode must be one of {list(TOOL_IDS)}")
    _run_in_view(lambda: bpy.ops.wm.tool_set_by_id(name=TOOL_IDS[mode]))
    return mode


def cmd_move(msg):
    space = msg.get("space", "world")
    d = Vector((_f(msg, "dx"), _f(msg, "dy"), _f(msg, "dz")))
    if space == "view":
        right, up, fwd = _view_axes()
        d = right * d.x + up * d.y + fwd * d.z
    snap = bpy.context.scene.tool_settings.use_snap
    for obj in _selected():
        obj.location += d
        if snap:
            inc = T.SNAP_INCREMENT
            obj.location = Vector(_snap_val(v, inc) for v in obj.location)
    return object_state(_active())


def cmd_set_location(msg):
    obj = _active()
    loc = obj.location.copy()
    for i, k in enumerate("xyz"):
        if k in msg:
            loc[i] = _f(msg, k)
    obj.location = loc
    return object_state(obj)


def cmd_rotate(msg):
    axis = str(msg.get("axis", "z")).lower()
    if axis not in "xyz" or len(axis) != 1:
        raise RuntimeError("axis must be x, y or z")
    deg = _f(msg, "degrees")
    snap = bpy.context.scene.tool_settings.use_snap
    if snap:
        deg = _snap_val(deg, T.SNAP_ANGLE)
    rot = Matrix.Rotation(math.radians(deg), 4, axis.upper())
    r3 = rot.to_3x3()
    for obj in _selected():
        basis = obj.rotation_euler.to_matrix()
        new = basis @ r3 if msg.get("local") else r3 @ basis
        obj.rotation_euler = new.to_euler(obj.rotation_euler.order)
    return object_state(_active())


def cmd_set_rotation(msg):
    obj = _active()
    e = list(obj.rotation_euler)
    for i, k in enumerate("xyz"):
        if k in msg:
            e[i] = math.radians(_f(msg, k))
    obj.rotation_euler = e
    return object_state(obj)


def cmd_scale(msg):
    if "factor" in msg:
        f = _f(msg, "factor", 1.0)
        fac = Vector((f, f, f))
    else:
        fac = Vector((_f(msg, "sx", 1.0), _f(msg, "sy", 1.0), _f(msg, "sz", 1.0)))
    for obj in _selected():
        obj.scale = Vector(a * b for a, b in zip(obj.scale, fac))
    return object_state(_active())


def cmd_set_scale(msg):
    obj = _active()
    s = list(obj.scale)
    for i, k in enumerate("xyz"):
        if k in msg:
            s[i] = _f(msg, k)
    obj.scale = s
    return object_state(obj)


def cmd_set_dimensions(msg):
    obj = _active()
    d = list(obj.dimensions)
    for i, k in enumerate("xyz"):
        if k in msg:
            d[i] = max(_f(msg, k), 0.0001)
    obj.dimensions = d
    bpy.context.view_layer.update()
    return object_state(obj)


def cmd_snap(msg):
    ts = bpy.context.scene.tool_settings
    if "on" in msg:
        ts.use_snap = bool(msg["on"])
    else:
        ts.use_snap = not ts.use_snap
    ts.snap_elements = {"INCREMENT"}
    return ts.use_snap


def cmd_camera(msg):
    """Fly the viewport. forward/right/up in CAM_MOVE_SPEED units, yaw/pitch in CAM_TURN_SPEED units, zoom in CAM_ZOOM_SPEED percent units."""
    _, area, _, space = _view3d()
    if not space:
        raise RuntimeError("no 3D viewport open")
    r3d = space.region_3d
    right, up, fwd = _view_axes()
    move = (right * _f(msg, "right") + up * _f(msg, "up") + fwd * _f(msg, "forward")) * T.CAM_MOVE_SPEED
    r3d.view_location += move
    yaw = math.radians(_f(msg, "yaw") * T.CAM_TURN_SPEED)
    pitch = math.radians(_f(msg, "pitch") * T.CAM_TURN_SPEED)
    if yaw:
        r3d.view_rotation = Matrix.Rotation(-yaw, 3, "Z").to_quaternion() @ r3d.view_rotation
    if pitch:
        r3d.view_rotation = r3d.view_rotation @ Matrix.Rotation(pitch, 3, "X").to_quaternion()
    zoom = _f(msg, "zoom")
    if zoom:
        r3d.view_distance = max(0.01, r3d.view_distance * (1 - zoom * T.CAM_ZOOM_SPEED / 100.0))
    area.tag_redraw()
    return {"view_location": [round(v, 3) for v in r3d.view_location], "distance": round(r3d.view_distance, 3)}


def cmd_pan(msg):
    """Slide the viewport in screen space. right/up/forward are multiples of ARROW_PAN percent of view distance."""
    _, area, _, space = _view3d()
    if not space:
        raise RuntimeError("no 3D viewport open")
    r3d = space.region_3d
    right, up, fwd = _view_axes()
    step = r3d.view_distance * T.ARROW_PAN / 100.0
    r3d.view_location += (right * _f(msg, "right") + up * _f(msg, "up") + fwd * _f(msg, "forward")) * step
    area.tag_redraw()
    return [round(v, 3) for v in r3d.view_location]


ARROW_VEC = {"left": (-1, 0), "right": (1, 0), "up": (0, 1), "down": (0, -1)}


def cmd_arrow(msg):
    """Tool-aware arrow key. dir: left/right/up/down. ctrl/alt flags.
    No modifier         -> camera pan (shift: forward/back on up/down)
    Ctrl, Move tool     -> nudge in the view plane (alt: nudge world Z on up/down)
    Ctrl, Rotate tool   -> left/right yaw (Z), up/down tilt (X); Alt swaps to roll (Y) on left/right
    Ctrl, Scale tool    -> up/down grow/shrink gently; Alt + left/right stretch X, Alt + up/down stretch Z
    Ctrl, Select tool   -> same as Move
    """
    d = str(msg.get("dir", "")).lower()
    if d not in ARROW_VEC:
        raise RuntimeError("dir must be left/right/up/down")
    h, v = ARROW_VEC[d]
    ctrl, alt, shift = bool(msg.get("ctrl")), bool(msg.get("alt")), bool(msg.get("shift"))
    if not ctrl:
        if shift:
            return cmd_pan({"right": h, "forward": v})
        return cmd_pan({"right": h, "up": v})
    tool = (_current_tool() or "").rsplit(".", 1)[-1]
    if tool == "rotate":
        step = T.ARROW_ROTATE_STEP
        if alt and h:
            return cmd_rotate({"axis": "y", "degrees": h * step})
        if h:
            return cmd_rotate({"axis": "z", "degrees": -h * step})
        return cmd_rotate({"axis": "x", "degrees": v * step})
    if tool == "scale":
        f = 1 + T.SCALE_GENTLE_STEP / 100.0
        if alt:
            if h:
                return cmd_scale({"sx": f if h > 0 else 1 / f})
            return cmd_scale({"sz": f if v > 0 else 1 / f})
        if h:
            return cmd_scale({"sy": f if h > 0 else 1 / f})
        return cmd_scale({"factor": f if v > 0 else 1 / f})
    # move / select / anything else
    s = T.NUDGE_STEP
    if alt and v:
        return cmd_move({"dz": v * s})
    return cmd_move({"dx": h * s, "dy": v * s, "space": "view"})


def cmd_frame(msg):
    _run_in_view(lambda: bpy.ops.view3d.view_selected())
    return True


def cmd_view_axis(msg):
    axis = msg.get("axis", "TOP")
    _run_in_view(lambda: bpy.ops.view3d.view_axis(type=axis.upper()))
    return axis


def cmd_fly(msg):
    _run_in_view(lambda: bpy.ops.view3d.walk("INVOKE_DEFAULT"))
    return True


def cmd_undo(msg):
    bpy.ops.ed.undo()
    return True


def cmd_redo(msg):
    bpy.ops.ed.redo()
    return True


def cmd_delete(msg):
    names = [o.name for o in _selected()]
    _run_in_view(lambda: bpy.ops.object.delete())
    return names


def cmd_duplicate(msg):
    _run_in_view(lambda: bpy.ops.object.duplicate())
    return object_state(_active())


PRIMITIVES = {
    "cube": "primitive_cube_add",
    "sphere": "primitive_uv_sphere_add",
    "cylinder": "primitive_cylinder_add",
    "cone": "primitive_cone_add",
    "plane": "primitive_plane_add",
    "torus": "primitive_torus_add",
    "monkey": "primitive_monkey_add",
}


def cmd_add(msg):
    kind = msg.get("type", "cube")
    if kind not in PRIMITIVES:
        raise RuntimeError(f"type must be one of {list(PRIMITIVES)}")
    loc = (_f(msg, "x"), _f(msg, "y"), _f(msg, "z"))
    op = getattr(bpy.ops.mesh, PRIMITIVES[kind])
    _run_in_view(lambda: op(location=loc))
    obj = _active()
    if msg.get("name"):
        obj.name = msg["name"]
    return object_state(obj)


def cmd_rename(msg):
    obj = _active()
    obj.name = str(msg.get("name", obj.name))
    return object_state(obj)


def cmd_save(msg):
    path = msg.get("path") or bpy.data.filepath
    if not path:
        raise RuntimeError("file has never been saved; pass a path")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    return path


def cmd_exec(msg):
    if not T.ALLOW_EXEC:
        raise RuntimeError("exec disabled in tunables")
    code = msg.get("code", "")
    ns = {"bpy": bpy, "C": bpy.context, "D": bpy.data, "Vector": Vector, "math": math}
    if msg.get("eval"):
        return repr(eval(code, ns))
    exec(code, ns)
    return ns.get("result", True)


COMMANDS = {
    name[4:]: fn for name, fn in list(globals().items()) if name.startswith("cmd_")
}


def handle(msg):
    if not isinstance(msg, dict):
        return {"ok": False, "error": "message must be an object"}
    name = msg.get("cmd")
    fn = COMMANDS.get(name)
    if fn is None:
        return {"ok": False, "error": f"unknown cmd {name!r}; known: {sorted(COMMANDS)}"}
    try:
        result = fn(msg)
        reply = {"ok": True, "cmd": name, "result": result}
    except Exception as e:  # report to client rather than crash the timer
        reply = {"ok": False, "cmd": name, "error": str(e)}
    if T.PUSH_STATE_AFTER_COMMAND and name not in ("ping", "state"):
        try:
            reply["state"] = scene_state()
        except Exception as e:
            reply["state_error"] = str(e)
    return reply
