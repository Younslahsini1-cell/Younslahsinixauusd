from flask import Flask, jsonify
from flask_cors import CORS
import requests, time, threading, os
import pandas as pd
import numpy as np

app=Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

# Independent market-data version.
# Uses Twelve Data REST API. Put your API key in TWELVE_DATA_API_KEY.
API_KEY=os.getenv("TWELVE_DATA_API_KEY","")
BASE="https://api.twelvedata.com/time_series"
SYMBOLS=["XAU/USD","EUR/USD"]

# In-memory journal; replace with SQLite later if persistent history is needed.
JOURNAL=[]
LAST_ALERT={}

NTFY_TOPIC=os.getenv("NTFY_TOPIC","")
NTFY_URL=f"https://ntfy.sh/{NTFY_TOPIC}" if NTFY_TOPIC else ""

def send_telegram(d):
    if not NTFY_TOPIC:
        return False
    title=f"{d['symbol']} — {d['signal']}"
    msg=(f"Entry: {d['entry']}\n"
         f"SL: {d['sl']}\n"
         f"TP: {d['tp']}\n"
         f"H4: {d['h4']} | H1: {d['h1']} | M15: {d['m15']}\n"
         f"ATR(20): {d['atr']}\n"
         f"{d['timestamp']}")
    r=requests.post(
        NTFY_URL,
        data=msg.encode("utf-8"),
        headers={
            "Title": title.encode("ascii","ignore"),
            "Priority":"high",
            "Tags":"rotating_light"
        },
        timeout=10
    )
    return r.ok

def fetch(symbol, interval, outputsize=240):
    if not API_KEY:
        raise RuntimeError("TWELVE_DATA_API_KEY is not configured")
    r=requests.get(BASE,params={
        "symbol":symbol,"interval":interval,"outputsize":outputsize,
        "apikey":API_KEY,"format":"JSON"
    },timeout=15)
    r.raise_for_status()
    j=r.json()
    if "values" not in j:
        raise RuntimeError(j.get("message","Market data error"))
    df=pd.DataFrame(j["values"])
    for c in ["open","high","low","close"]:
        df[c]=pd.to_numeric(df[c],errors="coerce")
    df=df.sort_values("datetime").reset_index(drop=True)
    return df

def ema(s,n): return s.ewm(span=n,adjust=False).mean()

def atr(df,n=20):
    pc=df.close.shift(1)
    tr=pd.concat([(df.high-df.low),(df.high-pc).abs(),(df.low-pc).abs()],axis=1).max(axis=1)
    return tr.rolling(n).mean()

def analyze(symbol):
    h4=fetch(symbol,"4h")
    h1=fetch(symbol,"1h")
    m15=fetch(symbol,"15min")

    def trend(df):
        return "BUY" if ema(df.close,50).iloc[-1] > ema(df.close,200).iloc[-1] else "SELL"

    h4t,h1t=trend(h4),trend(h1)

    # Last row is treated as current/incomplete; decision uses the last CLOSED row.
    c=m15.iloc[-2]
    prior=m15.iloc[:-2]
    don_high=prior.high.tail(20).max()
    don_low=prior.low.tail(20).min()
    momentum=c.close-m15.close.iloc[-32]
    trigger="BUY" if c.close>don_high and momentum>0 else ("SELL" if c.close<don_low and momentum<0 else "WAIT")

    signal="BUY" if h4t=="BUY" and h1t=="BUY" and trigger=="BUY" else (
            "SELL" if h4t=="SELL" and h1t=="SELL" and trigger=="SELL" else "WAIT")

    a=float(atr(m15,20).iloc[-2])
    entry=float(c.close)
    mult=1.5; rr=2.0
    sl=entry-a*mult if signal=="BUY" else entry+a*mult
    tp=entry+a*mult*rr if signal=="BUY" else entry-a*mult*rr

    return {
      "symbol":symbol,"signal":signal,"h4":h4t,"h1":h1t,"m15":trigger,
      "entry":entry,"sl":float(sl),"tp":float(tp),"atr":a,
      "timestamp":str(c.datetime),"source":"Twelve Data",
      "rule":"H4 + H1 trend, M15 Donchian/Momentum, last closed candle"
    }

def scan_all():
    results=[]
    for s in SYMBOLS:
        try:
            d=analyze(s); results.append(d)
            key=(s,d["signal"],d["timestamp"])
            if d["signal"] in ("BUY","SELL") and LAST_ALERT.get(s)!=key:
                LAST_ALERT[s]=key
                JOURNAL.insert(0,d)
                del JOURNAL[30:]
                try:
                    send_telegram(d)
                except Exception:
                    pass
        except Exception as e:
            results.append({"symbol":s,"signal":"WAIT","error":str(e)})
    return results

@app.get("/")
def home():
    return app.send_static_file('index.html')

@app.get("/api/health")
def health():
    return jsonify({"ok":bool(API_KEY),"provider":"Twelve Data","ntfy_configured":bool(NTFY_TOPIC),"symbols":SYMBOLS})

@app.get("/api/signals")
def signals():
    return jsonify(scan_all())

@app.get("/api/signal/<path:symbol>")
def signal(symbol):
    return jsonify(analyze(symbol.upper().replace("-","/")))

@app.get("/api/journal")
def journal():
    return jsonify(JOURNAL)

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.getenv("PORT","8000")))
