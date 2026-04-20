# Video Hunter

Search YouTube and Facebook for videos on a given subject, review candidates in
a grid, keep the ones you want, discard the rest — then paginate to the next
batch.

## Stack

| Layer | Tool |
|---|---|
| Frontend | React 18 + TypeScript + Vite + Tailwind + AG Grid Community |
| Backend  | FastAPI (Python 3.11) + SQLModel |
| DB       | PostgreSQL |
| Proxy    | Nginx (TLS via Let's Encrypt) |
| Service  | systemd |
| Downloads | `yt-dlp` |

## Product flow

1. **Log in** (default `admin` / `admin123` — change after first boot).
2. **Projects** — create or pick a project. A project can't search until it
   exists.
3. **Hunt** — type a subject, pick a provider (YouTube or Facebook), click
   Search. The backend fetches 10 results, starts a background `yt-dlp`
   download for each, and shows them in an AG Grid.
4. For each row: click **Keep** (survives pagination) or **Reject** (server
   deletes the row + file on the next page). Or click **Download** to stream
   the file to the browser.
5. **Next 10** — purges every candidate from the current batch that isn't
   marked Keep (DB row + mp4 on disk), fetches the next page.

## Provider credentials

Pasted into the Settings page and stored in the `app_config` table. Keys are
write-only through the API — they are never echoed back to the browser.

- **YouTube Data API v3 key** — from
  [Google Cloud Console](https://console.cloud.google.com/apis/credentials).
  When empty, the backend returns 10 fabricated results per page so the UI +
  pagination are testable before a real key is pasted.
- **Facebook session cookies** — paste the raw `Cookie` header from a
  logged-in facebook.com tab. Fragile by nature; re-paste whenever Facebook
  layout changes break the scraper or the session expires.

## Local development

Backend:
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# edit .env (copy from .env.example) — set DATABASE_URL to your local Postgres
uvicorn app.main:app --host 127.0.0.1 --port 8030 --reload
```

Frontend:
```bash
cd frontend
npm install
# edit .env.local with VITE_API_BASE_URL=http://127.0.0.1:8030 (optional)
npm run dev    # http://localhost:5174
```

First boot seeds `admin` / `admin123`. Change the password via DB directly
until the admin user-management UI lands.

## Deploy

See `deploy/README.md`. Target is a single Ubuntu host at
`video.wavelync.com` with Postgres + Nginx + systemd. One-shot:
```bash
./deploy/remote-deploy.sh root@video.wavelync.com /opt/video_hunter
```
