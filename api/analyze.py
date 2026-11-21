from http.server import BaseHTTPRequestHandler
import json
import os
import re
import requests

try:
    from api.nlp_engine import analyze_nlp, fetch_url_text
except ImportError:
    from nlp_engine import analyze_nlp, fetch_url_text


def try_ai_enrichment(text: str, nlp_result: dict) -> dict:
    """Optional AI enrichment. Gracefully falls back if no key or any error."""
    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("XAI_API_KEY")
    if not api_key:
        return nlp_result

    base_url = "https://api.openai.com/v1"
    model = "gpt-4o-mini"
    if os.environ.get("XAI_API_KEY"):
        base_url = "https://api.x.ai/v1"
        model = "grok-beta"
        api_key = os.environ.get("XAI_API_KEY")

    try:
        prompt = f"""You are a privacy policy risk analyst. Analyze the following privacy policy excerpt and return ONLY valid JSON with these keys:
- ai_summary: one short plain-language paragraph of overall risk
- extra_risks: array of up to 3 short additional risk points not already obvious
- confidence: number 0-100

Policy text (truncated):
{text[:6000]}
"""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You respond only with valid JSON. No markdown."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 500
        }
        resp = requests.post(f"{base_url}/chat/completions", headers=headers, json=body, timeout=20)
        if resp.status_code != 200:
            return nlp_result
        content = resp.json()["choices"][0]["message"]["content"]
        content = re.sub(r"^```json\s*|\s*```$", "", content.strip())
        ai_data = json.loads(content)

        nlp_result["engine"] = "Hybrid NLP + AI"
        if ai_data.get("ai_summary"):
            nlp_result["summary"] = ai_data["ai_summary"]
        if ai_data.get("extra_risks"):
            for risk in ai_data["extra_risks"][:3]:
                nlp_result["findings"].append({
                    "category": "AI Contextual Insight",
                    "status": "Insight",
                    "weight_added": 0,
                    "message": risk,
                    "evidence": "AI semantic analysis"
                })
        return nlp_result
    except Exception:
        return nlp_result


class handler(BaseHTTPRequestHandler):
    def _set_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS, GET")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._set_cors()
        self.end_headers()

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self._set_cors()
        self.end_headers()
        self.wfile.write(json.dumps({
            "status": "ok",
            "service": "Privacy Policy Analyzer",
            "message": "POST /api/analyze with {mode, content}"
        }).encode())

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
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
            result = try_ai_enrichment(extracted, result)

            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self._set_cors()
            self.end_headers()
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))

        except Exception as e:
            self.send_response(400)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self._set_cors()
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}, ensure_ascii=False).encode("utf-8"))
