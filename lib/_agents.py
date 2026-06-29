import os, json, urllib.request

def _post(url, payload):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())

def _generate(api_key, prompt, mime=None):
    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.1}}
    if mime: payload["generationConfig"]["responseMimeType"] = mime
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    return _post(url, payload)["candidates"][0]["content"]["parts"][0]["text"]

def _generate_with_file(api_key, prompt, file_uri, file_mime):
    payload = {"contents": [{"parts": [{"text": prompt}, {"file_data": {"mime_type": file_mime, "file_uri": file_uri}}]}], "generationConfig": {"temperature": 0.1}}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    return _post(url, payload)["candidates"][0]["content"]["parts"][0]["text"]

def _upload_file(api_key, file_bytes, mime_type, display_name):
    init_url = f"https://generativelanguage.googleapis.com/upload/v1beta/files?key={api_key}&uploadType=resumable"
    meta = json.dumps({"file": {"display_name": display_name}}).encode()
    hdrs = {"Content-Type": "application/json", "X-Goog-Upload-Protocol": "resumable", "X-Goog-Upload-Command": "start", "X-Goog-Upload-Header-Content-Length": str(len(file_bytes)), "X-Goog-Upload-Header-Content-Type": mime_type}
    init_req = urllib.request.Request(init_url, data=meta, headers=hdrs, method="POST")
    with urllib.request.urlopen(init_req, timeout=30) as r:
        upload_url = r.headers["X-Goog-Upload-URL"]
    up_hdrs = {"Content-Length": str(len(file_bytes)), "X-Goog-Upload-Offset": "0", "X-Goog-Upload-Command": "upload, finalize"}
    up_req = urllib.request.Request(upload_url, data=file_bytes, headers=up_hdrs, method="POST")
    with urllib.request.urlopen(up_req, timeout=60) as r:
        return json.loads(r.read())["file"]["uri"]

def _clean_json(raw):
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```", 2)
        raw = parts[1] if len(parts) >= 2 else raw
        if raw.startswith("json"): raw = raw[4:]
        if raw.endswith("```"): raw = raw[:-3]
    return raw.strip()

def render_mindmap_html(node, _root=True):
    if not isinstance(node, dict): return ""
    def esc(s): return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
    name = esc(node.get("name","Untitled"))
    desc = esc(str(node.get("description","")).strip())
    children = node.get("children") or []
    has_ch = isinstance(children, list) and len(children) > 0
    dh = f'<div class="lx-desc">{desc}</div>' if desc else ""
    if has_ch:
        kids = "".join(render_mindmap_html(c, False) for c in children)
        h = f'<details class="lx-node" open><summary class="lx-summary"><span class="lx-name">{name}</span><span class="lx-count">{len(children)}</span></summary>{dh}<div class="lx-children">{kids}</div></details>'
    else:
        h = f'<div class="lx-node lx-leaf"><div class="lx-summary lx-leaf-summary"><span class="lx-bullet">&#x2022;</span><span class="lx-name">{name}</span></div>{dh}</div>'
    if _root:
        css = "<style>.lx-tree{font-family:Inter,sans-serif;line-height:1.4;color:#e6e6e6;padding:8px 4px}.lx-node{margin:4px 0}.lx-children{margin-left:14px;padding-left:12px;border-left:2px solid #3a3f4b;margin-top:4px}.lx-summary{cursor:pointer;padding:6px 10px;border-radius:8px;display:flex;align-items:center;gap:8px;list-style:none}.lx-summary::-webkit-details-marker{display:none}.lx-summary:hover{background:rgba(255,140,60,.1)}.lx-name{font-weight:600;font-size:.92rem;color:#f5f5f5}.lx-count{margin-left:auto;background:#ff7a33;color:#1a1a1a;font-size:.7rem;font-weight:700;padding:1px 8px;border-radius:999px}.lx-bullet{color:#ff7a33}.lx-desc{font-size:.82rem;color:#a8b0bd;margin:2px 0 4px 28px}</style>"
        return f'{css}<div class="lx-tree">{h}</div>'
    return h

MIME_MAP = {".pdf":"application/pdf",".docx":"application/vnd.openxmlformats-officedocument.wordprocessingml.document",".png":"image/png",".jpg":"image/jpeg",".jpeg":"image/jpeg",".wav":"audio/wav",".mp3":"audio/mpeg",".m4a":"audio/mp4"}

def run_ingestion_agent(file_bytes, filename, api_key):
    ext = os.path.splitext(filename)[1].lower()
    mime_type = MIME_MAP.get(ext, "application/pdf")
    file_uri = _upload_file(api_key, file_bytes, mime_type, filename)
    prompt = "Transcribe this audio accurately." if ext in (".wav",".mp3",".m4a") else "Extract the complete text as clean Markdown preserving headings, lists, and tables."
    return _generate_with_file(api_key, prompt, file_uri, mime_type)

def run_analysis_agent(extracted_text, api_key):
    if "EXTRACTION_FAILED" in extracted_text:
        return {"summary": "### Extraction Failed\n" + extracted_text, "mindmap": {"name":"Error","description":"Failed","children":[]}}
    sp = "Legal analysis agent. Write markdown summary with sections: ## Title ## Parties ## Key Obligations ## Rights & Entitlements ## Risks & Liabilities ## Important Dates\n\nDocument:\n" + extracted_text[:30000]
    try:
        summary = _generate(api_key, sp)
    except Exception as e:
        summary = f"### Summary Failed: {e}"
    mp = "Output ONLY JSON object, no fences. Schema: {\"name\":\"title\",\"description\":\"one sentence\",\"children\":[{\"name\":\"Section\",\"description\":\"brief\",\"children\":[]}]}\n\nDocument:\n" + extracted_text[:15000]
    try:
        mindmap = json.loads(_clean_json(_generate(api_key, mp, mime="application/json")))
    except:
        mindmap = {"name":"Document","description":"Structure unavailable","children":[]}
    return {"summary": summary, "mindmap": mindmap}

def run_guardrail_agent(query, api_key):
    p = f'Analyze: "{query}". Harmful/illegal? JSON: {{"isSafe":true/false,"reason":"explanation"}}'
    try: return json.loads(_clean_json(_generate(api_key, p, mime="application/json")))
    except: return {"isSafe":True,"reason":"Fallback"}

def run_counsel_agent(query, context_docs, api_key):
    ctx = "\n\n".join(f"--- DOCUMENT: {d['name']} ---\n{d['text'][:30000]}" for d in context_docs)
    return _generate(api_key, f"Query: {query}\n\nContext:\n{ctx}\n\nAnswer using ONLY context. Cite as [Document Name]. Legal markdown.")

def run_validation_agent(draft, context_docs, api_key):
    ctx = "\n\n".join(f"--- DOCUMENT: {d['name']} ---\n{d['text'][:20000]}" for d in context_docs)
    return _generate(api_key, f"Context:\n{ctx}\n\nDraft:\n{draft}\n\nVerify claims. Return corrected markdown only.")
