"""Read a raw email (.eml) and turn it into a simple dictionary."""
import re
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr


def read_email(raw):
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    msg = BytesParser(policy=policy.default).parsebytes(raw)

    from_name, from_address = parseaddr(str(msg["From"] or ""))
    reply_to = parseaddr(str(msg["Reply-To"] or ""))[1]
    auth = str(msg["Authentication-Results"] or "")

    text, html, attachments = "", "", []
    for part in msg.walk():
        if part.is_multipart():
            continue
        if part.get_filename():
            attachments.append(part.get_filename())
        elif part.get_content_type() == "text/plain":
            text += part.get_content()
        elif part.get_content_type() == "text/html":
            html += part.get_content()

    return {
        "from_name": from_name,
        "from_address": from_address.lower(),
        "from_domain": from_address.split("@")[-1].lower(),
        "reply_to": reply_to.lower(),
        "subject": str(msg["Subject"] or ""),
        "spf": find_result(auth, "spf"),
        "dkim": find_result(auth, "dkim"),
        "dmarc": find_result(auth, "dmarc"),
        "body": (text + " " + remove_html(html)).strip(),
        "links": find_links(html, text),
        "attachments": attachments,
    }


def find_result(auth_text, name):
    """Find 'spf=pass' / 'dkim=fail' ... in the Authentication-Results header."""
    match = re.search(name + r"=(\w+)", auth_text)
    return match.group(1).lower() if match else "none"


def remove_html(html):
    return re.sub(r"<[^>]+>", " ", html)


def find_links(html, text):
    """Each link has 'text' (what the user sees) and 'url' (where it really goes)."""
    links = []
    for url, shown in re.findall(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.S):
        links.append({"text": remove_html(shown).strip(), "url": url})
    for url in re.findall(r"https?://[^\s<>\"]+", text):
        links.append({"text": "", "url": url})
    return links
