from http.server import BaseHTTPRequestHandler
import json, sys, os, traceback

_err = None
try:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    from _agents import run_guardrail_agent, run_counsel_agent, run_validation_agent
except Exception as e:
    _err = traceback.format_exc()

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self._cors(); self.end_headers()
    def do_POST(self):
        if _err:
            self._send(500, {"error": "Import failed", "trace": _err}); return
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            query = body.get("query","").strip()
            api_key = body.get("api_key","") or os.environ.get("GEMINI_API_KEY","")
            documents = body.get("documents",[])
            if not query: raise ValueError("query required")
            if not documents: raise ValueError("No documents")
            g = run_guardrail_agent(query, api_key)
            if not g.get("isSafe", True):
                self._send(200, {"blocked":True,"reason":g.get("reason","")}); return
            draft = run_counsel_agent(query, documents, api_key)
            final = run_validation_agent(draft, documents, api_key)
            self._send(200, {"response": final})
        except Exception as e:
            self._send(500, {"error": str(e), "trace": traceback.format_exc()})
    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self._cors()
        self.send_response(code)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Methods","POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers","Content-Type")
    def log_message(self, *a): pass
