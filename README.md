# Jira Otomasyonu — Gündoğdu Gıda Dijital Dönüşüm

Jira projelerinden günlük Excel raporları oluşturup mail gönderir, Telegram grubuna görev hatırlatmaları atar.

## Bileşenler

| Dosya | Amaç |
|------|------|
| `jira_to_excel.py` | Jira'dan veri çeker, çok sayfalı Excel raporu üretir (Ana Sayfa, Yol Haritası, proje panoları) |
| `send_report.py` | Sabah 08:00 raporunu mail eder |
| `send_status.py` | Akşam 18:00 anlık güncel durum maili |
| `telegram_notify.py` | 08:05 / 17:30 Telegram toplu özet |
| `telegram_nag.py` | 09:00–17:00 saatlik tek tek görev hatırlatma ("uyuz müdür") |
| `tg_helper.py` | Telegram mesaj gönder/sil yardımcı modülü |
| `cron_runner.py` | Cron job wrapper — exit kod ≠ 0 ise Telegram'a alert |
| `health_check.py` | Jira/SMTP/Telegram/Disk/Cron kontrol scripti |
| `config.py` | **Sirlar** (token, şifre) — repo'ya commit edilmez |
| `config.example.py` | Sablonlu örnek config |

## Kurulum

```bash
# Bağımlılıklar
apt-get install -y python3-pip fail2ban
pip install openpyxl paramiko --break-system-packages

# Dizin
mkdir -p /opt/jira_rapor/{raporlar,yedek}
cd /opt/jira_rapor

# Tüm .py dosyalarını kopyala, sonra:
cp config.example.py config.py
chmod 600 config.py
# config.py içindeki sirlari kendi degerlerinle doldur
```

## Cron çizelgesi

```cron
# Sabah e-posta raporu
0 8 * * * python3 /opt/jira_rapor/cron_runner.py cron_send.log /opt/jira_rapor/send_report.py
# Aksam anlik guncel durum
0 18 * * * python3 /opt/jira_rapor/cron_runner.py cron_status.log /opt/jira_rapor/send_status.py
# Sabah toplu Telegram ozet
5 8 * * 1-5 python3 /opt/jira_rapor/cron_runner.py cron_notify.log /opt/jira_rapor/telegram_notify.py
# Aksam toplu Telegram ozet
30 17 * * 1-5 python3 /opt/jira_rapor/cron_runner.py cron_notify.log /opt/jira_rapor/telegram_notify.py
# Saatlik nag
0 9-17 * * 1-5 python3 /opt/jira_rapor/cron_runner.py cron_nag.log /opt/jira_rapor/telegram_nag.py
# Haftalik yedek temizligi
0 2 * * 0 find /opt/jira_rapor/yedek -type f -mtime +30 -delete
```

## Özellikler

- **Otomatik tespit**: Tamamlandı (statusCategory bazlı), Erken bitirme, Geciken (Tip 1: bitiş geçmiş, Tip 2: başlangıç gecikmiş)
- **Çoklu proje**: RPA, GNDFAB, GNDERP, ODOO (config'den dinamik)
- **Cron alert**: Hata olursa Telegram grubuna otomatik bildirim
- **Yedekleme**: Her değişikten sonra otomatik yedek (`yedek/`)
- **Sağlık kontrolü**: `python3 health_check.py`

## Saglik Kontrolu

```bash
python3 /opt/jira_rapor/health_check.py
```

Çıktı: Jira API, SMTP, Telegram bot, disk, cron, fail2ban kontrolü (✓/✗).
