#!/usr/bin/env python3
"""Python client + CLI for the Blender Game Bridge add-on. Stdlib only.

Library:
    from bridge_client import Bridge
    with Bridge() as b:
        b.select("Cube"); b.move(dx=1); print(b.state())

CLI (each prints the JSON reply):
    bridge_client.py state
    bridge_client.py select Cube
    bridge_client.py move --dx 1 --dz 0.5
    bridge_client.py rotate --axis z --degrees 45
    bridge_client.py scale --factor 1.5
    bridge_client.py dims --x 2 --y 2 --z 0.5
    bridge_client.py add cube --name Crate --x 2
    bridge_client.py cam --forward 2 --yaw -1
    bridge_client.py exec "bpy.ops.object.shade_smooth()"
    bridge_client.py raw '{"cmd":"set_location","x":0,"y":0,"z":1}'
    bridge_client.py repl
"""
import argparse
import json
import socket
import sys

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


class BridgeError(RuntimeError):
    pass


class Bridge:
    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT, timeout=10.0):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.buf = b""
        self._id = 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def close(self):
        self.sock.close()

    def send(self, cmd, **args):
        self._id += 1
        msg = {"cmd": cmd, "id": self._id, **args}
        self.sock.sendall(json.dumps(msg).encode() + b"\n")
        while True:
            reply = self._read()
            if reply.get("id") == self._id or "id" not in reply:
                break
        if not reply.get("ok"):
            raise BridgeError(reply.get("error", "unknown error"))
        return reply

    def _read(self):
        while b"\n" not in self.buf:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise BridgeError("connection closed")
            self.buf += chunk
        line, self.buf = self.buf.split(b"\n", 1)
        return json.loads(line)

    # ---- convenience -------------------------------------------------------
    def state(self):
        return self.send("state")["result"]

    def objects(self):
        return self.send("list_objects")["result"]

    def select(self, name, extend=False):
        return self.send("select", name=name, extend=extend)["result"]

    def move(self, dx=0, dy=0, dz=0, space="world"):
        return self.send("move", dx=dx, dy=dy, dz=dz, space=space)["result"]

    def rotate(self, axis="z", degrees=0, local=False):
        return self.send("rotate", axis=axis, degrees=degrees, local=local)["result"]

    def scale(self, factor=None, sx=1, sy=1, sz=1):
        if factor is not None:
            return self.send("scale", factor=factor)["result"]
        return self.send("scale", sx=sx, sy=sy, sz=sz)["result"]

    def set_location(self, **xyz):
        return self.send("set_location", **xyz)["result"]

    def set_rotation(self, **xyz):
        return self.send("set_rotation", **xyz)["result"]

    def set_dimensions(self, **xyz):
        return self.send("set_dimensions", **xyz)["result"]

    def add(self, type="cube", name=None, x=0, y=0, z=0):
        return self.send("add", type=type, name=name, x=x, y=y, z=z)["result"]

    def camera(self, **kw):
        return self.send("camera", **kw)["result"]

    def exec(self, code, eval=False):
        return self.send("exec", code=code, eval=eval)["result"]


def _xyz(p, prefix=""):
    for k in "xyz":
        p.add_argument(f"--{prefix}{k}", type=float)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Blender Game Bridge CLI")
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    sub = ap.add_subparsers(dest="verb", required=True)

    sub.add_parser("state")
    sub.add_parser("objects")
    sub.add_parser("ping")
    p = sub.add_parser("select"); p.add_argument("name"); p.add_argument("--extend", action="store_true")
    p = sub.add_parser("move"); _xyz(p, "d"); p.add_argument("--space", default="world", choices=["world", "view"])
    p = sub.add_parser("rotate"); p.add_argument("--axis", default="z"); p.add_argument("--degrees", type=float, required=True); p.add_argument("--local", action="store_true")
    p = sub.add_parser("scale"); p.add_argument("--factor", type=float); p.add_argument("--sx", type=float, default=1); p.add_argument("--sy", type=float, default=1); p.add_argument("--sz", type=float, default=1)
    p = sub.add_parser("loc"); _xyz(p)
    p = sub.add_parser("rot"); _xyz(p)
    p = sub.add_parser("dims"); _xyz(p)
    p = sub.add_parser("add"); p.add_argument("type"); p.add_argument("--name"); _xyz(p)
    p = sub.add_parser("cam")
    for k in ("forward", "right", "up", "yaw", "pitch", "zoom"):
        p.add_argument(f"--{k}", type=float, default=0)
    p = sub.add_parser("mode"); p.add_argument("mode", choices=["select", "move", "rotate", "scale"])
    p = sub.add_parser("snap"); p.add_argument("on", nargs="?", choices=["on", "off"])
    for v in ("frame", "fly", "undo", "redo", "delete", "duplicate"):
        sub.add_parser(v)
    p = sub.add_parser("save"); p.add_argument("--path")
    p = sub.add_parser("exec"); p.add_argument("code"); p.add_argument("--eval", action="store_true")
    p = sub.add_parser("raw"); p.add_argument("json")
    sub.add_parser("repl")

    a = ap.parse_args(argv)
    try:
        b = Bridge(a.host, a.port)
    except OSError as e:
        print(f"cannot connect to Blender at {a.host}:{a.port}: {e}", file=sys.stderr)
        return 2

    def clean(d, keys):
        return {k: v for k, v in d.items() if k in keys and v is not None}

    v = a.verb
    try:
        if v == "repl":
            print("type JSON objects or `cmd key=val ...`; blank line to quit")
            for line in sys.stdin:
                line = line.strip()
                if not line:
                    break
                if line.startswith("{"):
                    msg = json.loads(line)
                else:
                    parts = line.split()
                    msg = {"cmd": parts[0]}
                    for kv in parts[1:]:
                        k, _, val = kv.partition("=")
                        try:
                            val = json.loads(val)
                        except ValueError:
                            pass
                        msg[k] = val
                try:
                    print(json.dumps(b.send(msg.pop("cmd"), **msg), indent=1))
                except BridgeError as e:
                    print("ERROR:", e)
            return 0
        if v == "raw":
            msg = json.loads(a.json)
            r = b.send(msg.pop("cmd"), **msg)
        elif v == "select":
            r = b.send("select", name=a.name, extend=a.extend)
        elif v == "move":
            r = b.send("move", space=a.space, **clean(vars(a), {"dx", "dy", "dz"}))
        elif v == "rotate":
            r = b.send("rotate", axis=a.axis, degrees=a.degrees, local=a.local)
        elif v == "scale":
            r = b.send("scale", factor=a.factor) if a.factor else b.send("scale", sx=a.sx, sy=a.sy, sz=a.sz)
        elif v in ("loc", "rot", "dims"):
            cmd = {"loc": "set_location", "rot": "set_rotation", "dims": "set_dimensions"}[v]
            r = b.send(cmd, **clean(vars(a), {"x", "y", "z"}))
        elif v == "add":
            r = b.send("add", type=a.type, name=a.name, **clean(vars(a), {"x", "y", "z"}))
        elif v == "cam":
            r = b.send("camera", **clean(vars(a), {"forward", "right", "up", "yaw", "pitch", "zoom"}))
        elif v == "mode":
            r = b.send("set_mode", mode=a.mode)
        elif v == "snap":
            r = b.send("snap", **({"on": a.on == "on"} if a.on else {}))
        elif v == "save":
            r = b.send("save", **({"path": a.path} if a.path else {}))
        elif v == "exec":
            r = b.send("exec", code=a.code, eval=a.eval)
        elif v == "objects":
            r = b.send("list_objects")
        else:
            r = b.send(v)
    except BridgeError as e:
        print("ERROR:", e, file=sys.stderr)
        return 1
    finally:
        b.close()
    print(json.dumps(r, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
