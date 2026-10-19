bl_info = {
    "name": "Game Bridge",
    "author": "Skye",
    "version": (0, 1, 0),
    "blender": (3, 3, 0),
    "location": "View3D > Sidebar > Game Bridge",
    "description": "Game-style transform controls, W/E/R hotkeys, and a socket API for external controllers.",
    "category": "Interface",
}

import importlib

import bpy

from . import commands, server, tunables

for m in (tunables, server, commands):
    importlib.reload(m)

T = tunables
_server = None
_keymaps = []


# ---- server lifecycle ------------------------------------------------------
def _tick():
    if _server is None or not _server.running:
        return None
    try:
        _server.drain(commands.handle)
    except Exception as e:  # never let the timer die
        print("[GameBridge] tick error:", e)
    return T.TICK_MS / 1000.0


def start_server():
    global _server
    if _server and _server.running:
        return
    _server = server.BridgeServer(T.HOST, T.PORT, T.MAX_MESSAGE_BYTES)
    _server.start()
    if not bpy.app.timers.is_registered(_tick):
        bpy.app.timers.register(_tick, first_interval=0.1, persistent=True)
    print(f"[GameBridge] listening on {T.HOST}:{T.PORT}")


def stop_server():
    global _server
    if _server:
        _server.stop()
        _server = None
    if bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)
    print("[GameBridge] server stopped")


# ---- operators -------------------------------------------------------------
class GB_OT_cmd(bpy.types.Operator):
    """Run a bridge command from the panel"""
    bl_idname = "gamebridge.cmd"
    bl_label = "Bridge Command"
    bl_options = {"REGISTER", "UNDO"}

    cmd: bpy.props.StringProperty()
    args: bpy.props.StringProperty(default="{}")

    def execute(self, context):
        import json
        msg = json.loads(self.args)
        msg["cmd"] = self.cmd
        reply = commands.handle(msg)
        if not reply.get("ok"):
            self.report({"WARNING"}, reply.get("error", "failed"))
            return {"CANCELLED"}
        return {"FINISHED"}


class GB_OT_server(bpy.types.Operator):
    bl_idname = "gamebridge.server"
    bl_label = "Toggle Bridge Server"
    action: bpy.props.EnumProperty(items=[("START", "Start", ""), ("STOP", "Stop", "")])

    def execute(self, context):
        try:
            start_server() if self.action == "START" else stop_server()
        except OSError as e:
            self.report({"ERROR"}, f"server: {e}")
            return {"CANCELLED"}
        return {"FINISHED"}


class GB_OT_tool(bpy.types.Operator):
    """Hotkey target: switch active tool"""
    bl_idname = "gamebridge.tool"
    bl_label = "Bridge Tool"
    mode: bpy.props.StringProperty(default="move")

    def execute(self, context):
        bpy.ops.wm.tool_set_by_id(name=commands.TOOL_IDS[self.mode])
        return {"FINISHED"}


# ---- panel -----------------------------------------------------------------
def _btn(row, label, cmd, icon="NONE", **args):
    import json
    op = row.operator("gamebridge.cmd", text=label, icon=icon)
    op.cmd = cmd
    op.args = json.dumps(args)


class GB_PT_panel(bpy.types.Panel):
    bl_label = "Game Bridge"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = T.PANEL_CATEGORY

    def draw(self, context):
        L = self.layout
        props = context.scene.gamebridge
        running = _server is not None and _server.running

        box = L.box()
        row = box.row()
        row.label(text=f"Server: {'ON ' + str(T.PORT) if running else 'off'}", icon="LINKED" if running else "UNLINKED")
        row.operator("gamebridge.server", text="Stop" if running else "Start").action = "STOP" if running else "START"

        col = L.column(align=True)
        col.scale_y = T.BIG_BUTTON_SCALE
        row = col.row(align=True)
        _btn(row, "Select", "set_mode", "RESTRICT_SELECT_OFF", mode="select")
        _btn(row, "Move", "set_mode", "ORIENTATION_GLOBAL", mode="move")
        row = col.row(align=True)
        _btn(row, "Rotate", "set_mode", "DRIVER_ROTATIONAL_DIFFERENCE", mode="rotate")
        _btn(row, "Scale", "set_mode", "FULLSCREEN_ENTER", mode="scale")

        L.separator()
        L.prop(props, "step")
        s = props.step
        box = L.box()
        box.label(text="Nudge")
        for axis in "xyz":
            row = box.row(align=True)
            row.scale_y = 1.3
            _btn(row, f"-{axis.upper()}", "move", **{"d" + axis: -s})
            _btn(row, f"+{axis.upper()}", "move", **{"d" + axis: s})

        box = L.box()
        box.label(text=f"Rotate {T.ROTATE_STEP} deg")
        row = box.row(align=True)
        for axis in "xyz":
            _btn(row, f"-{axis.upper()}", "rotate", axis=axis, degrees=-T.ROTATE_STEP)
            _btn(row, f"+{axis.upper()}", "rotate", axis=axis, degrees=T.ROTATE_STEP)

        box = L.box()
        f = 1 + T.SCALE_STEP / 100.0
        row = box.row(align=True)
        _btn(row, f"Smaller {T.SCALE_STEP}%", "scale", factor=1 / f)
        _btn(row, f"Bigger {T.SCALE_STEP}%", "scale", factor=f)

        obj = context.view_layer.objects.active
        if obj and obj.select_get():
            box = L.box()
            box.label(text=f"{obj.name}  dimensions")
            box.prop(obj, "dimensions", text="")

        row = L.row(align=True)
        ts = context.scene.tool_settings
        row.prop(ts, "use_snap", text="Snap", toggle=True, icon="SNAP_INCREMENT")
        _btn(row, "Frame", "frame", "VIEWZOOM")
        _btn(row, "Fly", "fly", "CAMERA_DATA")

        row = L.row(align=True)
        _btn(row, "Undo", "undo", "LOOP_BACK")
        _btn(row, "Redo", "redo", "LOOP_FORWARDS")
        _btn(row, "Dup", "duplicate", "DUPLICATE")
        _btn(row, "Del", "delete", "TRASH")


class GB_Props(bpy.types.PropertyGroup):
    step: bpy.props.FloatProperty(name="Step", default=T.NUDGE_STEP, min=0.001, soft_max=10, unit="LENGTH")


# ---- keymap ----------------------------------------------------------------
def _register_keys():
    if not T.ENABLE_HOTKEYS:
        return
    kc = bpy.context.window_manager.keyconfigs.addon
    if not kc:
        return
    km = kc.keymaps.new(name="Object Mode", space_type="EMPTY")
    for key, mode in ((T.KEY_SELECT, "select"), (T.KEY_MOVE, "move"), (T.KEY_ROTATE, "rotate"), (T.KEY_SCALE, "scale")):
        kmi = km.keymap_items.new("gamebridge.tool", key, "PRESS")
        kmi.properties.mode = mode
        _keymaps.append((km, kmi))
    kmi = km.keymap_items.new("gamebridge.cmd", T.KEY_FLY, "PRESS")
    kmi.properties.cmd = "fly"
    _keymaps.append((km, kmi))
    kmi = km.keymap_items.new("gamebridge.cmd", T.KEY_FRAME, "PRESS")
    kmi.properties.cmd = "frame"
    _keymaps.append((km, kmi))


def _unregister_keys():
    for km, kmi in _keymaps:
        km.keymap_items.remove(kmi)
    _keymaps.clear()


CLASSES = (GB_Props, GB_OT_cmd, GB_OT_server, GB_OT_tool, GB_PT_panel)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.gamebridge = bpy.props.PointerProperty(type=GB_Props)
    _register_keys()
    if T.AUTOSTART_SERVER:
        try:
            start_server()
        except OSError as e:
            print("[GameBridge] could not start server:", e)


def unregister():
    stop_server()
    _unregister_keys()
    del bpy.types.Scene.gamebridge
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
