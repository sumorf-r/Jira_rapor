#!/usr/bin/env python3
"""Cron job wrapper — calistirir, exit code != 0 ise Telegram'a alert gonderir.

Kullanim:
  python3 /opt/jira_rapor/cron_runner.py <log_dosyasi> <script_yolu>

Ornek:
  python3 /opt/jira_rapor/cron_runner.py cron_send.log /opt/jira_rapor/send_report.py
"""
import sys, os, subprocess, urllib.request, urllib.parse, urllib.error, json
from datetime import datetime

sys.path.insert(0, "/opt/jira_rapor")
import config as _cfg

LOG_DIR = "/opt/jira_rapor"

def alert(script_name, exit_code, tail_output):
    """Hata durumunda Telegram'a kisa bilgi at."""
    try:
        text = (
            f"⚠️ <b>CRON HATASI</b>\n"
            f"Script: <code>{script_name}</code>\n"
            f"Cikis kodu: <b>{exit_code}</b>\n"
            f"Saat: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n\n"
            f"<i>Son ciktilar:</i>\n<pre>{tail_output[-1500:]}</pre>"
        )
        data = urllib.parse.urlencode({
            "chat_id": _cfg.TG_CHAT,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }).encode()
        req = urllib.request.Request(f"https://api.telegram.org/bot{_cfg.TG_TOKEN}/sendMessage", data=data)
        urllib.request.urlopen(req, timeout=15)
    except Exception:
        pass  # Alert basarisiz olursa sessizce devam et (sonsuz dongu olmasin)

def main():
    if len(sys.argv) < 3:
        print("Kullanim: cron_runner.py <log_dosyasi> <script_yolu> [arg...]")
        sys.exit(2)

    log_file = os.path.join(LOG_DIR, sys.argv[1])
    script   = sys.argv[2]
    args     = sys.argv[3:]

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = f"\n[{ts}] >>> {os.path.basename(script)} basliyor\n"

    # Calistir, ciktiyi log'a yaz
    with open(log_file, "a") as lf:
        lf.write(header)
        lf.flush()
        proc = subprocess.run(
            ["python3", script] + args,
            capture_output=True, text=True
        )
        lf.write(proc.stdout)
        if proc.stderr:
            lf.write("\n[STDERR]\n" + proc.stderr)
        ts_end = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lf.write(f"\n[{ts_end}] <<< exit={proc.returncode}\n")

    # Hata varsa alert gonder
    if proc.returncode != 0:
        tail = (proc.stdout + "\n" + proc.stderr).strip()
        # HTML escape
        tail = tail.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        alert(os.path.basename(script), proc.returncode, tail)

    sys.exit(proc.returncode)

if __name__ == "__main__":
    main()
