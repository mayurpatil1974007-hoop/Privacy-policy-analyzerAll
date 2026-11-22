import json
import os
import re
import urllib.error
import urllib.request
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"

NEGATION_PATTERNS = [
    r"\bdo\s+not\b", r"\bdon't\b", r"\bdoes\s+not\b", r"\bdoesn't\b",
    r"\bnever\b", r"\bwill\s+not\b", r"\bwon't\b", r"\bprohibit(s|ed)?\b",
    r"\bdo\s+not\s+sell\b", r"\bnot\s+sell\b", r"\bnot\s+share\b",
    r"\bdo\s+not\s+train\b", r"\bnot\s+used\s+to\s+train\b",
    r"\bno\s+personal\s+data\s+(is\s+)?sold\b"
]

CONDITIONAL_PATTERNS = [
    r"\bwith\s+your\s+(explicit\s+)?consent\b",
    r"\bif\s+you\s+(opt[- ]?in|choose|enable|authorize)\b",
    r"\bexcept\s+(as\s+)?required\s+by\s+law\b",
    r"\baggregated\s+or\s+de[- ]?identified\b",
    r"\banonymized\b"
]

DATA_COLLECTION_RULES = [
    {
        "data_type": "Identity & Contact Info",
        "pattern": r"\b(name|email|e-mail|phone|mobile|address|username|account\s+id)\b"
    },
    {
        "data_type": "Location & IP / Device Info",
        "pattern": r"\b(location|gps|geolocation|ip\s+address|device\s+(id|type|info)|browser|operating\s+system)\b"
    },
    {
        "data_type": "Cookies, SDKs & Activity Logs",
        "pattern": r"\b(cookies?|sdk(s)?|pixels?|browsing|clickstream|usage\s+data|log\s+data|interactions?)\b"
    },
    {
        "data_type": "Financial & Payment Details",
        "pattern": r"\b(credit\s+card|debit\s+card|payment|billing|bank|account\s+number|transaction)\b"
    },
    {
        "data_type": "Health, Biometric & Sensitive Data",
        "pattern": r"\b(biometric|face|fingerprint|voiceprint|health|medical|genetic|race|religion|sexual)\b"
    }
]

RISK_RULES = [
    {
        "category": "Data Selling & Monetization",
        "weight": 5,
        "verb": r"\b(sell|sells|selling|sold|monetize|rent|lease|trade|license)\b",
        "target": r"\b(personal\s+(data|information)|user\s+(data|information)|your\s+(data|information)|data)\b",
        "risk_msg": "Personal data may be sold, rented, or monetized.",
        "safe_msg": "Clear restriction on selling personal data found."
    },
    {
        "category": "AI Training & Profiling",
        "weight": 4,
        "verb": r"\b(train|training|fine[- ]?tune|profile|profiling|infer|predict|score)\b",
        "target": r"\b(ai|artificial\s+intelligence|machine\s+learning|models?|algorithms?|behavior|preferences)\b",
        "risk_msg": "Data may be used for AI/ML model training or automated profiling.",
        "safe_msg": "Restriction on AI/ML training or profiling found."
    },
    {
        "category": "Biometric, Health & Financial Data",
        "weight": 4,
        "verb": r"\b(collect|capture|scan|process|store|use|extract|access)\b",
        "target": r"\b(biometric|face\s+(scan|geometry|recognition)|fingerprint|voiceprint|retina|iris|health|medical|financial|payment|card\s+number|bank)\b",
        "risk_msg": "Sensitive biometric, health, or financial data may be collected or processed.",
        "safe_msg": "Protective provision regarding sensitive data found."
    },
    {
        "category": "Location & GPS Tracking",
        "weight": 3,
        "verb": r"\b(collect|track|access|gather|infer|monitor)\b",
        "target": r"\b(precise\s+location|exact\s+location|real[- ]?time\s+location|gps|geolocation|ip\s+address)\b",
        "risk_msg": "Location or device tracking data may be collected.",
        "safe_msg": "Limitation on location tracking found."
    },
    {
        "category": "Third-Party & Ad Sharing",
        "weight": 3,
        "verb": r"\b(share|shares|sharing|disclose|transfer|provide|distribute)\b",
        "target": r"\b(third[- ]part(y|ies)|advertisers?|advertising\s+(partners?|networks?)|marketing\s+partners?|affiliates?|data\s+brokers?)\b",
        "risk_msg": "Information may be shared with third parties, advertisers, or data brokers.",
        "safe_msg": "Restriction or opt-out on third-party sharing found."
    },
    {
        "category": "Cross-Border Data Transfers",
        "weight": 3,
        "verb": r"\b(transfer|transferred|transferring|store|process|host)\b",
        "target": r"\b(internationally|overseas|abroad|cross[- ]?border|other\s+countr(y|ies)|outside\s+(your\s+)?country|global\s+servers?)\b",
        "risk_msg": "Data may be transferred or processed across international borders.",
        "safe_msg": "Safeguards or restrictions on cross-border transfer mentioned."
    },
    {
        "category": "Children & Minors Privacy",
        "weight": 4,
        "verb": r"\b(collect|use|target|allow|permit)\b",
        "target": r"\b(child(ren)?|minor(s)?|under\s+(13|16|18)|student\s+data)\b",
        "risk_msg": "Provisions involving children, minors, or age-related data were detected.",
        "safe_msg": "Restriction or protection for children/minors found."
    },
    {
        "category": "Cookies & Cross-Site Tracking",
        "weight": 1,
        "verb": r"\b(use|uses|using|place|set|deploy|read)\b",
        "target": r"\b(cookies?|tracking\s+pixels?|web\s+beacons?|sdk(s)?|device\s+fingerprint(ing)?)\b",
        "risk_msg": "Cookies, SDKs or tracking technologies may be used.",
        "safe_msg": "Limited use of cookies/trackers mentioned."
    },
    {
        "category": "Indefinite Data Retention",
        "weight": 2,
        "verb": r"\b(retain|store|keep|preserve|hold)\b",
        "target": r"\b(indefinitely|forever|permanently|for\s+as\s+long\s+as\s+necessary|no\s+fixed\s+period)\b",
        "risk_msg": "Data may be retained indefinitely or without clear limit.",
        "safe_msg": "Retention period limits mentioned."
    },
    {
        "category": "Unilateral Policy Changes & Broad Use",
        "weight": 2,
        "verb": r"\b(modify|update|change|amend|revise|use|disclose)\b",
        "target": r"\b(without\s+(prior\s+)?notice|at\s+any\s+time|sole\s+discretion|any\s+purpose|any\s+reason)\b",
        "risk_msg": "Policy terms or broad data usage may change without prior notice or at sole discretion.",
        "safe_msg": "Advance notice or clear update terms mentioned."
    }
]

DATA_USAGE_RULES = [
    {
        "destination": "Advertising, AdTech & Data Brokers",
        "where_tag": "External Ad Networks / Marketing & Data Brokers",
        "purpose": "Targeted ads, cross-context behavioral tracking, or audience matching",
        "pattern": r"\b(advertis(e|ing|ement)|targeted\s+ads|behavioral\s+ads|marketing|promotional|data\s+brokers?)\b"
    },
    {
        "destination": "Third-Party Vendors & Cloud Processors",
        "where_tag": "Third-Party Vendors & Cloud Processors",
        "purpose": "Hosting, payments, support, security, or analytics services",
        "pattern": r"\b(service\s+providers?|vendors?|contractors?|analytics|third[- ]part(y|ies)|cloud)\b"
    },
    {
        "destination": "Cross-Border & International Regions",
        "where_tag": "International / Cross-Border Infrastructure",
        "purpose": "Global operations, regional servers, or international affiliates",
        "pattern": r"\b(internationally|overseas|abroad|cross[- ]?border|other\s+countr(y|ies)|affiliates?)\b"
    },
    {
        "destination": "Legal & Compliance Authorities",
        "where_tag": "Legal Authorities / Compliance Systems",
        "purpose": "Legal compliance, fraud prevention, regulatory or government requests",
        "pattern": r"\b(law\s+enforcement|legal\s+obligation|comply\s+with\s+law|fraud|security|court\s+order|regulat(ory|ors?)|government)\b"
    },
    {
        "destination": "Core Product & Server Infrastructure",
        "where_tag": "Company Servers & Core Product Systems",
        "purpose": "Account management, core features, AI/service delivery and improvement",
        "pattern": r"\b(provide\s+the\s+service|maintain|improve|personalize|account|authenticate)\b"
    },
    {
        "destination": "User Privacy Controls & Rights",
        "where_tag": "User Privacy Controls & Rights",
        "purpose": "Access, correction, deletion, portability, and opt-out rights",
        "pattern": r"\b(delete\s+(your\s+)?(data|account)|opt[- ]?out|access\s+your\s+(data|information)|privacy\s+rights|withdraw\s+consent|rectification|portability)\b"
    }
]


def _extract_clean_html_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    main_node = soup.find("main") or soup.find("article")
    if main_node:
        main_text = re.sub(r"\s+", " ", main_node.get_text(separator=" ", strip=True)).strip()
        if len(main_text.split()) >= 25:
            return main_text

    for tag in soup(["nav", "footer", "header", "aside"]):
        tag.decompose()

    body_text = soup.get_text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", body_text).strip()


def fetch_url_text(url: str) -> str:
    cleaned = (url or "").strip()
    if not cleaned:
        raise ValueError("Please enter a valid website URL.")
    if not cleaned.startswith(("http://", "https://")):
        cleaned = "https://" + cleaned

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        req = urllib.request.Request(cleaned, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            text = _extract_clean_html_text(html)
            if len(text.split()) >= 25:
                return text
            raise ValueError(
                "Not enough readable text extracted from this URL. "
                "Try pasting the policy text instead."
            )
    except urllib.error.HTTPError as exc:
        raise ValueError(f"Could not fetch this URL (HTTP {exc.code}). Try pasting the policy text.")
    except Exception:
        raise ValueError("Unable to read this URL automatically. Please paste the policy text.")


def split_sentences(text: str):
    parts = re.split(r"(?<=[.!?])\s+|\s*[•▪▸]\s*", text)
    return [p.strip() for p in parts if 15 <= len(p.strip()) <= 650]


def matches_any(patterns, s_lower: str) -> bool:
    return any(re.search(p, s_lower, re.IGNORECASE) for p in patterns)


def extract_data_collected(text: str) -> list:
    found = []
    for rule in DATA_COLLECTION_RULES:
        m = re.search(rule["pattern"], text, re.IGNORECASE)
        if m:
            found.append({
                "data_type": rule["data_type"],
                "matched_term": m.group(0)
            })
    return found


def build_user_advice(level: str, data_usage: list) -> list:
    advice = []
    if level == "Red":
        advice.append("Avoid sharing sensitive personal details, exact location, or unnecessary permissions before carefully reviewing the full terms.")
    elif level == "Yellow":
        advice.append("Review privacy and ad settings to disable non-essential tracking or location sharing where possible.")
    else:
        advice.append("No major high-risk clauses were detected, but still review settings periodically.")

    has_rights = any(u.get("where_tag") == "User Privacy Controls & Rights" for u in data_usage)
    if has_rights:
        advice.append("Data access, deletion or opt-out rights are mentioned — check account privacy controls.")
    else:
        advice.append("Clear data deletion or opt-out options were not immediately detected; verify via support or settings.")

    advice.append("This analysis is automated and is not legal advice.")
    return advice


def _call_gemini_analysis(text: str) -> dict | None:
    api_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if not api_key:
        return None

    model_name = (os.environ.get("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL).strip()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

    prompt = (
        "Analyze the following privacy policy text and return ONLY valid JSON with keys:\n"
        '{"risk_score": 0-100, "level": "Green"|"Yellow"|"Red", "summary": "...", '
        '"findings": [{"category": "...", "status": "Risk"|"Conditional"|"Safe Note", "message": "...", "evidence": "..."}], '
        '"advice": ["..."]}\n\n'
        f"Policy text:\n{text[:12000]}"
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        raw_text = (
            body.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        ).strip()
        if not raw_text:
            return None
        parsed = json.loads(raw_text)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def analyze_nlp(text: str):
    sentences = split_sentences(text)
    words = text.split()

    score_points = 0
    findings = []
    seen_risk_cats = set()
    data_usage = []
    seen_destinations = set()

    for sentence in sentences:
        s_low = sentence.lower()

        for rule in RISK_RULES:
            cat = rule["category"]
            if cat in seen_risk_cats:
                continue
            v_match = re.search(rule["verb"], s_low, re.IGNORECASE)
            t_match = re.search(rule["target"], s_low, re.IGNORECASE)
            if v_match and t_match and abs(v_match.start() - t_match.start()) <= 150:
                negated = matches_any(NEGATION_PATTERNS, s_low)
                conditional = matches_any(CONDITIONAL_PATTERNS, s_low)
                if negated:
                    added = 0
                    status = "Safe Note"
                    msg = rule["safe_msg"]
                elif conditional:
                    added = max(1, rule["weight"] - 2)
                    status = "Conditional"
                    msg = f"Conditional usage: {rule['risk_msg']}"
                else:
                    added = rule["weight"]
                    status = "Risk"
                    msg = rule["risk_msg"]
                score_points += added
                seen_risk_cats.add(cat)
                findings.append({
                    "category": cat,
                    "status": status,
                    "weight_added": added,
                    "message": msg,
                    "evidence": sentence[:210] + ("..." if len(sentence) > 210 else "")
                })

        for u_rule in DATA_USAGE_RULES:
            dest = u_rule["destination"]
            if dest in seen_destinations:
                continue
            if re.search(u_rule["pattern"], s_low, re.IGNORECASE):
                negated = matches_any(NEGATION_PATTERNS, s_low)
                seen_destinations.add(dest)
                data_usage.append({
                    "destination": dest,
                    "where_tag": u_rule["where_tag"],
                    "purpose": u_rule["purpose"],
                    "negated": negated,
                    "evidence": sentence[:200] + ("..." if len(sentence) > 200 else "")
                })

    rule_score = max(0, min(score_points * 10, 100))
    gemini_data = _call_gemini_analysis(text)

    if gemini_data:
        g_score = gemini_data.get("risk_score")
        if isinstance(g_score, (int, float)):
            risk_score = max(0, min(100, round(float(g_score))))
        else:
            risk_score = rule_score

        g_level = str(gemini_data.get("level") or "").strip().capitalize()
        if g_level not in ("Red", "Yellow", "Green"):
            g_level = "Red" if risk_score >= 50 else ("Yellow" if risk_score >= 20 else "Green")
        level = g_level

        summary = str(gemini_data.get("summary") or "").strip() or (
            "Significant privacy or data-sharing risks were detected in the policy."
            if level == "Red"
            else (
                "Some tracking, sharing or conditional data terms were detected."
                if level == "Yellow"
                else "No major high-risk privacy clauses were detected in the analyzed text."
            )
        )

        g_findings = gemini_data.get("findings")
        if isinstance(g_findings, list) and g_findings:
            cleaned_findings = []
            for item in g_findings[:15]:
                if isinstance(item, dict):
                    cleaned_findings.append({
                        "category": str(item.get("category") or "Gemini Clause Analysis"),
                        "status": str(item.get("status") or "Risk"),
                        "weight_added": 2 if level == "Red" else 1,
                        "message": str(item.get("message") or ""),
                        "evidence": str(item.get("evidence") or "")[:210],
                    })
            if cleaned_findings:
                findings = cleaned_findings + findings

        g_advice = gemini_data.get("advice")
        advice = [str(a) for a in g_advice if a] if isinstance(g_advice, list) and g_advice else build_user_advice(level, data_usage)
        engine_name = f"Gemini API ({os.environ.get('GEMINI_MODEL') or DEFAULT_GEMINI_MODEL}) + NLP"
    else:
        risk_score = rule_score
        level = "Red" if risk_score >= 50 else ("Yellow" if risk_score >= 20 else "Green")
        summary = (
            "Significant privacy or data-sharing risks were detected in the policy."
            if level == "Red"
            else (
                "Some tracking, sharing or conditional data terms were detected."
                if level == "Yellow"
                else "No major high-risk privacy clauses were detected in the analyzed text."
            )
        )
        advice = build_user_advice(level, data_usage)
        engine_name = "Deterministic NLP (Gemini fallback)"

    if level == "Red":
        verdict = "HIGH RISK (Red)"
    elif level == "Yellow":
        verdict = "MODERATE RISK (Yellow)"
    else:
        verdict = "GENERALLY SAFE (Green)"

    coverage = min(100, round((len(sentences) / 25) * 100)) if len(words) >= 25 else 20

    return {
        "level": level,
        "verdict": verdict,
        "risk_score": risk_score,
        "text_coverage_percent": coverage,
        "summary": summary,
        "word_count": len(words),
        "sentences_analyzed": len(sentences),
        "data_collected": extract_data_collected(text),
        "findings": findings,
        "data_usage": data_usage,
        "user_advice": advice,
        "engine": engine_name,
        "disclaimer": "This analysis is automated and is not legal advice."
    }
