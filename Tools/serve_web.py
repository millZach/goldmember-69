#!/usr/bin/env python3
"""Serve Build/web for browser playtesting.

Godot web builds need a secure context (HTTPS or localhost). The usual setup
is plain HTTP on localhost with Tailscale terminating HTTPS in front:

    python3 Tools/serve_web.py --bind 127.0.0.1 --port 8070 &
    tailscale serve --bg http://127.0.0.1:8070

Alternatively pass --cert/--key (e.g. from `tailscale cert`) to serve HTTPS directly.
"""

import argparse
import functools
import http.server
import os
import ssl

parser = argparse.ArgumentParser()
parser.add_argument("--bind", default="127.0.0.1")
parser.add_argument("--port", type=int, default=8070)
parser.add_argument("--cert")
parser.add_argument("--key")
args = parser.parse_args()

root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Build", "web")
handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=root)
server = http.server.ThreadingHTTPServer((args.bind, args.port), handler)
scheme = "http"
if args.cert:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(args.cert, args.key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    scheme = "https"
print(f"Serving {root} on {scheme}://{args.bind}:{args.port}", flush=True)
server.serve_forever()
