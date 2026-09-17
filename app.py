import os, secrets, sqlite3
from datetime import datetime, timezone
from functools import wraps
from flask import Flask, jsonify, request, session, redirect, url_for, render_template
import requests

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-this-secret-key")
DB_PATH = os.getenv("DB_PATH", "app.db")
TWELVE_API_KEY = os.getenv("TWELVE_DATA_API_KEY", "")
SYMBOL = os.getenv("SYMBOL", "XAU/USD")
ADMIN_KEY = os.getenv("ADMIN_KEY", "change-admin-key")

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    conn.execute("""CREATE TABLE IF NOT EXISTS codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        active INTEGER DEFAULT 1,
        created_at TEXT NOT NULL
    )""")
    conn.commit()
    conn.close()

def valid_code(code):
    conn = db()
    row = conn.execute("SELECT * FROM codes WHERE code=? AND active=1", (code,)).fetchone()
    conn.close()
    return row is not None

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

def get_candles(interval="5min", outputsize=150):
    if not TWELVE_API_KEY:
        raise RuntimeError("TWELVE_DATA_API_KEY is not configured")
    r = requests.get(
        "https://api.twelvedata.com/time_series",
        params={"symbol": SYMBOL, "interval": interval, "outputsize": outputsize,
                "apikey": TWELVE_API_KEY},
        timeout=15
    )
    r.raise_for_status()
    data = r.json()
    if "values" not in data:
        raise RuntimeError(data.get("message", "Twelve Data returned no candle data"))
    values = list(reversed(data["values"]))
    return [{k: float(v) if k in ("open","high","low","close") else v for k,v in x.items()} for x in values]

def ema(values, period):
    if len(values) < period:
        return None
    k = 2/(period+1)
    e = sum(values[:period])/period
    for v in values[period:]:
        e = v*k + e*(1-k)
    return e

def rsi(values, period=14):
    if len(values) <= period:
        return None
    gains, losses = [], []
    for i in range(1, len(values)):
        d = values[i]-values[i-1]
        gains.append(max(d,0)); losses.append(max(-d,0))
    avg_gain = sum(gains[:period])/period
    avg_loss = sum(losses[:period])/period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain*(period-1)+gains[i])/period
        avg_loss = (avg_loss*(period-1)+losses[i])/period
    if avg_loss == 0: return 100.0
    return 100 - 100/(1 + avg_gain/avg_loss)

def analyze(candles):
    closes = [x["close"] for x in candles]
    price = closes[-1]
    e20, e50, e200 = ema(closes,20), ema(closes,50), ema(closes,200)
    rr = rsi(closes,14)
    score = 0
    if e20 and price > e20: score += 1
    if e50 and price > e50: score += 1
    if e200 and price > e200: score += 1
    if e20 and e50 and e20 > e50: score += 1
    if rr is not None and rr > 50: score += 1
    if score >= 3: side = "BUY"
    elif score <= 2: side = "SELL"
    else: side = "WAIT"

    recent = candles[-20:]
    atr_like = sum(x["high"]-x["low"] for x in recent)/len(recent)
    risk = max(atr_like*1.2, price*0.0008)
    if side == "BUY":
        sl = price-risk
        tps = [price+risk*i for i in (1,2,3,4)]
    elif side == "SELL":
        sl = price+risk
        tps = [price-risk*i for i in (1,2,3,4)]
    else:
        sl = price
        tps = [price]*4

    return {
        "symbol": SYMBOL, "price": price, "signal": side,
        "entry": price, "sl": sl, "tp1": tps[0], "tp2": tps[1],
        "tp3": tps[2], "tp4": tps[3], "rsi14": rr,
        "ema20": e20, "ema50": e50, "ema200": e200,
        "updated": datetime.now(timezone.utc).isoformat()
    }

@app.route("/")
def index():
    if session.get("logged_in"): return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET","POST"])
def login():
    error = None
    if request.method == "POST":
        code = request.form.get("code","").strip()
        if valid_code(code):
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        error = "كود الاشتراك غير صحيح أو غير فعال"
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", symbol=SYMBOL)

@app.route("/api/analysis")
@login_required
def api_analysis():
    try:
        interval = request.args.get("interval", "5min")
        if interval not in {"1min","5min","15min","30min","1h","4h","1day"}:
            return jsonify({"error":"Unsupported interval"}), 400
        return jsonify(analyze(get_candles(interval)))
    except Exception as e:
        return jsonify({"error": str(e)}), 502

@app.route("/admin/create-code", methods=["POST"])
def create_code():
    if request.headers.get("X-Admin-Key") != ADMIN_KEY:
        return jsonify({"error":"Unauthorized"}), 401
    code = secrets.token_urlsafe(9).replace("-","").replace("_","").upper()
    conn = db()
    conn.execute("INSERT INTO codes(code,active,created_at) VALUES(?,?,?)",
                 (code,1,datetime.now(timezone.utc).isoformat()))
    conn.commit(); conn.close()
    return jsonify({"code":code})

@app.route("/admin/codes")
def list_codes():
    if request.headers.get("X-Admin-Key") != ADMIN_KEY:
        return jsonify({"error":"Unauthorized"}), 401
    conn=db()
    rows=conn.execute("SELECT id,code,active,created_at FROM codes ORDER BY id DESC").fetchall()
    conn.close()
    return jsonify([dict(x) for x in rows])

@app.route("/health")
def health():
    return jsonify({"status":"ok"})

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT","10000")))
