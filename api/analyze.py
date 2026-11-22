from http.server import BaseHTTPRequestHandler
import json

try:
    from api.nlp_engine import analyze_nlp, fetch_url_text
except ImportError:
    from nlp_engine import analyze_nlp, fetch_url_text


class handler(BaseHTTPRequestHandler):
    def _set_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS, GET")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json(self, status_code: int, payload: dict):
        self.send_response(status_code)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self._set_cors()
        self.end_headers()
        self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(204)
        self._set_cors()
        self.end_headers()

    def do_GET(self):
        self._send_json(200, {
            "status": "ok",
            "service": "Privacy Policy Analyzer",
            "message": "POST /api/analyze with {mode, content}"
        })

    def do_POST(self):
        try:
            content_length = max(0, int(self.headers.get("Content-Length") or 0))
            raw = self.rfile.read(content_length) if content_length else b"{}"
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Invalid request format.")

            mode = payload.get("mode", "text")
            content = (payload.get("content") or "").strip()

            if not content:
                raise ValueError("Please provide a URL or policy text.")

            if mode == "url":
                extracted = fetch_url_text(content)
                if len(extracted.split()) < 25:
                    raise ValueError(
                        "Not enough readable text extracted from this URL. "
                        "The site may block automated access. Try pasting the policy text instead."
                    )
            else:
                extracted = content

            result = analyze_nlp(extracted)
            self._send_json(200, result)

        except Exception as e:
            self._send_json(400, {"error": str(e)})
