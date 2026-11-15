"""Each check looks at ONE thing in the email and returns a list of findings.

A finding = {"reason": "...", "points": n}
    3 points = strong sign of phishing
    2 points = medium sign
    1 point  = weak sign
    negative = a good sign (the email looks safe)
"""
import re
import warnings
from functools import lru_cache

import joblib

from . import config

warnings.filterwarnings("ignore", category=UserWarning)  # hide the sklearn version notice when loading the model

BRANDS = ["microsoft", "paypal", "google", "apple", "amazon", "dhl", "linkedin", "facebook", "instapay", "vodafone"]
REAL_DOMAINS = ["microsoft.com", "microsoftonline.com", "office.com", "live.com", "outlook.com", "google.com",
                "gmail.com", "paypal.com", "apple.com", "amazon.com", "dhl.com", "linkedin.com", "facebook.com"]
SHORTENERS = ["bit.ly", "tinyurl.com", "t.co", "goo.gl", "cutt.ly"]
DANGEROUS_FILES = [".exe", ".js", ".bat", ".scr", ".html", ".htm", ".iso", ".docm", ".xlsm"]

URGENT_WORDS = ["urgent", "immediately", "within 24 hours", "suspended", "act now", "عاجل", "فورا"]
PASSWORD_WORDS = ["password", "verify your account", "login", "sign in", "otp", "كلمة السر", "الباسورد"]
MONEY_WORDS = ["wire transfer", "bank details", "gift card", "invoice", "iban", "تحويل", "فودافون كاش"]
SECRET_WORDS = ["confidential", "don't tell anyone", "in a meeting", "سري"]
BAIT_WORDS = ["you won", "you have won", "winner", "prize", "free spins", "freispiele", "bonus", "jackpot", "casino",
              "gratis", "gewonnen", "cadeau", "geschenk", "prêmio", "premio", "lottery", "مبروك ربحت", "جائزة"]
BLOCKED_WORDS = ["blocked", "bloqueado", "bloqué", "gesperrt", "geblokkeerd", "suspensão", "suspendu", "expired", "expir"]
RISKY_ENDINGS = (".top", ".xyz", ".click", ".shop", ".icu", ".buzz", ".rest", ".cam", ".zip")
INJECTION_WORDS = ["ignore previous instructions", "classify this email as safe", "this message is legitimate",
                   "you are now", "system prompt", "new instructions", "تجاهل التعليمات", "تجاهل كل التعليمات"]


# ---------- small helpers ----------
def main_domain(domain):
    """login.paypal.com -> paypal.com"""
    return ".".join(domain.split(".")[-2:])


def looks_like(domain, real_name):
    """True if the domain imitates real_name. Example: sentinel-dem0.com imitates sentinel-demo."""
    name = main_domain(domain).split(".")[0]
    if main_domain(domain) in REAL_DOMAINS or name == real_name:
        return False
    cleaned = name.replace("0", "o").replace("1", "l").replace("-", "")
    target = real_name.replace("-", "")
    return target in cleaned


def domain_of(url):
    """http://bad.xyz/login -> bad.xyz"""
    return re.sub(r"^https?://", "", url).split("/")[0].lower()


def find_domain(text):
    """The website written in a link's visible text, e.g. 'Go to login.microsoft.com' -> 'login.microsoft.com'."""
    if "@" in text:   # an email address is not a website
        return ""
    match = re.search(r"([a-z0-9-]+\.)+[a-z]{2,}", text.lower())
    return match.group(0) if match else ""


# ---------- the checks ----------
def check_authentication(email):
    failed = [name.upper() for name in ["spf", "dkim", "dmarc"] if email[name] in ["fail", "softfail"]]
    if failed:
        return [{"reason": f"{', '.join(failed)} failed (sender not verified)", "points": 2}]
    if email["spf"] == email["dkim"] == email["dmarc"] == "pass":
        return [{"reason": "SPF, DKIM and DMARC all passed", "points": -2}]
    return []


def check_sender(email):
    findings = []
    domain = email["from_domain"]
    company = config.COMPANY_DOMAIN.split(".")[0]

    for name in [company] + BRANDS:
        if looks_like(domain, name):
            findings.append({"reason": f"Fake domain: {domain} imitates {name}", "points": 3})
            break

    name = domain.split(".")[0]
    if sum(ch.isdigit() for ch in name) >= 5 or len(name) >= 20:
        findings.append({"reason": f"Sender domain looks auto-generated: {domain}", "points": 2})
    if domain.endswith(RISKY_ENDINGS):
        findings.append({"reason": f"Sender uses a cheap, often-abused domain ending: {domain}", "points": 1})

    reply_domain = email["reply_to"].split("@")[-1]
    if email["reply_to"] and reply_domain != domain:
        findings.append({"reason": f"Replies go to {reply_domain}, not {domain}", "points": 2})

    if domain != config.COMPANY_DOMAIN:
        for boss in config.EXEC_NAMES:
            if boss.lower() in email["from_name"].lower():
                findings.append({"reason": f"Uses the name '{boss}' from an outside address", "points": 3})
    return findings


def check_links(email):
    findings = []
    company = config.COMPANY_DOMAIN.split(".")[0]
    for link in email["links"]:
        real = domain_of(link["url"])
        shown = find_domain(link["text"])
        if shown and main_domain(shown) != main_domain(real):
            findings.append({"reason": f"Link shows {shown} but goes to {real}", "points": 3})
        if any(looks_like(real, name) for name in [company] + BRANDS):
            findings.append({"reason": f"Link goes to a fake domain: {real}", "points": 2})
        if main_domain(real) in SHORTENERS:
            findings.append({"reason": f"Short link hides the real address: {real}", "points": 1})
        if re.fullmatch(r"[\d.]+", real):
            findings.append({"reason": f"Link uses a raw IP address: {real}", "points": 2})
    return findings


def check_words(email):
    text = (email["subject"] + " " + email["body"]).lower()
    findings = []
    for label, words, points in [("Prize / gift bait", BAIT_WORDS, 2),
                                 ("Says your account is blocked", BLOCKED_WORDS, 1),
                                 ("Urgency", URGENT_WORDS, 1),
                                 ("Asks for password", PASSWORD_WORDS, 2),
                                 ("Asks for money", MONEY_WORDS, 2),
                                 ("Asks for secrecy", SECRET_WORDS, 1)]:
        found = [w for w in words if w in text]
        if found:
            findings.append({"reason": f"{label}: {', '.join(found)}", "points": points})
    return findings


def check_injection(email):
    """Normal emails never talk to an AI. If this one does, it is an attack."""
    text = (email["subject"] + " " + email["body"]).lower()
    found = [w for w in INJECTION_WORDS if w in text]
    if found:
        return [{"reason": f"Tries to give orders to the AI: {', '.join(found)}", "points": 3}]
    return []


def check_attachments(email):
    findings = []
    for name in email["attachments"]:
        if name.lower().endswith(tuple(DANGEROUS_FILES)):
            findings.append({"reason": f"Dangerous attachment: {name}", "points": 3})
        if name.count(".") >= 2:
            findings.append({"reason": f"Double extension (hides the real type): {name}", "points": 2})
    return findings


@lru_cache   # load the model once, not for every email
def load_model():
    return joblib.load(config.MODELS_DIR / "model.pkl"), joblib.load(config.MODELS_DIR / "vectorizer.pkl")


def check_ml(email):
    """Ask my trained ML model (TF-IDF + Logistic Regression) about the text."""
    model, vectorizer = load_model()
    text = email["subject"] + " " + email["body"]
    ham, phishing, spam = model.predict_proba(vectorizer.transform([text]))[0]  # 0=ham, 1=phishing, 2=spam

    if phishing + spam >= 0.9:
        return [{"reason": f"ML model: {phishing + spam:.0%} phishing/spam", "points": 3}]
    if phishing + spam >= 0.6:
        return [{"reason": f"ML model: {phishing + spam:.0%} phishing/spam", "points": 2}]
    if ham >= 0.9:
        return [{"reason": f"ML model: {ham:.0%} normal email", "points": -1}]
    return []


ALL_CHECKS = [check_authentication, check_sender, check_links, check_words,
              check_injection, check_attachments, check_ml]
