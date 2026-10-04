#!/usr/bin/env python3
"""Forward nanocodex's Responses requests to OpenRouter, swapping the model id.

nanocodex 0.6.6 only accepts a closed model enum, so it cannot ask for
qwen/qwen3.7-flash directly. It is run as `--model mimo-v2.6-pro
--model-id-prefix xiaomi` against this proxy, which rewrites the JSON body's
"model" field and streams the SSE response back unchanged. The nanocodex
binary itself is the unmodified release build.

Usage: REWRITE_TO=qwen/qwen3.7-flash PORT=0 python3 model_rewrite_proxy.py
Prints the bound port on the first stdout line.
"""

import http.client
import http.server
import json
import os
import sys

UPSTREAM = "openrouter.ai"
REWRITE_FROM = os.environ.get("REWRITE_FROM", "xiaomi/mimo-v2.6-pro")
REWRITE_TO = os.environ.get("REWRITE_TO", "qwen/qwen3.7-flash")
HOP = {"host", "content-length", "connection", "accept-encoding", "transfer-encoding"}


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        sys.stderr.write("proxy: " + (fmt % args) + "\n")

    def _forward(self, method):
        body = self.rfile.read(int(self.headers.get("content-length") or 0))
        if body:
            try:
                data = json.loads(body)
                if data.get("model") == REWRITE_FROM:
                    data["model"] = REWRITE_TO
                    body = json.dumps(data).encode()
                if os.environ.get("DUMP"):
                    with open(os.environ["DUMP"], "w") as f:
                        json.dump(data, f)
            except ValueError:
                pass
        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP}
        headers["content-length"] = str(len(body))
        conn = http.client.HTTPSConnection(UPSTREAM, timeout=600)
        conn.request(method, self.path, body=body or None, headers=headers)
        resp = conn.getresponse()
        self.send_response(resp.status)
        for k, v in resp.getheaders():
            if k.lower() not in HOP:
                self.send_header(k, v)
        self.send_header("transfer-encoding", "chunked")
        self.end_headers()
        while chunk := resp.read1(65536):
            self.wfile.write(b"%x\r\n%s\r\n" % (len(chunk), chunk))
            self.wfile.flush()
        self.wfile.write(b"0\r\n\r\n")
        conn.close()

    def do_POST(self):
        self._forward("POST")

    def do_GET(self):
        self._forward("GET")


server = http.server.ThreadingHTTPServer(("127.0.0.1", int(os.environ.get("PORT", "0"))), Handler)
print(server.server_address[1], flush=True)
server.serve_forever()
