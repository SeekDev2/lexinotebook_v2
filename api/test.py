from http.server import BaseHTTPRequestHandler
import json, sys, os
_err = None
try:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import _agents
    _fns = [x for x in dir(_agents) if not x.startswith("__")]
except Exception as e:
    import traceback; _err = traceback.format_exc(); _fns = []
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"import_error":_err,"functions":_fns,"python":sys.version}, indent=2).encode()
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(body)))
        self.send_header("Access-Control-Allow-Origin","*")
        self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass
