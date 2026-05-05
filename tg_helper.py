"""Telegram yardimci - mesaj gonder/sil ve ID takip et."""
import urllib.request, urllib.parse, urllib.error, json, os
from datetime import datetime

import sys as _sys
_sys.path.insert(0, "/opt/jira_rapor")
import config as _cfg
TG_TOKEN = _cfg.TG_TOKEN
TG_CHAT  = _cfg.TG_CHAT
STATE_FILE = "/opt/jira_rapor/tg_messages.json"
LOG_FILE   = "/opt/jira_rapor/telegram.log"

def _log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [tg_helper] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except: pass

def _api(method, **params):
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{TG_TOKEN}/{method}", data=data)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read())
        except:
            return {"ok": False, "description": str(e)}
    except Exception as e:
        return {"ok": False, "description": str(e)}

def _load_ids():
    if not os.path.exists(STATE_FILE):
        return []
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except:
        return []

def _save_ids(ids):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(ids, f)
    except Exception as e:
        _log(f"Kayit hatasi: {e}")

def delete_previous():
    """Onceki tum bot mesajlarini sil."""
    ids = _load_ids()
    if not ids:
        return 0
    deleted = 0
    for mid in ids:
        res = _api("deleteMessage", chat_id=TG_CHAT, message_id=mid)
        if res.get("ok"):
            deleted += 1
    _save_ids([])
    _log(f"{deleted}/{len(ids)} onceki mesaj silindi")
    return deleted

def send(text):
    """HTML mesaj gonder ve ID kaydet."""
    res = _api("sendMessage",
               chat_id=TG_CHAT, text=text,
               parse_mode="HTML",
               disable_web_page_preview="true")
    if res.get("ok"):
        mid = res["result"]["message_id"]
        ids = _load_ids()
        ids.append(mid)
        _save_ids(ids)
        return True
    else:
        _log(f"Gonderim HATASI: {res.get('description', res)}")
        return False
