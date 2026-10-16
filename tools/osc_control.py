#!/usr/bin/env python3
"""Drive a running Infinite over its OSC control API (v0.6 2.31).

Infinite listens on 127.0.0.1:9100 (INFINITE_OSC_PORT moves it, 0 turns it
off). Standard library only. Examples:

  tools/osc_control.py nodes
  tools/osc_control.py create Shape 100 80          -> prints the new index
  tools/osc_control.py set 3 cutoff 1200
  tools/osc_control.py get 3 cutoff
  tools/osc_control.py params 3
  tools/osc_control.py connect 3 0 4 0              (src output dst slot)
  tools/osc_control.py disconnect 4 0               (dst slot)
  tools/osc_control.py delete 3
  tools/osc_control.py listen 3 cutoff              (prints every change; Ctrl+C stops)
  tools/osc_control.py demo                         (builds Shape -> Output, sweeps a param)

Param names are the patch-file names with spaces as '_'.
"""
import socket
import struct
import sys
import time

PORT = 9100


def _pad(b):
    return b + b"\0" * (4 - len(b) % 4)


def encode(address, *args):
    tags, data = ",", b""
    for a in args:
        if isinstance(a, bool) or isinstance(a, int):
            tags += "i"
            data += struct.pack(">i", int(a))
        elif isinstance(a, float):
            tags += "f"
            data += struct.pack(">f", a)
        else:
            tags += "s"
            data += _pad(str(a).encode())
    return _pad(address.encode()) + _pad(tags.encode()) + data


def _read_str(buf, pos):
    end = buf.index(b"\0", pos)
    s = buf[pos:end].decode()
    return s, (end + 4) & ~3


def decode(buf):
    address, pos = _read_str(buf, 0)
    args = []
    if pos < len(buf):
        tags, pos = _read_str(buf, pos)
        for t in tags[1:]:
            if t == "f":
                args.append(struct.unpack(">f", buf[pos:pos + 4])[0]); pos += 4
            elif t == "i":
                args.append(struct.unpack(">i", buf[pos:pos + 4])[0]); pos += 4
            elif t == "s":
                s, pos = _read_str(buf, pos); args.append(s)
    return address, args


class Infinite:
    def __init__(self, port=PORT):
        self.addr = ("127.0.0.1", port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))

    def send(self, address, *args):
        self.sock.sendto(encode(address, *args), self.addr)

    def replies(self, until=None, timeout=1.0):
        """Yields replies until one on `until` arrives, or `timeout` s of quiet."""
        self.sock.settimeout(timeout)
        while True:
            try:
                data, _ = self.sock.recvfrom(4096)
            except socket.timeout:
                return
            msg = decode(data)
            if msg[0] == "/infinite/error":
                print("error:", msg[1][0], file=sys.stderr)
            yield msg
            if msg[0] == until:
                return

    def ask(self, until, address, *args):
        self.send(address, *args)
        last = None
        for msg in self.replies(until):
            if msg[0] == until:
                last = msg
        return last


def node_addr(index, param=None):
    return "/infinite/node/%d" % int(index) + ("/" + param if param else "")


def num(s):
    try:
        return int(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return s


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    inf, cmd, a = Infinite(), argv[0], argv[1:]
    if cmd == "nodes":
        inf.send("/infinite/nodes")
        for address, args in inf.replies("/infinite/nodes/end"):
            if address == "/infinite/node":
                print(args[0], args[1])
    elif cmd == "create":
        extra = [float(v) for v in a[1:3]]
        msg = inf.ask("/infinite/created", "/infinite/create", a[0], *extra)
        if msg:
            print(msg[1][0])
    elif cmd == "set":
        inf.send(node_addr(a[0], a[1]), num(a[2]))
        inf.ask("/infinite/error", "/infinite/node/%s/%s" % (a[0], a[1]))  # reads back; errors print
    elif cmd == "get":
        msg = inf.ask(node_addr(a[0], a[1]), node_addr(a[0], a[1]))
        if msg:
            print(msg[1][0])
    elif cmd == "params":
        end = node_addr(a[0], "end")
        inf.send(node_addr(a[0]))
        for address, args in inf.replies(end):
            if address != end:
                print(address.rsplit("/", 1)[1], args[0])
    elif cmd == "connect":
        inf.send("/infinite/connect", *[int(v) for v in a[:4]])
        list(inf.replies(timeout=0.3))
    elif cmd == "disconnect":
        inf.send("/infinite/disconnect", int(a[0]), int(a[1]))
        list(inf.replies(timeout=0.3))
    elif cmd == "delete":
        inf.send("/infinite/delete", int(a[0]))
        list(inf.replies(timeout=0.3))
    elif cmd == "listen":
        target = node_addr(a[0], a[1])
        inf.send("/infinite/listen", target)
        try:
            while True:
                for address, args in inf.replies(timeout=3600):
                    if address == target:
                        print(args[0], flush=True)
        except KeyboardInterrupt:
            inf.send("/infinite/unlisten", target)
    elif cmd == "demo":
        shape = inf.ask("/infinite/created", "/infinite/create", "Shape", 100.0, 80.0)[1][0]
        out = inf.ask("/infinite/created", "/infinite/create", "Output", 420.0, 80.0)[1][0]
        inf.send("/infinite/connect", shape, 0, out, 0)
        params = []
        end = node_addr(shape, "end")
        inf.send(node_addr(shape))
        for address, args in inf.replies(end):
            if address != end and isinstance(args[0], float):
                params.append(address)
        target = params[0]
        print("Shape %d -> Output %d; sweeping %s" % (shape, out, target.rsplit("/", 1)[1]))
        for i in range(60):
            inf.send(target, 0.5 + 0.5 * __import__("math").sin(i / 6.0))
            time.sleep(1 / 30)
        print("read back:", inf.ask(target, target)[1][0])
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
