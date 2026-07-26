# Guide de Démarrage et Configuration - Projet Cid (Clin-Bot)

Ce projet est un Assistant de Santé Clinique doté d'une interface d'administration et d'un chatbot WhatsApp via Twilio.

---

## 1. Démarrage Rapide

1. **Activer l'environnement virtuel et démarrer la base de données :**
   ```bash
   source .venv/bin/activate
   docker compose up -d postgres
   ```

2. **Démarrer le serveur FastAPI :**
   ```bash
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```

3. **Démarrer le tunnel Cloudflare (pour les webhooks Twilio et les liens publics) :**
   ```bash
   cloudflared tunnel --url http://127.0.0.1:8000
   ```

---

## 2. Configuration Cruciale de l'envoi des documents PDF (WhatsApp)

Pour que Twilio puisse délivrer les fiches de rendez-vous et les résultats d'analyses (PDF) sur les téléphones des patients, **Twilio doit pouvoir télécharger le document depuis votre serveur via une URL publique**.

### Le problème avec `localhost` :
Si vous naviguez sur l'interface d'administration locale (`http://localhost:8000/admin`), le système génère par défaut des liens en `http://localhost:8000/...`. Twilio rejette ces liens car il ne peut pas accéder à votre machine locale.

### La Solution :
1. Repérez l'adresse HTTPS générée par la commande `cloudflared` (ex: `https://votre-sous-domaine.trycloudflare.com`).
2. Ouvrez le fichier `.env` à la racine du projet.
3. Renseignez cette adresse dans la variable `BASE_URL` :
   ```env
   BASE_URL=https://votre-sous-domaine.trycloudflare.com
   ```
4. Redémarrez le serveur FastAPI.

Grâce à cette configuration, même si vous utilisez l'application d'administration sur `http://localhost:8000`, le serveur générera des liens publics via le tunnel Cloudflare pour Twilio, garantissant l'envoi réussi des rapports PDF aux patients !
