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
    """Optional Free Gemini enrichment. Gracefully falls back to NLP if no key or quota/error."""
    api_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if not api_key:
        return nlp_result

    model = (os.environ.get("GEMINI_MODEL") or "gemini-3.5-flash-lite").strip()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    try:
        prompt = f"""You are a privacy policy risk analyst. Analyze the following privacy policy excerpt and return ONLY valid JSON with these keys:
- ai_summary: one short plain-language paragraph of overall risk
- extra_risks: array of up to 3 short additional risk points not already obvious
- confidence: number 0-100

Policy text (truncated):
{text[:6000]}
"""
        body = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 500,
                "responseMimeType": "application/json"
            }
        }
        resp = requests.post(url, json=body, timeout=12)
        if resp.status_code != 200:
            return nlp_result

        data = resp.json()
        candidates = data.get("candidates") or []
        parts = (candidates[0].get("content") or {}).get("parts") or [] if candidates else []
        raw_text = (parts[0].get("text") or "").strip() if parts else ""
        if not raw_text:
            return nlp_result

        cleaned_json = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text, flags=re.IGNORECASE).strip()
        ai_data = json.loads(cleaned_json)
        if not isinstance(ai_data, dict):
            return nlp_result

        nlp_result["engine"] = f"Hybrid NLP + Gemini ({model})"

        ai_summary = ai_data.get("ai_summary")
        if isinstance(ai_summary, str) and ai_summary.strip():
            nlp_result["summary"] = ai_summary.strip()

        confidence = ai_data.get("confidence")
        if isinstance(confidence, (int, float)) and not isinstance(confidence, bool):
            nlp_result["ai_confidence"] = max(0, min(100, round(confidence)))

        extra_risks = ai_data.get("extra_risks")
        if isinstance(extra_risks, list):
            findings = list(nlp_result.get("findings") or [])
            for risk in extra_risks[:3]:
                if isinstance(risk, str) and risk.strip():
                    findings.append({
                        "category": "AI Contextual Insight",
                        "status": "Insight",
                        "weight_added": 0,
                        "message": risk.strip(),
                        "evidence": "AI semantic analysis"
                    })
            nlp_result["findings"] = findings

        return nlp_result
    except Exception:
        return nlp_result


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
            result = try_ai_enrichment(extracted, result)
            self._send_json(200, result)

        except Exception as e:
            self._send_json(400, {"error": str(e)})
