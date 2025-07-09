# Gmail IMAP → n8n

Ce projet récupère le dernier e-mail (corps HTML) d’une boîte Gmail à l’aide d’IMAP/OAuth 2, puis – via GitHub Actions – l’envoie optionnellement à un webhook n8n.

---
## 1. Exécution locale

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt  # ou laisser le script installer les libs
```

1. **Créer un client OAuth "Application de bureau"** dans Google Cloud → APIs & Services → Identifiants.  
   Téléchargez le fichier **credentials.json** et placez-le à la racine du dépôt.
2. Lancez le script :

   ```bash
   export MAIL_USER="moncompte@gmail.com"
   export GMAIL_FILTER="from:(newsletter@example.com)"
   python gmail_fetch.py
   ```
   Le navigateur s’ouvre ; après validation le fichier **token.json** est créé.
Les fichiers **credentials_default.json** et **token_default.json** fournis dans ce dépôt servent d’exemple ; copiez-les en `credentials.json` et `token.json` puis remplissez-les avec vos vraies valeurs.

* `credentials.json` s’obtient depuis Google Cloud Console (ID client « Application de bureau »).  
* `token.json` est généré automatiquement après le premier lancement interactif ; vous pouvez ensuite l’encoder en Base-64 pour `TOKEN_JSON_B64`.

---
## 2. Déploiement GitHub Actions

Le workflow YAML se trouve dans `.github/workflows/gmail.yml` et exécute `gmail_fetch.py`.

### Secrets obligatoires
| Secret | Description |
|--------|-------------|
| `MAIL_USER` | Adresse Gmail à relever |
| `CREDENTIALS_JSON` | Contenu de `credentials.json` encodé Base-64 〈 `base64 credentials.json` 〉 |
| `TOKEN_JSON_B64` | Contenu de `token.json` encodé Base-64 (généré après la 1ʳᵉ exécution locale) |
| `GMAIL_FILTER` | Chaîne de recherche Gmail (ex. `from:(newsletter@example.com)`) |

### Secrets optionnels (pour n8n)
| Secret | Description |
|--------|-------------|
| `N8N_URL` | URL du webhook n8n (méthode POST) |
| `N8N_KEY` | Clé API associée au webhook (en-tête `X-API-Key`) |

### Fréquence d’exécution
La planification par défaut est _toutes les heures_ (`cron: "0 * * * *"`). Modifiez-la dans le YAML si nécessaire.

---
## 3. Personnaliser la recherche Gmail

Le filtre n’est plus codé en dur ; il vient de la variable d’environnement `GMAIL_FILTER` (ou du secret GitHub).  
Utilisez la même syntaxe que dans la barre de recherche Gmail : `label:"Nom"`, `subject:xxx`, `-"mots"`, etc.

---
## 4. Sécurité
* Ne commitez jamais vos **vrais** `credentials.json` / `token.json`. Utilisez les fichiers *_default.json* comme modèles.
* Les secrets GitHub sont chiffrés au repos et injectés en variables d’environnement uniquement pendant le job.

---
## 5. Décodeur côté n8n
Le workflow envoie `mail.html` encodé en Base-64.  
Ajoutez un nœud **Function** juste après le Webhook :
```javascript
const buff = Buffer.from($json.html, 'base64');
return [{ json: { html: buff.toString('utf-8') } }];
```
Vous pouvez ensuite parser ou stocker le contenu comme vous le souhaitez. 

---
## 6. Créer un Personal Access Token GitHub

1. Pour un **classic PAT** : <https://github.com/settings/tokens> → « Generate new token (classic) ».  
2. Pour un **fine-grained token** : <https://github.com/settings/personal-access-tokens/new>.

Accordez au minimum le scope `repo` (actions déclenchées dans le dépôt).  Copiez-le et stockez-le dans n8n (HTTP Basic Auth : username vide, password = PAT). 