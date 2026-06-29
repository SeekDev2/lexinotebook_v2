from http.server import BaseHTTPRequestHandler
import json, sys, os, traceback

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lib'))
from _agents import run_ingestion_agent, run_analysis_agent, render_mindmap_html

def parse_multipart(data, boundary):
    fields, files = {}, {}
    if isinstance(boundary, str):
        boundary = boundary.encode()
    sep = b'--' + boundary
    parts = data.split(sep)
    for part in parts[1:]:
        if len(part) < 4:
            continue
        if part[:2] == b'\r\n':
            part = part[2:]
        if b'\r\n\r\n' not in part:
            continue
        headers_raw, body = part.split(b'\r\n\r\n', 1)
        if body[-2:] == b'\r\n':
            body = body[:-2]
        if body[-2:] == b'--':
            body = body[:-2]
        disp = ''
        for line in headers_raw.decode('utf-8', errors='replace').splitlines():
            if line.lower().startswith('content-disposition:'):
                disp = line
        name, filename = '', None
        for chunk in disp.split(';'):
            chunk = chunk.strip()
            if chunk.startswith('name='):
                name = chunk[5:].strip('"').strip("'")
            elif chunk.startswith('filename='):
                filename = chunk[9:].strip('"').strip("'")
        if filename is not None:
            files[name] = (filename, body)
        else:
            fields[name] = body.decode('utf-8', errors='replace')
    return fields, files

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self._cors()
        self.end_headers()

    def do_POST(self):
        try:
            ct = self.headers.get('Content-Type', '')
            length = int(self.headers.get('Content-Length', 0))
            raw = self.rfile.read(length)
            boundary = ''
            for part in ct.split(';'):
                part = part.strip()
                if part.startswith('boundary='):
                    boundary = part[9:].strip()
            if not boundary:
                raise ValueError('No boundary found in Content-Type: ' + ct)
            fields, files = parse_multipart(raw, boundary)
            api_key = fields.get('api_key', '') or os.environ.get('GEMINI_API_KEY', '')
            if 'file' not in files:
                raise ValueError('No file in request. Fields=' + str(list(fields.keys())))
            filename, file_bytes = files['file']
            filename = filename or 'upload.pdf'
            text = run_ingestion_agent(file_bytes, filename, api_key)
            analysis = run_analysis_agent(text, api_key)
            self._send(200, {
                'name': filename,
                'text': text,
                'summary': analysis['summary'],
                'mindmap': analysis['mindmap'],
                'mindmap_html': render_mindmap_html(analysis['mindmap'])
            })
        except Exception as e:
            self._send(500, {'error': str(e), 'trace': traceback.format_exc()})

    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self._cors()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def log_message(self, *a):
        pass
