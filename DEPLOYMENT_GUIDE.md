# Vyapar Saarthi AI — Production Deployment Guide

This guide provides the best, most cost-effective, and reliable architecture to deploy **Vyapar Saarthi AI** online.

---

## 🏗️ Recommended Architecture

```
User (Browser / Mobile) ---> Render.com (Flask + Gunicorn WSGI) ---> Supabase PostgreSQL
                                                               ---> Google Gemini API
```

| Component | Provider | Cost | Why Chosen |
| :--- | :--- | :--- | :--- |
| **Web App Hosting** | **Render.com** | **Free** | Native Flask/Python support, automatic GitHub deployments, free SSL/HTTPS certificate, Gunicorn WSGI support. |
| **Production Database** | **Supabase** | **Free** | Managed PostgreSQL database, high performance, automatic backups, persistent cloud storage. |
| **AI Processing** | **Google Gemini API** | Pay-as-you-go | Fast voice/text intent extraction and product matching. |

---

## 📋 Step-by-Step Deployment Steps

### Step 1: Set Up Cloud Database (Supabase)

1. Sign up at [supabase.com](https://supabase.com).
2. Click **New Project** and name it `vyapar-saarthi-db`.
3. Set a strong **Database Password** and select the region nearest to your users (e.g., `Mumbai / India`).
4. Once created, go to **Project Settings → Database → Connection String → URI**.
5. Copy the connection string format:
   ```env
   postgresql://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres
   ```

---

### Step 2: Deploy Web App on Render.com

1. Sign up / Log in to [render.com](https://render.com).
2. Click **New +** → Select **Web Service**.
3. Connect your GitHub account and select your repository: **`Dipesh562/vyapar-saarthi-ai`**.
4. Configure the service parameters:

| Field | Value |
| :--- | :--- |
| **Name** | `vyapar-saarthi-ai` |
| **Region** | Singapore / Nearest to India |
| **Branch** | `main` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn run:app` |
| **Instance Type** | **Free** |

---

### Step 3: Configure Environment Variables

In Render Dashboard, scroll down to the **Environment Variables** section and add the following keys:

| Key | Example Value | Description |
| :--- | :--- | :--- |
| **`FLASK_APP`** | `run.py` | Entry script |
| **`FLASK_ENV`** | `production` | Production mode |
| **`SECRET_KEY`** | `generate-a-random-secure-string-here` | Session cookie encryption |
| **`DATABASE_URL`** | `postgresql://postgres:pass@db.ref.supabase.co:5432/postgres` | Your Supabase connection URI |
| **`GEMINI_API_KEY`** | `YOUR_GEMINI_API_KEY` | Google Gemini AI Key |
| **`SEED_DEMO`** | `true` | Auto-seeds initial demo items on first deployment |
| **`VOICE_PIPELINE_MODE`** | `ai_first` | Voice parsing strategy |

---

### Step 4: Deploy & Verify

1. Click **Create Web Service**.
2. Render will automatically build the dependencies from `requirements.txt` and start the server using Gunicorn.
3. Once the build log displays `Your service is live 🎉`, click your generated URL (e.g., `https://vyapar-saarthi-ai.onrender.com`).
4. Test **Voice Billing**, **Product Management**, and **Multi-Store Outlets** live online!

---

## 💡 Alternative Options Comparison

| Provider | Pros | Cons | Verdict |
| :--- | :--- | :--- | :--- |
| **Render.com** | Very easy GitHub integration, free SSL, native Python WSGI. | Free tier sleeps after 15m inactivity (wake-up takes ~30s). | 🌟 **Best Overall** |
| **Railway.app** | Extremely fast, zero sleep on paid tier ($5 credit). | Credit card required after free trial. | ⚡ **Best for Zero Sleep** |
| **Vercel** | Super fast global CDN. | Requires converting Flask to serverless functions. | ⚠️ More setup needed |
