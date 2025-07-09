import imaplib
import email
from email.header import decode_header
import os
import base64
import json

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ["https://mail.google.com/"]


def _get_credentials():
    """Retourne des Credentials valides.
    Priorité :
    1. TOKEN_JSON_B64 (CI)
    2. token.json local
    3. Flux OAuth interactif (localhost)
    """

    creds = None

    token_b64 = os.getenv("TOKEN_JSON_B64")
    if token_b64:
        try:
            token_info = json.loads(base64.b64decode(token_b64))
            creds = Credentials.from_authorized_user_info(token_info, SCOPES)
        except Exception as exc:
            print("Impossible de décoder TOKEN_JSON_B64:", exc)

    if not creds and os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=8080)
        try:
            with open("token.json", "w") as f:
                f.write(creds.to_json())
        except OSError:
            pass

    return creds


def _build_xoauth2_string(username: str, access_token: str) -> bytes:
    return f"user={username}\1auth=Bearer {access_token}\1\1".encode()


# ---------------------------------------------------------------------------
# Fonctions principales
# ---------------------------------------------------------------------------

def fetch_last_mail_html(gm_filter: str | None = None) -> str | None:
    """Renvoie le corps HTML du dernier mail correspondant au filtre Gmail."""

    creds = _get_credentials()

    email_user = os.getenv("MAIL_USER")
    if not email_user:
        raise RuntimeError("MAIL_USER n'est pas défini")

    auth_string = _build_xoauth2_string(email_user, creds.token)
    imap = imaplib.IMAP4_SSL("imap.gmail.com")
    imap.authenticate("XOAUTH2", lambda _: auth_string)
    imap.select("INBOX")

    # Construction de la requête
    if gm_filter:
        raw_query = gm_filter if gm_filter.startswith("\"") else f'"{gm_filter}"'
        if any(ord(c) > 127 for c in raw_query):
            status, data = imap.search("UTF-8", "X-GM-RAW", raw_query)
        else:
            status, data = imap.search(None, "X-GM-RAW", raw_query)
    else:
        status, data = imap.search(None, "ALL")

    if status != "OK" or not data or not data[0]:
        print("Aucun message trouvé")
        imap.logout()
        return None

    last_id = data[0].split()[-1]
    status, msg_data = imap.fetch(last_id, "(RFC822)")
    if status != "OK":
        print("Impossible de récupérer le message", last_id)
        imap.logout()
        return None

    msg = email.message_from_bytes(msg_data[0][1])
    html_part = None
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                html_part = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                break
    else:
        if msg.get_content_type() == "text/html":
            payload = msg.get_payload(decode=True)
            html_part = payload.decode(msg.get_content_charset() or "utf-8", errors="replace")

    imap.logout()
    return html_part


def list_gmail_labels():
    """Affiche les labels Gmail disponibles."""
    creds = _get_credentials()
    email_user = os.getenv("MAIL_USER")
    if not email_user:
        raise RuntimeError("MAIL_USER n'est pas défini")
    auth_string = _build_xoauth2_string(email_user, creds.token)
    imap = imaplib.IMAP4_SSL("imap.gmail.com")
    imap.authenticate("XOAUTH2", lambda _: auth_string)
    typ, data = imap.list()
    if typ == "OK":
        for line in data:
            print(line.decode())
    imap.logout()


if __name__ == "__main__":
    filter_query = os.getenv("GMAIL_FILTER")
    html = fetch_last_mail_html(filter_query)
    if html:
        print(html) 