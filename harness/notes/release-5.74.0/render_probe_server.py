"""Serve the render probe and RECEIVE its measurement, so no number is transcribed.

The probe must run in a real browser -- that is the whole point of it. The weak
link in "render it, then write the numbers down" is the writing down: a human or
an agent reading a result off a screen and retyping it is exactly the producer-less
number Law 2 forbids. So the page POSTs its own result here and this writes the
file. The chain is browser -> POST -> json, with no hand in it.

    python harness/notes/release-5.74.0/render_probe_server.py [port]

Then open http://127.0.0.1:<port>/render_probe.html and the JSON lands beside it.
"""
import http.server
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "render-probe-5.74.0.json")


class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=HERE, **kw)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n).decode("utf-8")
        json.loads(body)  # refuse to write anything that is not valid JSON
        io.open(OUT, "w", encoding="utf-8", newline="\n").write(body)
        self.send_response(204)
        self.end_headers()
        print("WROTE %s (%d bytes)" % (OUT, len(body)), flush=True)

    def log_message(self, *a):
        pass


port = int(sys.argv[1]) if len(sys.argv) > 1 else 8778
print("serving %s on %d" % (HERE, port), flush=True)
http.server.HTTPServer(("127.0.0.1", port), H).serve_forever()
