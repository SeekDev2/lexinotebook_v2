from http.server import BaseHTTPRequestHandler
import json, cgi, sys, os, traceback

_err = None
try:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    from _agents import run_ingestion_agent, run_analysis_agent, render_mindmap_html
except Exception as e:
    _err = traceback.format_exc()

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self._cors(); self.end_headers()
    def do_POST(self):
        if _err:
            self._send(500, {"error": "Import failed", "trace": _err}); return
        try:
            env = {"REQUEST_METHOD":"POST","CONTENT_TYPE":self.headers.get("Content-Type",""),"CONTENT_LENGTH":self.headers.get("Content-Length","0")}
            form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ=env)
            api_key = form.getvalue("api_key","") or os.environ.get("GEMINI_API_KEY","")
            fi = form["file"]
            filename = fi.filename or "upload.pdf"
            file_bytes = fi.file.read()
            text = run_ingestion_agent(file_bytes, filename, api_key)
            analysis = run_analysis_agent(text, api_key)
            self._send(200, {"name":filename,"text":text,"summary":analysis["summary"],"mindmap":analysis["mindmap"],"mindmap_html":render_mindmap_html(analysis["mindmap"])})
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
