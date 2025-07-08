import imaplib
import email
from email.header import decode_header
import os
import base64

# Librairies Google OAuth2
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Portée OAuth : accès complet à Gmail via IMAP
SCOPES = ["https://mail.google.com/"]


def _get_credentials():
    """Retourne un objet Credentials valide, en lançant le flux OAuth si nécessaire.

    • Le fichier client OAuth (client_id / client_secret) doit être présent sous
      le nom `credentials.json` (téléchargé depuis Google Cloud Console).
    • Les jetons sont persistés dans `token.json` pour éviter de se reconnecter
      à chaque exécution.
    """

    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    # Rafraîchir ou lancer le flux si nécessaire
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=8080)

        # Sauvegarder / mettre à jour le token
        with open("token.json", "w") as token_file:
            token_file.write(creds.to_json())

    return creds


def _build_xoauth2_string(username: str, access_token: str) -> bytes:
    """Construit la chaîne d'authentification XOAUTH2 attendue par Gmail."""

    return f"user={username}\1auth=Bearer {access_token}\1\1".encode()


def fetch_mails():

    # Obtenir les credentials OAuth2 (lance un navigateur la 1ère fois)
    creds = _get_credentials()

    # Adresse e-mail : soit variable d'env, soit extraite des credentials
    email_user = os.getenv("MAIL_USER", "sauvegardeportail@gmail.com")

    # Préparation de la chaîne XOAUTH2
    auth_string = _build_xoauth2_string(email_user, creds.token)

    print("\n>>> Connexion à imap.gmail.com …")
    imap = imaplib.IMAP4_SSL("imap.gmail.com")
    imap.debug = 4  # verbosité protocole (désactivez en prod)

    print(">>> Authentification XOAUTH2 …")
    try:
        imap.authenticate("XOAUTH2", lambda _: auth_string)
    except imaplib.IMAP4.error as err:
        print("! Erreur d'authentification :", err)
        return []

    print(">>> Sélection du dossier INBOX …")
    imap.select("INBOX")

    print(">>> Récupération de la liste des messages …")
    status, messages = imap.search(None, "ALL")
    mails = []

    print(">>> Téléchargement des sujets …")
    for num in messages[0].split():
        typ, data = imap.fetch(num, '(RFC822)')
        raw_email = data[0][1]
        msg = email.message_from_bytes(raw_email)
        subject, encoding = decode_header(msg["Subject"])[0]
        if isinstance(subject, bytes):
            subject = subject.decode(encoding or "utf-8", errors="replace")
        mails.append({"subject": subject})

    print(">>> Fermeture de la connexion …")
    imap.close()
    imap.logout()

    
    return mails


# --------------------------------------------------
# 2) Nouvelle fonction : récupérer le corps HTML du
#    dernier mail (id le plus élevé)
# --------------------------------------------------

def get_last_mail_html(gm_filter: str | None = None):
    """Récupère le corps HTML du dernier message qui correspond au filtre Gmail.

    gm_filter : syntaxe de recherche Gmail (ex: 'from:(foo@bar.com) -{"Spam"}').
    S'il est None, la fonction considère tous les messages.
    """

    creds = _get_credentials()
    email_user = os.getenv("MAIL_USER", "sauvegardeportail@gmail.com")

    auth_string = _build_xoauth2_string(email_user, creds.token)

    imap = imaplib.IMAP4_SSL("imap.gmail.com")
    imap.authenticate("XOAUTH2", lambda _: auth_string)

    imap.select("INBOX")

    # Recherche selon le filtre Gmail (X-GM-RAW) si fourni
    if gm_filter:
        # Pour éviter l'erreur "Could not parse command", on entoure la requête de guillemets
        raw_query = gm_filter
        if not (gm_filter.startswith("\"") and gm_filter.endswith("\"")):
            raw_query = f'"{gm_filter}"'

        if any(ord(c) > 127 for c in raw_query):
            status, data = imap.search("UTF-8", "X-GM-RAW", raw_query)
        else:
            status, data = imap.search(None, "X-GM-RAW", raw_query)
    else:
        status, data = imap.search(None, "ALL")

    if status != "OK" or not data or not data[0]:
        print("Aucun message trouvé")
        return None

    last_id = data[0].split()[-1]

    # Récupérer l'email complet
    status, msg_data = imap.fetch(last_id, "(RFC822)")
    if status != "OK":
        print("Impossible de récupérer le message", last_id)
        return None

    raw_email = msg_data[0][1]
    msg = email.message_from_bytes(raw_email)

    html_part = None
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                html_part = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                html_part = html_part.decode(charset, errors="replace")
                break
    else:
        if msg.get_content_type() == "text/html":
            html_part = msg.get_payload(decode=True)
            html_part = html_part.decode(msg.get_content_charset() or "utf-8", errors="replace")

    imap.logout()

    return html_part


# Filtre Gmail souhaité
FILTER = 'from:(reservation@rentiles.fr)'


if __name__ == "__main__":
    html = get_last_mail_html(FILTER)
    if html:
        print("\n===== Corps HTML du dernier mail =====\n")
        print(html)
    else:
        print("Aucun corps HTML trouvé.")


# --------------------------------------------------
# 3) Option utilitaire : lister les labels Gmail (boîtes)
# --------------------------------------------------

def list_gmail_labels():
    """Affiche tous les labels (boîtes IMAP) disponibles."""

    creds = _get_credentials()
    email_user = os.getenv("MAIL_USER", "sauvegardeportail@gmail.com")
    auth_string = _build_xoauth2_string(email_user, creds.token)

    imap = imaplib.IMAP4_SSL("imap.gmail.com")
    imap.authenticate("XOAUTH2", lambda _: auth_string)

    typ, data = imap.list()
    if typ == "OK":
        print("\n=== Labels Gmail ===")
        for line in data:
            print(line.decode())
    else:
        print("Impossible de lister les labels :", data)

    imap.logout()
