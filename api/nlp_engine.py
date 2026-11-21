import re
import requests
from bs4 import BeautifulSoup

NEGATION_PATTERNS = [
    r"\bdo\s+not\b", r"\bdon't\b", r"\bdoes\s+not\b", r"\bdoesn't\b",
    r"\bnever\b", r"\bwill\s+not\b", r"\bwon't\b", r"\bprohibit(s|ed)?\b",
    r"\bdo\s+not\s+sell\b", r"\bnot\s+sell\b", r"\bnot\s+share\b",
    r"\bno\s+personal\s+data\s+(is\s+)?sold\b"
]

CONDITIONAL_PATTERNS = [
    r"\bwith\s+your\s+(explicit\s+)?consent\b",
    r"\bif\s+you\s+(opt[- ]?in|choose|enable|authorize)\b",
    r"\bexcept\s+(as\s+)?required\s+by\s+law\b",
    r"\baggregated\s+or\s+de[- ]?identified\b"
]

RISK_RULES = [
    {
        "category": "Data Selling & Monetization",
        "weight": 5,
        "verb": r"\b(sell|sells|selling|sold|monetize|rent|lease|trade)\b",
        "target": r"\b(personal\s+(data|information)|user\s+(data|information)|your\s+(data|information)|data)\b",
        "risk_msg": "Personal data may be sold, rented, or monetized.",
        "safe_msg": "Clear restriction on selling personal data found."
    },
    {
        "category": "Location & GPS Tracking",
        "weight": 3,
        "verb": r"\b(collect|track|access|gather|infer|monitor)\b",
        "target": r"\b(precise\s+location|exact\s+location|real[- ]?time\s+location|gps|geolocation)\b",
        "risk_msg": "Precise location or GPS data may be collected.",
        "safe_msg": "Limitation on location tracking found."
    },
    {
        "category": "Third-Party & Ad Sharing",
        "weight": 3,
        "verb": r"\b(share|shares|sharing|disclose|transfer|provide|distribute)\b",
        "target": r"\b(third[- ]part(y|ies)|advertisers?|advertising\s+(partners?|networks?)|marketing\s+partners?|affiliates?)\b",
        "risk_msg": "Information may be shared with third parties or advertisers.",
        "safe_msg": "Restriction or opt-out on third-party sharing found."
    },
    {
        "category": "Biometric & Sensitive Data",
        "weight": 4,
        "verb": r"\b(collect|capture|scan|process|store|use|extract)\b",
        "target": r"\b(biometric|face\s+(scan|geometry|recognition)|fingerprint|voiceprint|retina|iris)\b",
        "risk_msg": "Biometric identifiers may be collected or processed.",
        "safe_msg": "Protective provision regarding biometric data found."
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
    }
]

DATA_USAGE_RULES = [
    {
        "destination": "Advertising & Marketing Networks",
        "where_tag": "External Ad Networks / Marketing Partners",
        "purpose": "Targeted or behavioral ads and campaign measurement",
        "pattern": r"\b(advertis(e|ing|ement)|targeted\s+ads|behavioral\s+ads|marketing|promotional)\b"
    },
    {
        "destination": "Third-Party Vendors & Service Providers",
        "where_tag": "Third-Party Vendors & Cloud Processors",
        "purpose": "Hosting, payments, support or analytics services",
        "pattern": r"\b(service\s+providers?|vendors?|contractors?|analytics|third[- ]part(y|ies))\b"
    },
    {
        "destination": "Legal & Compliance Authorities",
        "where_tag": "Legal Authorities / Compliance Systems",
        "purpose": "Legal compliance, fraud prevention or government requests",
        "pattern": r"\b(law\s+enforcement|legal\s+obligation|comply\s+with\s+law|fraud|security|court\s+order)\b"
    },
    {
        "destination": "Core Product & Server Infrastructure",
        "where_tag": "Company Servers & Core Product Systems",
        "purpose": "Account management, core features and service improvement",
        "pattern": r"\b(provide\s+the\s+service|maintain|improve|personalize|account|authenticate)\b"
    },
    {
        "destination": "User Privacy Controls & Rights",
        "where_tag": "User Privacy Controls & Rights",
        "purpose": "Access, correction, deletion and opt-out rights",
        "pattern": r"\b(delete\s+(your\s+)?(data|account)|opt[- ]?out|access\s+your\s+(data|information)|privacy\s+rights|withdraw\s+consent)\b"
    }
]


def fetch_url_text(url: str) -> str:
    cleaned = url.strip()
    if not cleaned.startswith(("http://", "https://")):
        cleaned = "https://" + cleaned

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    resp = requests.get(cleaned, headers=headers, timeout=15, allow_redirects=True)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "aside"]):
        tag.decompose()

    text = soup.get_text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", text)


def split_sentences(text: str):
    parts = re.split(r"(?<=[.!?])\s+|\s*[•▪▸]\s*", text)
    return [p.strip() for p in parts if 15 <= len(p.strip()) <= 650]


def matches_any(patterns, s_lower: str) -> bool:
    return any(re.search(p, s_lower, re.IGNORECASE) for p in patterns)


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

    risk_score = max(0, min(score_points * 10, 100))

    if risk_score >= 50:
        level = "Red"
        verdict = "HIGH RISK (Red)"
        summary = "Significant privacy or data-sharing risks were detected in the policy."
    elif risk_score >= 20:
        level = "Yellow"
        verdict = "MODERATE RISK (Yellow)"
        summary = "Some tracking, sharing or conditional data terms were detected."
    else:
        level = "Green"
        verdict = "GENERALLY SAFE (Green)"
        summary = "No major high-risk privacy clauses were detected in the analyzed text."

    coverage = min(100, round((len(sentences) / 25) * 100)) if len(words) >= 25 else 20

    return {
        "level": level,
        "verdict": verdict,
        "risk_score": risk_score,
        "text_coverage_percent": coverage,
        "summary": summary,
        "word_count": len(words),
        "sentences_analyzed": len(sentences),
        "findings": findings,
        "data_usage": data_usage,
        "user_advice": build_user_advice(level, data_usage),
        "engine": "Deterministic NLP",
        "disclaimer": "This NLP analysis reflects text patterns found in the provided policy and cannot guarantee actual runtime or hidden backend behavior. Not legal advice."
    }
