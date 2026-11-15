# ⚡ No Brain Stickman - Next.js Control Panel

A production-ready **Next.js (App Router, TypeScript)** control panel for reviewing, editing, approving, and scheduling automated stick-figure mystery Shorts.

Deploys on the **Vercel Free Tier** with **Root Directory = `web`**.

---

## 🚀 Local Development

1. **Navigate into the web directory**:
   ```bash
   cd web
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

3. **Configure local environment**:
   Copy `.env.example` to `.env.local`:
   ```bash
   cp .env.example .env.local
   ```
   Fill in your `SUPABASE_URL`, `SUPABASE_KEY`, `PANEL_PASSWORD`, and `SESSION_SECRET`.

4. **Start the development server**:
   ```bash
   npm run dev
   ```
   Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## ☁️ Vercel Deployment Guide

### 1. Project Import Settings
When importing this repository into Vercel:
- **Framework Preset**: `Next.js`
- **Root Directory**: `web` (Click "Edit" and choose `web`)
- **Build Command**: `npm run build` (default)
- **Output Directory**: `.next` (default)

### 2. Environment Variables in Vercel
Go to **Project Settings > Environment Variables** and add:

| Variable | Description | Example / Note |
|---|---|---|
| `PANEL_PASSWORD` | Password for single-user authentication | e.g. `MySuperSecretPassword2026!` |
| `SESSION_SECRET` | 32+ character random secret for signing session cookies | e.g. `9f8e7d6c5b4a3928170e1f2a3b4c5d6e` |
| `SUPABASE_URL` | Your Supabase project URL | `https://xxxx.supabase.co` |
| `SUPABASE_KEY` | Server-side service_role (or anon) key | `eyJh...` (Never prefixed with `NEXT_PUBLIC_`) |
| `SUPABASE_BUCKET` | Storage bucket for video assets | `shorts` |
| `GITHUB_TOKEN` | GitHub Fine-Grained Personal Access Token | Actions: Read & Write |
| `GITHUB_REPO` | Target GitHub repository | `Ashtosh009/YTAutomation` |

> 🔒 **Security Notice**: None of these keys are exposed to the client. All Supabase calls and GitHub dispatches run server-side in Route Handlers.

---

## 🔑 Changing the Panel Password
To change the password:
1. In Vercel, go to **Settings > Environment Variables**.
2. Edit `PANEL_PASSWORD` to your new password.
3. Redeploy your latest deployment under the **Deployments** tab (or run a new commit).

---

## 🌐 Public OAuth Pages (Google Consent Screen)
The following routes are public and bypass authentication:
- `/about`: Public channel summary for Google OAuth app verification.
- `/privacy`: Plain-English privacy policy stating data is only uploaded to the owner's channel.
