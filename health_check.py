#!/usr/bin/env python3
"""Sistem saglik kontrolu — Jira API, SMTP, Telegram bot canli mi?

Manuel calistirma: python3 /opt/jira_rapor/health_check.py
Cikti: her servis icin OK / FAIL ve aciklama.
"""
import sys, urllib.request, urllib.parse, urllib.error, base64, json, smtplib, ssl
from datetime import datetime

sys.path.insert(0, "/opt/jira_rapor")
import config as cfg

CHECKS = []

def check(name, ok, detail=""):
    icon = "✓" if ok else "✗"
    line = f"  {icon}  {name:30}  {detail}"
    CHECKS.append((name, ok, detail))
    print(line)

print(f"=== SAGLIK KONTROLU — {datetime.now().strftime('%d.%m.%Y %H:%M:%S')} ===\n")

# 1) Config dosyasi yuklenebiliyor mu (zaten import ile dogrulandi)
check("config.py yuklenmesi", True, "OK")

# 2) Jira API
print("\n[Jira]")
try:
    creds = base64.b64encode(f"{cfg.JIRA_EMAIL}:{cfg.JIRA_TOKEN}".encode()).decode()
    headers = {"Authorization": f"Basic {creds}", "Accept": "application/json"}
    req = urllib.request.Request(f"{cfg.JIRA_BASE}/rest/api/3/myself", headers=headers)
    with urllib.request.urlopen(req, timeout=10) as r:
        d = json.loads(r.read())
    check("Jira /myself",  True, f"user={d.get('emailAddress')}")

    # Her proje icin erisim kontrolu (project endpoint)
    for proj in cfg.PROJECTS:
        try:
            req = urllib.request.Request(f"{cfg.JIRA_BASE}/rest/api/3/project/{proj}", headers=headers)
            with urllib.request.urlopen(req, timeout=10) as r:
                d = json.loads(r.read())
            check(f"Jira proje {proj}", True, f"{d.get('name', '')[:40]}")
        except Exception as e:
            check(f"Jira proje {proj}", False, str(e)[:80])
except Exception as e:
    check("Jira /myself", False, str(e)[:100])

# 3) SMTP
print("\n[SMTP]")
try:
    with smtplib.SMTP(cfg.SMTP_SERVER, cfg.SMTP_PORT, timeout=10) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(cfg.SMTP_USERNAME, cfg.SMTP_PASSWORD)
    check("SMTP login", True, f"{cfg.SMTP_SERVER}:{cfg.SMTP_PORT}")
except Exception as e:
    check("SMTP login", False, str(e)[:100])

# 4) Telegram bot
print("\n[Telegram]")
try:
    req = urllib.request.Request(f"https://api.telegram.org/bot{cfg.TG_TOKEN}/getMe")
    with urllib.request.urlopen(req, timeout=10) as r:
        d = json.loads(r.read())
    if d.get("ok"):
        bot = d["result"]
        check("Bot getMe", True, f"@{bot.get('username')}")
        # Privacy mode warning
        if bot.get("can_read_all_group_messages") is False:
            check("Bot privacy mode", True, "AKTIF (grup mesajlarini okumaz; mention/komut OK)")
    else:
        check("Bot getMe", False, str(d))

    # Chat erisimi
    req = urllib.request.Request(f"https://api.telegram.org/bot{cfg.TG_TOKEN}/getChat?chat_id={cfg.TG_CHAT}")
    with urllib.request.urlopen(req, timeout=10) as r:
        d = json.loads(r.read())
    if d.get("ok"):
        chat = d["result"]
        check("Bot chat erisimi", True, f"{chat.get('title')} (tip={chat.get('type')})")
    else:
        check("Bot chat erisimi", False, str(d))
except Exception as e:
    check("Telegram", False, str(e)[:100])

# 5) Disk / dosya kontrolleri
print("\n[Sistem]")
import os, shutil
total, used, free = shutil.disk_usage("/opt")
gb = lambda b: f"{b//(1024**3)}GB"
check("Disk /opt", free > 1024**3, f"toplam={gb(total)} bos={gb(free)}")
check("/opt/jira_rapor", os.path.isdir("/opt/jira_rapor"), "")
check("/opt/jira_rapor/raporlar", os.path.isdir("/opt/jira_rapor/raporlar"), "")
check("/opt/jira_rapor/yedek", os.path.isdir("/opt/jira_rapor/yedek"), "")
check("config.py chmod", oct(os.stat("/opt/jira_rapor/config.py").st_mode)[-3:] == "600", oct(os.stat("/opt/jira_rapor/config.py").st_mode)[-3:])

# Cron servisi
import subprocess
r = subprocess.run(["systemctl", "is-active", "cron"], capture_output=True, text=True)
check("cron servis", r.stdout.strip() == "active", r.stdout.strip())
r = subprocess.run(["systemctl", "is-active", "fail2ban"], capture_output=True, text=True)
check("fail2ban servis", r.stdout.strip() == "active", r.stdout.strip())

# OZET
print("\n=== OZET ===")
ok = sum(1 for _,o,_ in CHECKS if o)
total = len(CHECKS)
print(f"  {ok}/{total} test gecti")

if ok < total:
    print("\n  HATALAR:")
    for name, o, det in CHECKS:
        if not o:
            print(f"    ✗ {name}: {det}")
    sys.exit(1)
sys.exit(0)
