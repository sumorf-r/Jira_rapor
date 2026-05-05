#!/usr/bin/env python3
"""Aksam 18:00 anlik guncel durum maili.
TO: Talha Bey, CC: Yusuf
"""
import os, glob, smtplib, subprocess, sys
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from datetime import datetime

sys.path.insert(0, "/opt/jira_rapor")
import config as cfg
from send_report import hitap_olustur, log, NAME_OVERRIDES, PROJECT_NAMES

TO = "talhacemil@gundogdugida.com"
CC = ["myusufyanik@gundogdugida.com"]

def main():
    log("=== Aksam guncel durum maili basladi ===")

    result = subprocess.run(
        ["python3", "/opt/jira_rapor/jira_to_excel.py"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        log("HATA: " + result.stderr[:500])
        sys.exit(1)
    log(result.stdout.strip())

    files = sorted(glob.glob(cfg.RAPOR_DIR + "/Digital_Donusum_*.xlsx"))
    if not files:
        log("HATA: Rapor dosyasi bulunamadi")
        sys.exit(1)

    latest = files[-1]
    log("Son rapor: " + latest)

    msg = MIMEMultipart()
    msg["From"]    = cfg.SMTP_NAME + " <" + cfg.SMTP_SENDER + ">"
    msg["To"]      = TO
    msg["Cc"]      = ", ".join(CC)
    msg["Subject"] = "Anlik Guncel Durum | " + datetime.now().strftime("%d.%m.%Y %H:%M")

    now = datetime.now()
    hitap = hitap_olustur(TO)
    kapsam = " & ".join(PROJECT_NAMES) + " Proje Panoları"
    body = (
        hitap + ",\n\n"
        "Gün sonu itibariyle Dijital Dönüşüm projelerinin anlık güncel durum raporu "
        "ekte sunulmaktadır.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "  RAPOR DETAYLARI\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "  Rapor Tarihi  : " + now.strftime("%d.%m.%Y") + "\n"
        "  Rapor Saati   : " + now.strftime("%H:%M") + " (Gün Sonu)\n"
        "  Kapsam        : " + kapsam + "\n"
        "  Dosya Adı     : " + os.path.basename(latest) + "\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Bu rapor; gün içinde tamamlanan, ilerleyen ve geciken görevlerin son halini "
        "gösteren bir gün sonu özetidir.\n\n"
        "Saygılarımla,\n"
        "Gündoğdu Gıda — Dijital Dönüşüm Ekibi\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Bu rapor her akşam 18:00'de otomatik olarak gönderilmektedir.\n"
    )
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with open(latest, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", "attachment; filename=" + os.path.basename(latest))
    msg.attach(part)

    try:
        with smtplib.SMTP(cfg.SMTP_SERVER, cfg.SMTP_PORT, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(cfg.SMTP_USERNAME, cfg.SMTP_PASSWORD)
            smtp.sendmail(cfg.SMTP_SENDER, [TO] + CC, msg.as_string())
        log("Aksam maili gonderildi -> " + TO + " (CC: " + ", ".join(CC) + ")")
    except Exception as e:
        log("E-posta HATASI: " + str(e))
        sys.exit(1)

    log("=== Bitti ===")

if __name__ == "__main__":
    main()
