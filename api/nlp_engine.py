import os
import re
import requests
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    import torch
    import torch.nn.functional as F
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    _TORCH_AVAILABLE = True
except Exception:
    _TORCH_AVAILABLE = False

DEFAULT_HF_REPO_ID = "mayurpatil1974007/privacy-policy-risk-model"

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

_MODEL_BUNDLE = None
_MODEL_LOAD_ATTEMPTED = False


def _resolve_model_source() -> str | None:
    env_path = (os.environ.get("PRIVACY_MODEL_DIR") or "").strip()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    local_candidates = [
        env_path,
        os.path.join(base_dir, "final_privacy_model"),
        os.path.join(base_dir, "..", "final_privacy_model"),
        "./final_privacy_model",
    ]
    for path in local_candidates:
        if path and os.path.isdir(path) and os.path.isfile(os.path.join(path, "config.json")):
            return os.path.abspath(path)

    hf_repo = (os.environ.get("HF_MODEL_REPO") or DEFAULT_HF_REPO_ID).strip()
    return hf_repo or None


def _get_legal_bert():
    global _MODEL_BUNDLE, _MODEL_LOAD_ATTEMPTED
    if _MODEL_LOAD_ATTEMPTED:
        return _MODEL_BUNDLE
    _MODEL_LOAD_ATTEMPTED = True

    if not _TORCH_AVAILABLE:
        return None

    source = _resolve_model_source()
    if not source:
        return None

    try:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        tokenizer = AutoTokenizer.from_pretrained(source)
        model = AutoModelForSequenceClassification.from_pretrained(source).to(device)
        model.eval()
        _MODEL_BUNDLE = (tokenizer, model, device, source)
        return _MODEL_BUNDLE
    except Exception:
        return None


def _map_probs_to_color(p_low: float, p_med: float, p_high: float, low_threshold=0.35, high_threshold=0.50):
    if p_high >= high_threshold and p_high >= p_low:
        return "HIGH", "Red", "🔴", p_high * 100.0
    if p_low >= low_threshold and p_low >= p_high * 0.8:
        return "LOW", "Green", "🟢", p_low * 100.0
    return "MEDIUM", "Yellow", "🟡", p_med * 100.0


def predict_clauses_with_model(sentences: list[str]) -> tuple[list[dict], str | None]:
    bundle = _get_legal_bert()
    if not bundle or not sentences:
        return [], None

    tokenizer, model, device, source = bundle
    try:
        inputs = tokenizer(
            sentences,
            padding=True,
            truncation=True,
            max_length=256,
            return_tensors="pt"
        ).to(device)

        with torch.no_grad():
            logits = model(**inputs).logits
            probs = F.softmax(logits, dim=-1).cpu().numpy()

        clause_predictions = []
        for sentence, prob in zip(sentences, probs):
            p_low, p_med, p_high = float(prob[0]), float(prob[1]), float(prob[2])
            risk, color, icon, score = _map_probs_to_color(p_low, p_med, p_high)
            clause_predictions.append({
                "clause": sentence,
                "risk": risk,
                "level": color,
                "icon": icon,
                "confidence": round(score, 1),
                "probs": {
                    "low": round(p_low * 100, 1),
                    "medium": round(p_med * 100, 1),
                    "high": round(p_high * 100, 1),
                }
            })
        return clause_predictions, source
    except Exception:
        return [], None


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

    attempts = [
        {
            "headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
            "verify": True,
            "timeout": 7,
        },
        {
            "headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                    "Version/17.5 Safari/605.1.15"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-GB,en;q=0.8",
            },
            "verify": False,
            "timeout": 8,
        },
    ]

    last_err = None
    with requests.Session() as session:
        for cfg in attempts:
            try:
                resp = session.get(
                    cleaned,
                    headers=cfg["headers"],
                    timeout=cfg["timeout"],
                    allow_redirects=True,
                    verify=cfg["verify"],
                )
                resp.raise_for_status()
                text = _extract_clean_html_text(resp.text)
                if len(text.split()) >= 25:
                    return text
                last_err = ValueError(
                    "Not enough readable text extracted from this URL. "
                    "The site may load via JavaScript or block bots. Try pasting the policy text or uploading a file."
                )
            except requests.exceptions.HTTPError as exc:
                code = exc.response.status_code if exc.response is not None else "unknown"
                if code in (401, 403, 429):
                    last_err = ValueError(
                        f"This website blocked automated URL access (HTTP {code}). "
                        "Please paste the policy text or upload a PDF/file instead."
                    )
                    break
                last_err = ValueError(
                    f"Could not fetch this URL (HTTP {code}). Try pasting the policy text or uploading a file."
                )
            except requests.exceptions.Timeout:
                last_err = ValueError(
                    "The website took too long to respond. Try pasting the policy text or uploading a file."
                )
            except Exception:
                last_err = ValueError(
                    "Unable to read this URL automatically. Please paste the policy text or upload a file."
                )

    raise last_err or ValueError(
        "Unable to read this URL automatically. Please paste the policy text or upload a file."
    )


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

    model_clauses, loaded_source = predict_clauses_with_model(sentences[:60])
    red_count = sum(1 for c in model_clauses if c["level"] == "Red")
    yellow_count = sum(1 for c in model_clauses if c["level"] == "Yellow")
    green_count = sum(1 for c in model_clauses if c["level"] == "Green")

    if model_clauses:
        total_c = len(model_clauses)
        model_risk_ratio = ((red_count * 1.0) + (yellow_count * 0.45)) / total_c
        model_score = round(min(100, model_risk_ratio * 100))
        rule_score = max(0, min(score_points * 10, 100))
        risk_score = round(0.7 * model_score + 0.3 * rule_score)

        if red_count > 0 and risk_score < 50:
            risk_score = max(risk_score, 55)

        for c in model_clauses[:15]:
            findings.append({
                "category": f"Model Clause ({c['icon']} {c['level']} · {c['confidence']}%)",
                "status": c["risk"],
                "weight_added": 2 if c["level"] == "Red" else (1 if c["level"] == "Yellow" else 0),
                "message": f"Classified as {c['level']} ({c['risk']}) with {c['confidence']}% confidence.",
                "evidence": c["clause"][:210] + ("..." if len(c["clause"]) > 210 else "")
            })
        engine_name = f"Fine-Tuned Legal-BERT ({loaded_source}) + NLP"
    else:
        risk_score = max(0, min(score_points * 10, 100))
        engine_name = "Deterministic NLP (Model fallback)"

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
        "clause_breakdown": {
            "red": red_count,
            "yellow": yellow_count,
            "green": green_count,
            "total": len(model_clauses)
        },
        "clauses": model_clauses,
        "data_collected": extract_data_collected(text),
        "findings": findings,
        "data_usage": data_usage,
        "user_advice": build_user_advice(level, data_usage),
        "engine": engine_name,
        "disclaimer": "This analysis is automated and is not legal advice."
    }
