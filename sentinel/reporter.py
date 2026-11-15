"""Turn results into emails, and send them (or save them in data/outbox when DRY_RUN is on)."""
import re
import smtplib
from datetime import datetime
from email.message import EmailMessage

from . import config, memory
from .llm import get_llm, text_of

COLORS = {"phishing": "#dc2626", "critical": "#dc2626", "suspicious": "#d97706", "warning": "#d97706",
          "safe": "#16a34a", "ok": "#16a34a"}


def hide_emails(text):
    """Privacy: ahmed.hassan.ceo@gmail.com -> ***@gmail.com"""
    return re.sub(r"[\w.+-]+@", "***@", text)


def alert_email(result):
    subject = f"[Sentinel] {result['verdict'].upper()}: {result['title']}"
    findings = "".join(f"<li>{hide_emails(f['reason'])} ({f['points']:+d})</li>" for f in result["findings"])
    actions = "".join(f"<li>{a['action']}{' (needs approval)' if a['needs_approval'] else ''}</li>"
                      for a in result["actions"])
    status = result.get("extra", {}).get("status_update", "")
    html = f"""
    <h2 style="color:{COLORS[result['verdict']]}">{result['verdict'].upper()}: {result['title']}</h2>
    <p><b>Agent:</b> {result['agent']} &nbsp; <b>Decided by:</b> {result.get('decided_by', 'rules')} &nbsp;
       <b>Evidence points:</b> {result['score']} &nbsp; <b>Tools used:</b> {len(result.get('steps', []))}</p>
    <p>{hide_emails(result['summary'])}</p>{f"<p><i>{hide_emails(status)}</i></p>" if status else ""}
    <h3>Why</h3><ul>{findings}</ul>
    <h3>Next steps</h3><ul>{actions}</ul>"""
    return subject, html


def daily_brief(use_llm=True):
    """Today's results for management. With an LLM, it also writes a short executive summary."""
    results = memory.todays_results()
    urgent = [r for r in results if r["verdict"] in ["phishing", "critical"]]
    subject = f"[Sentinel] Daily brief {datetime.now():%Y-%m-%d}: {len(urgent)} urgent items"
    rows = "".join(f"<li style='color:{COLORS.get(r['verdict'], '#000')}'>{r['verdict'].upper()} | {r['agent']} | "
                   f"{r['title']}</li>" for r in results)
    intro = f"<p>{len(results)} events today.</p>"

    llm = get_llm() if use_llm and results else None
    if llm:
        try:
            lines = "\n".join(f"- {r['agent']}: {r['verdict']} - {r['title']} - {r['summary'][:300]}" for r in results[-15:])
            prompt = ("You are Sentinel. Write a short daily brief for the company's management (4 sentences, plain English): "
                      "the most urgent problems first, what was already done, and what needs their decision.\n" + lines)
            intro = f"<p>{hide_emails(text_of(llm.invoke(prompt)))}</p>" + intro
        except Exception as error:
            intro += f"<p><i>(LLM not used: {type(error).__name__})</i></p>"
    html = f"<h2>Sentinel daily brief</h2>{intro}<ul>{rows}</ul>"
    return subject, html


def send_email(to, subject, html):
    if config.DRY_RUN or not config.SMTP_USER:
        config.OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
        path = config.OUTBOX_DIR / f"{datetime.now():%Y%m%d-%H%M%S-%f}.html"
        path.write_text(f"<p>To: {to}<br>Subject: {subject}</p>{html}", encoding="utf-8")
        return f"saved to outbox: {path.name}"

    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = config.SMTP_USER, to, subject
    msg.set_content("Please open this email in an HTML email app.")
    msg.add_alternative(html, subtype="html")
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(config.SMTP_USER, config.SMTP_PASSWORD)
        server.send_message(msg)
    return f"sent to {to}"
