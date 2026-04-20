# Deploy Video Hunter to `video.wavelync.com`

Target host: `root@185.229.226.37` (single Ubuntu VM, already running Nginx
with many other sites).

## 1. DNS

Create an A record: `video.wavelync.com` → `185.229.226.37`. Wait for
propagation before running certbot.

## 2. System packages (skip what's already installed)

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip ffmpeg git postgresql
# yt-dlp lives in the app's venv (pip install), so no system install needed.
```

## 3. PostgreSQL

```bash
sudo -u postgres psql <<'SQL'
CREATE USER video_hunter WITH PASSWORD 'STRONG_PASSWORD_HERE';
CREATE DATABASE video_hunter OWNER video_hunter;
SQL
```

Set the same password in `DATABASE_URL` inside `/opt/video_hunter/.env`:

```
DATABASE_URL=postgresql+psycopg2://video_hunter:STRONG_PASSWORD_HERE@127.0.0.1:5432/video_hunter
```

## 4. App directory

```bash
sudo mkdir -p /opt/video_hunter
sudo chown -R $USER:$USER /opt/video_hunter
cp deploy/env.example /opt/video_hunter/.env   # edit secrets
```

Deploy the code (from your dev machine):

```bash
# rsync/tar the repo (excluding node_modules/.venv/.env/data) to the server,
# e.g. via the remote-deploy.sh pattern you use for other projects, then:
export APP_ROOT=/opt/video_hunter
bash /opt/video_hunter/deploy/post-deploy.sh
```

`post-deploy.sh` creates `.venv`, `pip install`s, builds `frontend/dist`,
creates `data/{downloads,thumbs}`, chowns everything to `www-data`, and
restarts the systemd service.

## 5. systemd

```bash
sudo cp deploy/video-hunter.service /etc/systemd/system/video-hunter.service
sudo systemctl daemon-reload
sudo systemctl enable --now video-hunter.service
sudo systemctl status video-hunter.service --no-pager
```

## 6. Nginx + TLS

```bash
sudo cp deploy/nginx-video.wavelync.com.conf /etc/nginx/sites-available/video.wavelync.com
sudo ln -sf /etc/nginx/sites-available/video.wavelync.com /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d video.wavelync.com
```

## 7. First boot

- Browse to `https://video.wavelync.com`.
- Log in with `admin / admin123`.
- Open **Settings** (sidebar), paste the YouTube API key (and FB cookies if
  you plan to search Facebook). Everything is stored in `app_config` in
  Postgres and never echoed back to the browser.
- Create a project, run a search — before the API key is pasted you'll get a
  stub batch of 10 so the flow is testable end-to-end.

## 8. Change the default password

Until the admin user-management UI lands, shell into the server and:
```bash
sudo -u www-data /opt/video_hunter/.venv/bin/python - <<'PY'
from sqlmodel import Session, select
from app.db import engine
from app.auth import hash_password
from app.models import User
with Session(engine) as s:
    u = s.exec(select(User).where(User.username == 'admin')).first()
    u.password_hash = hash_password('YOUR_NEW_PASSWORD')
    s.add(u); s.commit()
print('ok')
PY
```
