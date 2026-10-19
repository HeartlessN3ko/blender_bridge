"""Stdlib-only socket server. Speaks two dialects on one port:

* WebSocket (browser controller): standard RFC 6455 handshake, text frames.
* Raw newline-delimited JSON (Python CLI): one JSON object per line.

The server never touches bpy. It queues (client, message) pairs; the add-on
drains the queue on Blender's main thread via a timer and calls client.send().
"""
import base64
import hashlib
import json
import queue
import socket
import struct
import threading

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class Client:
    def __init__(self, sock, addr, server):
        self.sock = sock
        self.addr = addr
        self.server = server
        self.ws = False
        self.alive = True
        self.lock = threading.Lock()

    # ---- sending -----------------------------------------------------------
    def send(self, obj):
        data = json.dumps(obj).encode("utf-8")
        try:
            with self.lock:
                if self.ws:
                    self.sock.sendall(_ws_frame(data))
                else:
                    self.sock.sendall(data + b"\n")
        except OSError:
            self.close()

    def close(self):
        if not self.alive:
            return
        self.alive = False
        try:
            self.sock.close()
        except OSError:
            pass
        self.server._drop(self)

    # ---- receiving ---------------------------------------------------------
    def run(self):
        try:
            first = self.sock.recv(4, socket.MSG_PEEK)
            if first.startswith(b"GET "):
                self.ws = True
                if not self._handshake():
                    return
                self._ws_loop()
            else:
                self._line_loop()
        except OSError:
            pass
        finally:
            self.close()

    def _read_exact(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise OSError("closed")
            buf += chunk
        return buf

    def _handshake(self):
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                return False
            buf += chunk
            if len(buf) > 65536:
                return False
        headers = {}
        for line in buf.split(b"\r\n")[1:]:
            if b":" in line:
                k, v = line.split(b":", 1)
                headers[k.strip().lower()] = v.strip()
        key = headers.get(b"sec-websocket-key")
        if not key:
            return False
        accept = base64.b64encode(hashlib.sha1(key + WS_GUID.encode()).digest())
        self.sock.sendall(
            b"HTTP/1.1 101 Switching Protocols\r\n"
            b"Upgrade: websocket\r\nConnection: Upgrade\r\n"
            b"Sec-WebSocket-Accept: " + accept + b"\r\n\r\n"
        )
        return True

    def _ws_loop(self):
        limit = self.server.max_bytes
        while self.alive:
            b1, b2 = self._read_exact(2)
            opcode = b1 & 0x0F
            masked = b2 & 0x80
            length = b2 & 0x7F
            if length == 126:
                length = struct.unpack(">H", self._read_exact(2))[0]
            elif length == 127:
                length = struct.unpack(">Q", self._read_exact(8))[0]
            if length > limit:
                return
            mask = self._read_exact(4) if masked else None
            payload = self._read_exact(length)
            if mask:
                payload = bytes(c ^ mask[i % 4] for i, c in enumerate(payload))
            if opcode == 0x8:
                return
            if opcode == 0x9:
                with self.lock:
                    self.sock.sendall(_ws_frame(payload, opcode=0xA))
                continue
            if opcode in (0x1, 0x0):
                self._dispatch(payload)

    def _line_loop(self):
        buf = b""
        while self.alive:
            chunk = self.sock.recv(65536)
            if not chunk:
                return
            buf += chunk
            if len(buf) > self.server.max_bytes:
                return
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if line.strip():
                    self._dispatch(line)

    def _dispatch(self, raw):
        try:
            msg = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            self.send({"ok": False, "error": f"bad json: {e}"})
            return
        self.server.inbox.put((self, msg))


def _ws_frame(data, opcode=0x1):
    head = bytes([0x80 | opcode])
    n = len(data)
    if n < 126:
        head += bytes([n])
    elif n < 65536:
        head += bytes([126]) + struct.pack(">H", n)
    else:
        head += bytes([127]) + struct.pack(">Q", n)
    return head + data


class BridgeServer:
    def __init__(self, host, port, max_bytes=1_000_000):
        self.host = host
        self.port = port
        self.max_bytes = max_bytes
        self.inbox = queue.Queue()
        self.clients = set()
        self._clients_lock = threading.Lock()
        self._sock = None
        self._thread = None
        self.running = False

    def start(self):
        if self.running:
            return
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((self.host, self.port))
        s.listen(8)
        s.settimeout(0.5)
        self._sock = s
        self.running = True
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False
        with self._clients_lock:
            clients = list(self.clients)
        for c in clients:
            c.close()
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def _accept_loop(self):
        while self.running:
            try:
                sock, addr = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            c = Client(sock, addr, self)
            with self._clients_lock:
                self.clients.add(c)
            threading.Thread(target=c.run, daemon=True).start()

    def _drop(self, client):
        with self._clients_lock:
            self.clients.discard(client)

    def broadcast(self, obj):
        with self._clients_lock:
            clients = list(self.clients)
        for c in clients:
            c.send(obj)

    def drain(self, handler):
        """Call on the main thread. handler(msg) -> reply dict."""
        n = 0
        while True:
            try:
                client, msg = self.inbox.get_nowait()
            except queue.Empty:
                return n
            reply = handler(msg)
            if reply is not None:
                if isinstance(msg, dict) and "id" in msg:
                    reply["id"] = msg["id"]
                client.send(reply)
            n += 1
