#!/usr/bin/env python3
"""Serve Build/web over HTTPS on the tailnet using a Tailscale-issued cert.

Godot web builds need a secure context. Get a cert (no root needed) with:
    tailscale cert --cert-file <crt> --key-file <key> <host>.ts.net
"""

import argparse
import functools
import http.server
import os
import ssl

parser = argparse.ArgumentParser()
parser.add_argument("--bind", required=True, help="Tailscale IP to listen on")
parser.add_argument("--port", type=int, default=8069)
parser.add_argument("--cert", required=True)
parser.add_argument("--key", required=True)
args = parser.parse_args()

root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Build", "web")
handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=root)
server = http.server.ThreadingHTTPServer((args.bind, args.port), handler)
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain(args.cert, args.key)
server.socket = context.wrap_socket(server.socket, server_side=True)
print(f"Serving {root} on https://{args.bind}:{args.port}", flush=True)
server.serve_forever()
