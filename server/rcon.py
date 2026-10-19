import socket
import struct

AUTH = 3
EXEC = 2


class RconError(Exception):
    pass


class Rcon:
    def __init__(self, host, port, password, timeout=60):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self._id = 0
        self._send(AUTH, password)
        while True:
            req_id, ptype, _ = self._recv()
            if ptype == 2:
                if req_id == -1:
                    raise RconError("Złe hasło RCON")
                break

    def _send(self, ptype, body):
        self._id += 1
        data = struct.pack("<ii", self._id, ptype) + body.encode("utf-8") + b"\x00\x00"
        self.sock.sendall(struct.pack("<i", len(data)) + data)
        return self._id

    def _recv_exact(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise RconError("Połączenie RCON zamknięte")
            buf += chunk
        return buf

    def _recv(self):
        (size,) = struct.unpack("<i", self._recv_exact(4))
        data = self._recv_exact(size)
        req_id, ptype = struct.unpack("<ii", data[:8])
        return req_id, ptype, data[8:-2].decode("utf-8", errors="replace")

    def command(self, cmd):
        sent = self._send(EXEC, cmd)
        while True:
            req_id, _, body = self._recv()
            if req_id == sent:
                return body

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
