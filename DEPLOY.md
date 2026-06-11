# Deployment guide

Three pieces to host: **Postgres**, the **two FastAPI services**, and the **React app**.
Free tiers everywhere. ~20 minutes end to end.

> Pick one shared `WEBHOOK_SECRET` (any long random string) and use the *same* value on both
> backend services.

## 1. Database — Neon (or Render Postgres)
1. Create a free Postgres at https://neon.tech → copy the connection string.
   (The CRM auto-rewrites `postgres://` → `postgresql+asyncpg://`, so paste it as-is.)

## 2. Backend services — Render
Easiest path uses the included [`render.yaml`](render.yaml) blueprint:
1. Push this repo to GitHub.
2. Render → **New → Blueprint** → pick the repo. It creates `reach-crm` + `reach-channel`
   (and a Postgres if you didn't make one on Neon).
3. Set env vars when prompted:
   - **Both services:** `WEBHOOK_SECRET` = your shared secret.
   - **reach-crm:** `DATABASE_URL` (Neon string, or auto-wired if using Render's DB), and an
     LLM provider + key: `LLM_PROVIDER=groq` + `GROQ_API_KEY` (free at
     https://console.groq.com/keys), **or** `LLM_PROVIDER=gemini` + `GEMINI_API_KEY`.
4. After both are live, set on **reach-crm** and redeploy:
   - `CHANNEL_SERVICE_URL = https://reach-channel.onrender.com`
   - `CRM_PUBLIC_URL      = https://reach-crm.onrender.com`
5. Seed once: Render → reach-crm → **Shell** → `python -m app.seed`.

> Render free web services sleep when idle; the first request after a nap takes ~30s to wake.
> Hit the CRM URL once before demoing.

## 3. Frontend — Vercel
1. Vercel → **New Project** → import the repo → set **Root Directory** to `web`.
2. Env var: `VITE_API_BASE = https://reach-crm.onrender.com`.
3. Deploy. (Framework preset: Vite. Build `npm run build`, output `dist`.)
4. Add the Vercel URL to the CRM's `CORS_ORIGINS` (or leave `*` for the demo) and redeploy CRM.

## 4. Smoke test
1. Open the Vercel URL → **AI Copilot** → "win back lapsed lipstick buyers" → **Approve & Launch**.
2. Watch the campaign funnel fill. If callbacks don't arrive, re-check that `CRM_PUBLIC_URL` is
   the CRM's public URL and `WEBHOOK_SECRET` matches on both services.

Fill the live URLs into the top of [`README.md`](README.md) when done.
