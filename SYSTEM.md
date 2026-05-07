# Jira Otomasyon Sistemi — Tam Dokümantasyon

**Gündoğdu Gıda — Dijital Dönüşüm Ekibi**

Bu dokümantasyon, Jira'dan veri çeken, Excel raporu üreten, e-posta gönderen, Telegram bildirimleri yapan ve real-time webhook ile anlık olay bildirimi sağlayan tam otomatik sistemin tüm bileşenlerini açıklar.

---

## İçindekiler

1. [Mimari Genel Bakış](#mimari-genel-bakış)
2. [Bileşenler](#bileşenler)
3. [Veri Akışı](#veri-akışı)
4. [Cron Çizelgesi](#cron-çizelgesi)
5. [Servisler (systemd)](#servisler-systemd)
6. [Kurulum (Sıfırdan)](#kurulum-sıfırdan)
7. [Konfigürasyon (`config.py`)](#konfigürasyon-configpy)
8. [Sağlık Kontrolü](#sağlık-kontrolü)
9. [Doğrulama (Verify)](#doğrulama-verify)
10. [Yedekleme & Geri Yükleme](#yedekleme--geri-yükleme)
11. [Sorun Giderme](#sorun-giderme)
12. [Güvenlik Notları](#güvenlik-notları)

---

## Mimari Genel Bakış

```
                 ┌──────────────────────────────────────────────────┐
                 │              JIRA CLOUD                          │
                 │      (gundogdugida-team-tfx1b7cu)                │
                 └────────────────┬─────────────────────────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────────┐
        │ Pull (REST API)         │ Push (Webhook HTTPS)        │
        ▼                         ▼                             │
  ┌──────────┐         ┌──────────────────┐                     │
  │ jira_to_ │         │ Caddy (port 443) │                     │
  │ excel    │         │   ↓ reverse      │                     │
  └────┬─────┘         │   proxy          │                     │
       │               └────────┬─────────┘                     │
       │                        ▼                               │
       │               ┌──────────────────┐                     │
       │               │ jira_webhook.py  │                     │
       │               │ (Flask :8089)    │                     │
       │               └────────┬─────────┘                     │
       │                        │                               │
       ├────────────────────────┼─────────────┐                 │
       ▼                        ▼             ▼                 │
  ┌─────────┐            ┌────────────┐  ┌──────────────┐       │
  │ Excel   │            │ Telegram   │  │ telegram_    │       │
  │ rapor   │            │ Bot API    │  │ visual.py    │       │
  └────┬────┘            └────┬───────┘  └──────┬───────┘       │
       │                      │                 │               │
       ▼                      ▼                 ▼               │
  ┌─────────┐         ┌──────────────────────────────┐          │
  │ SMTP    │         │      Telegram Grup            │          │
  │ Mail    │         │  (gnd dijital donusum)        │          │
  └─────────┘         └──────────────────────────────┘          │
                                                                 │
  Tüm scriptler ────────────────────────────────────────────────►
  config.py'den okur (sırlar tek yerde, chmod 600)
```

---

## Bileşenler

### Veri Çekme & Rapor Üretimi

| Dosya | Rolü |
|-------|------|
| **`config.py`** | Tüm sırlar (Jira token, SMTP password, Telegram token), proje listesi, mail alıcıları. **Git'te değil**, chmod 600. Şablon: `config.example.py`. |
| **`jira_to_excel.py`** | Jira'dan tüm projeleri (paginated) çek, çoklu sayfa Excel üret: Ana Sayfa + Yol Haritası + her proje için Pano + Özet sayfaları. |
| **`verify_report.py`** | Jira'dan tüm issue'ları JSON'a dump et + en son Excel'i oku + karşılaştır → eksik/fazla satır, durum farkı, tarih farkı raporu. |

### E-posta

| Dosya | Cron | Hedef | Rolü |
|-------|------|-------|------|
| **`send_report.py`** | 08:00 her gün | 7 personel + CC | Sabah HTML formatlı rapor maili (Excel ekte) |
| **`send_status.py`** | 18:00 her gün | Talha Bey + CC | Akşam gün sonu status maili |

### Telegram

| Dosya | Cron | Rolü |
|-------|------|------|
| **`telegram_notify.py`** | 08:05 + 17:30 (hafta içi) | Toplu metin özet — geciken/bugün/yarın/3gün kategorize |
| **`telegram_visual.py`** | 09:30 + 13:30 + 16:30 (hafta içi) | matplotlib ile dashboard PNG üret + Telegram'a sendPhoto |
| **`jira_webhook.py`** | systemd (sürekli açık) | Real-time webhook receiver — Jira event → Telegram anlık mesaj |
| **`tg_helper.py`** | (modül) | Mesaj gönder/sil + state JSON yardımcısı (notify kullanır) |

### Cron / Sistem

| Dosya | Rolü |
|-------|------|
| **`cron_runner.py`** | Cron job wrapper — bir scripti çalıştır, exit code != 0 ise Telegram'a alert at. Tüm cron scriptleri bunun içinde sarılır. |
| **`health_check.py`** | 17 noktayı kontrol: Jira API, SMTP, Telegram bot, disk, dizinler, cron, fail2ban. Manuel: `python3 health_check.py`. |
| **`duckdns_update.sh`** | DuckDNS dynamic DNS auto-update (her 5 dk cron). VPS IP'si değişirse domain otomatik güncellenir. |

### Webhook Altyapısı

| Bileşen | Rolü |
|---------|------|
| **Caddy** | Port 80/443 reverse proxy. Otomatik Let's Encrypt SSL (60 günde bir auto-renew). `gnd-jira.duckdns.org` → `localhost:8089`'a iletir. |
| **systemd:`jira-webhook.service`** | Flask uygulamasını her zaman ayakta tutar (restart on failure). |
| **systemd:`caddy.service`** | Caddy'yi her zaman ayakta tutar. |
| **DuckDNS** | Bedava dynamic DNS provider (`gnd-jira.duckdns.org`). Token ile IP güncellemesi yapılır. |

### Arşivlenmiş (eskiden vardı, artık yok)

| Dosya | Niye kaldırıldı |
|-------|----------------|
| `telegram_nag.py` | Saatlik 15 mesaj spam'di. Real-time webhook devreye girince gereksiz oldu. `arsiv/telegram_nag.py.disabled_*` |
| `cloudflared.service` | Quick tunnel URL restart'ta değişiyordu. DuckDNS + Caddy ile değişti. Disabled. |

---

## Veri Akışı

### Sabah (08:00 — 10:00)

```
08:00  cron → send_report.py
       └→ jira_to_excel.py'i subprocess olarak çağır
          └→ Jira REST API'den 4 projeyi çek (paginated)
          └→ Excel oluştur: /opt/jira_rapor/raporlar/Digital_Donusum_DD.MM.YYYY.xlsx
          └→ HTML mail body üret + Excel ekte gönder
       └→ SMTP (exch.gundogdugida.com:587) ile 7 personel + CC

08:05  cron → telegram_notify.py
       └→ Jira'dan aktif görevleri çek (≤3 gün)
       └→ tg_helper.delete_previous() (bir önceki batch'i sil)
       └→ Kategori bazlı 3-4 mesaj gönder (overdue/today/tomorrow/3days)
       └→ Mesaj ID'lerini tg_messages.json'a kaydet

09:30  cron → telegram_visual.py
       └→ Jira'dan istatistik çek (proje × durum)
       └→ matplotlib ile multi-panel PNG üret (header + KPI + 4 donut + bar + acil liste)
       └→ Telegram sendPhoto → grup
```

### Gün Boyu (sürekli)

```
Jira'da X kullanıcı bir görevin durumunu değiştirir
       │
       ▼
Jira webhook tetiklenir → POST https://gnd-jira.duckdns.org/jira-webhook
       │
       ▼
DuckDNS DNS → 194.146.47.182 (VPS)
       │
       ▼
Caddy (port 443) → Let's Encrypt SSL terminate
       │
       ▼ (lokal HTTP)
Flask :8089 → /jira-webhook endpoint
       │
       ▼
jira_webhook.py:
  - Payload parse
  - Event tipini belirle (jira:issue_updated)
  - changelog.items[] içinden field'ı çek (status, duedate, assignee, ...)
  - Alt görev mi ana görev mi tespit et
  - HTML formatında Telegram mesajı kur
  - Telegram Bot API → grup
       │
       ▼
~5-10 saniyede grupta:
  ✅ Durum degisikligi
  GNDFAB-101  ↳ alt gorev (GNDFAB-100)
  Devam Ediyor → Tamam
```

### Öğle / Akşam

```
13:30  telegram_visual.py (öğle dashboard)
16:30  telegram_visual.py (akşam dashboard)
17:30  telegram_notify.py (akşam toplu özet, eski silinir)
18:00  send_status.py (Talha Bey'e gün sonu durum maili)
```

### Pasif Cron'lar

```
*/5 * * * *  duckdns_update.sh (DuckDNS IP güncelleme)
0 2 * * 0    find /opt/jira_rapor/yedek -type f -mtime +30 -delete (haftalık temizlik)
```

---

## Cron Çizelgesi

```cron
# Sabah e-posta raporu (Talha Bey + CC)
0 8 * * * python3 /opt/jira_rapor/cron_runner.py cron_send.log /opt/jira_rapor/send_report.py

# Aksam anlik guncel durum (Talha Bey, CC: Yusuf)
0 18 * * * python3 /opt/jira_rapor/cron_runner.py cron_status.log /opt/jira_rapor/send_status.py

# Sabah toplu Telegram ozet
5 8 * * 1-5 python3 /opt/jira_rapor/cron_runner.py cron_notify.log /opt/jira_rapor/telegram_notify.py

# Aksam toplu Telegram ozet
30 17 * * 1-5 python3 /opt/jira_rapor/cron_runner.py cron_notify.log /opt/jira_rapor/telegram_notify.py

# Telegram gorsel dashboard (gunde 3 kere)
30 9 * * 1-5 python3 /opt/jira_rapor/cron_runner.py cron_visual.log /opt/jira_rapor/telegram_visual.py
30 13 * * 1-5 python3 /opt/jira_rapor/cron_runner.py cron_visual.log /opt/jira_rapor/telegram_visual.py
30 16 * * 1-5 python3 /opt/jira_rapor/cron_runner.py cron_visual.log /opt/jira_rapor/telegram_visual.py

# Haftalik yedek temizligi (30 gunden eski yedekleri sil)
0 2 * * 0 find /opt/jira_rapor/yedek -type f -mtime +30 -delete

# DuckDNS IP auto-update (her 5 dk)
*/5 * * * * /opt/jira_rapor/duckdns_update.sh
```

---

## Servisler (systemd)

### `jira-webhook.service`

```ini
[Unit]
Description=Jira Webhook Receiver (Flask)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/jira_rapor
ExecStart=/usr/bin/python3 /opt/jira_rapor/jira_webhook.py
Restart=always
RestartSec=5
StandardOutput=append:/opt/jira_rapor/jira_webhook_stdout.log
StandardError=append:/opt/jira_rapor/jira_webhook_stderr.log

[Install]
WantedBy=multi-user.target
```

### `caddy.service`

Caddy paketi ile birlikte gelir. Konfigürasyon: `/etc/caddy/Caddyfile`:

```caddy
gnd-jira.duckdns.org {
    log {
        output file /var/log/caddy/access.log
        format json
    }
    reverse_proxy 127.0.0.1:8089
}
```

### Komutlar

```bash
# Servisleri yönet
systemctl status jira-webhook.service caddy
systemctl restart jira-webhook.service
systemctl restart caddy

# Logları izle
journalctl -u jira-webhook.service -f
tail -f /opt/jira_rapor/jira_webhook.log
tail -f /var/log/caddy/access.log
```

---

## Kurulum (Sıfırdan)

### 1) Gereksinimler

```bash
apt-get update
apt-get install -y python3 python3-pip fail2ban curl gnupg fonts-dejavu fonts-liberation
pip install openpyxl paramiko matplotlib pillow flask --break-system-packages
```

### 2) Dizin yapısı

```bash
mkdir -p /opt/jira_rapor/{raporlar,yedek,arsiv}
cd /opt/jira_rapor
# Tum .py dosyalarini buraya kopyala
chmod +x duckdns_update.sh
```

### 3) `config.py` oluştur

```bash
cp config.example.py config.py
chmod 600 config.py
nano config.py  # gercek sirlari doldur
```

`config.py` içinde doldurulacak alanlar:
- `JIRA_TOKEN`, `JIRA_EMAIL`, `JIRA_BASE`
- `SMTP_*` (server, port, sender, name, username, password)
- `TG_TOKEN`, `TG_CHAT`
- `MAIL_TO`, `MAIL_CC`
- `PROJECTS` (proje kodları listesi)
- `PROJECT_THEMES` (her proje için tüm renkler)
- `JIRA_START_DATE_FIELD` (genelde `customfield_10015`)
- `PROGRESS_WINDOW_PANO` (varsayılan 30), `PROGRESS_WINDOW_ROADMAP` (varsayılan 60)
- `JIRA_WEBHOOK_SECRET` (opsiyonel ama prod'da öneriyor)

### 4) Crontab kur

```bash
crontab -e
# Yukarıdaki "Cron Çizelgesi" bölümündeki tüm satırları yapıştır
```

### 5) Webhook (Real-time) Kurulumu

#### a) Caddy kur

```bash
apt-get install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
apt-get update && apt-get install -y caddy
```

#### b) DuckDNS kayıt

1. https://www.duckdns.org → Google ile giriş
2. Subdomain ekle (örn `gnd-jira`)
3. "current ip" alanına VPS IP'sini yaz, "update ip"
4. Sayfanın üstündeki `token` UUID'sini al

#### c) `duckdns_update.sh` doldur

```bash
nano /opt/jira_rapor/duckdns_update.sh
# DOMAIN="gnd-jira"
# TOKEN="senin-token-uuid"
chmod +x duckdns_update.sh
./duckdns_update.sh  # test
```

#### d) Caddyfile

```bash
nano /etc/caddy/Caddyfile
```

```caddy
your-subdomain.duckdns.org {
    log {
        output file /var/log/caddy/access.log
        format json
    }
    reverse_proxy 127.0.0.1:8089
}
```

```bash
mkdir -p /var/log/caddy
systemctl enable caddy
systemctl restart caddy
```

#### e) systemd webhook servisi

`/etc/systemd/system/jira-webhook.service` dosyasını yukarıdaki içerikle oluştur:

```bash
systemctl daemon-reload
systemctl enable jira-webhook.service
systemctl start jira-webhook.service
```

#### f) Test

```bash
curl https://your-subdomain.duckdns.org/health
# Beklenen: OK
```

#### g) Jira'da Webhook Tanımla

1. Jira admin → Settings → System → WebHooks
2. Create a WebHook:
   - Name: `Telegram Realtime`
   - Status: Enabled
   - URL: `https://your-subdomain.duckdns.org/jira-webhook?token=<JIRA_WEBHOOK_SECRET>` (token opsiyonel)
   - Events: Issue (created, updated, deleted) + Comment (created)
   - Exclude body: ❌ kapalı bırak
3. Save

---

## Konfigürasyon (`config.py`)

Tüm sırlar ve sabit değerler tek yerde. **Git'e commit edilmez** (`.gitignore`'da). Şablon: `config.example.py`.

### Önemli Bölümler

```python
# Jira projeleri (örn 4 proje)
PROJECTS = ["RPA", "GNDFAB", "GNDERP", "ODOO"]

# Her proje için TÜM renkler tek dict'te. Yeni proje eklerken:
# 1) PROJECTS listesine ekle
# 2) PROJECT_THEMES'e bir entry ekle
# Kod hiçbir yerde değişmesin
PROJECT_THEMES = {
    "RPA": {
        "label":            "RPA  —  Robotic Process Automation",
        "sheet_color":      "1F4E79",   # Pano sheet header
        "card_accent":      "1B3A6B",   # Ana Sayfa kart aksan
        "card_btn":         "2E75B6",   # "Panoya Git" butonu
        "card_stat_bg":     "EBF2FA",   # Stat satırı arka plan
        "card_stat_border": "C5D8F0",   # Ayraç
        "badge_color":      "1B3A6B",   # Yol Haritası rozet yazı
        "badge_bg":         "D6E4F0",   # Yol Haritası rozet bg
    },
    # ... diğer projeler
}

# İlerleme cubuğu pencereleri (gün)
PROGRESS_WINDOW_PANO    = 30  # Pano sheet'leri
PROGRESS_WINDOW_ROADMAP = 60  # Yol Haritası

# Jira start date custom field ID
JIRA_START_DATE_FIELD = "customfield_10015"
```

---

## Sağlık Kontrolü

```bash
python3 /opt/jira_rapor/health_check.py
```

17 noktayı kontrol eder:
- Config dosyası yüklenebiliyor mu
- Jira `/myself` çağrısı (auth)
- 4 proje erişimi (PROJECTS listesindeki her biri)
- SMTP login
- Telegram bot `getMe` + chat erişimi + privacy mode
- Disk boş alan
- Dizin yapısı
- Config chmod 600
- Cron servisi aktif
- fail2ban servisi aktif

Çıktı: `✓ 17/17 test gecti` veya hangi adımın başarısız olduğunu gösterir.

---

## Doğrulama (Verify)

```bash
python3 /opt/jira_rapor/verify_report.py
```

Adımlar:
1. Tüm projelerden TÜM issue'ları (paginated) çek
2. JSON dump'a kaydet (`/opt/jira_rapor/jira_dump_YYYYMMDD_HHMMSS.json`)
3. En son Excel raporunu oku (`raporlar/Digital_Donusum_*.xlsx`)
4. Karşılaştır:
   - Eksik satır (Jira'da var, Excel'de yok)
   - Fazla satır (Excel'de var, Jira'da yok)
   - Durum farkı (status mismatch)
   - Tarih farkı (duedate / startdate mismatch)

Beklenen çıktı:
```
PROJE: RPA
  Jira: 50 issue   |   Excel: 50 satir
  [OK] Hicbir tutarsizlik yok
...
OZET: 180 Jira issue   |   0 tutarsizlik
```

---

## Yedekleme & Geri Yükleme

### Otomatik Yedekleme

Her büyük değişiklikten önce manuel:
```bash
cd /opt/jira_rapor
TS=$(date +%Y%m%d_%H%M%S)
for f in *.py *.sh; do cp -p "$f" "yedek/${f%.*}_${TS}.${f##*.}"; done
```

Haftalık otomatik temizlik (30 günden eski yedekleri siler):
```cron
0 2 * * 0 find /opt/jira_rapor/yedek -type f -mtime +30 -delete
```

### Geri Yükleme

```bash
# Bir dosyayı eski haline döndür
cp /opt/jira_rapor/yedek/jira_to_excel_20260507_135613.py /opt/jira_rapor/jira_to_excel.py

# Crontab'ı geri yükle (her zaman /opt/jira_rapor/yedek/cron_export.txt yedeği var)
crontab /opt/jira_rapor/yedek/cron_export.txt

# Servisi restart
systemctl restart jira-webhook.service
```

---

## Sorun Giderme

### Webhook gelmiyor

```bash
# 1) Servisler aktif mi?
systemctl is-active jira-webhook.service caddy

# 2) DNS doğru mu?
host your-subdomain.duckdns.org
# Beklenen: VPS IP

# 3) HTTPS endpoint çalışıyor mu?
curl https://your-subdomain.duckdns.org/health
# Beklenen: OK

# 4) Webhook log
tail -f /opt/jira_rapor/jira_webhook.log
# Jira'da değişiklik yap, log'a düşmesi gerek

# 5) Caddy access log
tail -f /var/log/caddy/access.log
# Jira IP'lerinden POST geliyor mu?

# 6) Jira webhook delivery test
# Jira admin paneli → Webhooks → Edit → "Test webhook" butonu
```

### Sabah maili gönderilmedi

```bash
# 1) Cron çalıştı mı?
grep "$(date +%Y-%m-%d) 08:" /opt/jira_rapor/cron_send.log

# 2) Hata varsa
tail -50 /opt/jira_rapor/cron_send.log

# 3) Manuel çalıştır
python3 /opt/jira_rapor/send_report.py

# 4) SMTP testi
python3 -c "import smtplib; s=smtplib.SMTP('exch.gundogdugida.com', 587); s.starttls(); s.login('USER', 'PASS'); print('OK'); s.quit()"
```

### Telegram mesajı gelmiyor

```bash
# 1) Bot token doğru mu?
curl "https://api.telegram.org/bot${TG_TOKEN}/getMe"

# 2) Chat'e erişim var mı?
curl "https://api.telegram.org/bot${TG_TOKEN}/getChat?chat_id=${TG_CHAT}"

# 3) Bot privacy mode kapalı olmalı
# BotFather → /mybots → Bot Settings → Group Privacy → Disable

# 4) Manuel test
python3 -c "
import sys; sys.path.insert(0, '/opt/jira_rapor')
import config as cfg
import urllib.request, urllib.parse
data = urllib.parse.urlencode({'chat_id': cfg.TG_CHAT, 'text': 'TEST'}).encode()
req = urllib.request.Request(f'https://api.telegram.org/bot{cfg.TG_TOKEN}/sendMessage', data=data)
print(urllib.request.urlopen(req).read())
"
```

### Visual dashboard üretilmiyor

```bash
# 1) matplotlib kurulu mu?
python3 -c "import matplotlib; print(matplotlib.__version__)"

# 2) Manuel çalıştır (gönderim yok, sadece üretim)
python3 -c "
import sys; sys.path.insert(0, '/opt/jira_rapor')
from telegram_visual import gather_stats, make_dashboard
stats = gather_stats()
png = make_dashboard(stats)
with open('/tmp/test.png', 'wb') as f: f.write(png)
print(f'OK, {len(png)} bytes')
"
```

### Excel çıktısı boş veya hatalı

```bash
# Verify scriptini çalıştır
python3 /opt/jira_rapor/verify_report.py
# Tutarsızlık varsa hangi proje/key olduğunu söyler
```

### DuckDNS IP güncellenmedi

```bash
# Manuel güncelle
/opt/jira_rapor/duckdns_update.sh
cat /opt/jira_rapor/duckdns.log
# Beklenen son satır: "OK"
# "KO" görürsen: token yanlış veya domain bulunamadı
```

---

## Güvenlik Notları

### Sırlar Yönetimi

- `config.py` **chmod 600**, sadece root okuyabilir
- `.gitignore`'da → asla git'e commit edilmez
- Şablon: `config.example.py` (sahte değerler, git'te commit edilir)
- Sırlar:
  - Jira API token
  - SMTP password
  - Telegram bot token
  - DuckDNS token
  - (opsiyonel) JIRA_WEBHOOK_SECRET

### Webhook Güvenliği

- Caddy + Let's Encrypt → tüm trafik HTTPS
- Caddy access log: kimlerin geldiği görülebilir
- Bot taramaları (`leakix.net`, vs) `/v3/api-docs`, `/.vscode/sftp.json` gibi yolları arıyor → Caddy 404 döner
- **Önemli:** `JIRA_WEBHOOK_SECRET` ayarlanmadıysa rastgele birisi `/jira-webhook` endpoint'ine sahte payload yollayabilir → Telegram spam.
  Çözüm: `config.py`'de `JIRA_WEBHOOK_SECRET = "uzun-string"` ayarla, Jira webhook URL'ine `?token=...` ekle.

### Server Güvenliği

- fail2ban aktif (SSH brute-force koruması)
- ufw inactive ama Caddy + sshd dışında dış erişimli port yok
- Webhook Flask `127.0.0.1:8089`'da dinler, sadece lokalden erişilebilir
- Tüm dış HTTPS trafiği Caddy üzerinden geçer

### KVKK / Kişisel Veri

- `jira_webhook_debug.log` → Jira payload'ları (assignee, summary vb içerir) → `.gitignore`'da
- `jira_dump_*.json` → tam Jira veri dump'ı → `.gitignore`'da
- Excel raporları (`raporlar/`) → `.gitignore`'da
- Email adresleri (`@gundogdugida.com`) sırlar değil ama hassas değerler config'e taşınabilir

---

## Geliştirici Notları

### Yeni Bir Proje Eklemek

Sadece `config.py`'yi güncellemen yeterli:

```python
PROJECTS = ["RPA", "GNDFAB", "GNDERP", "ODOO", "YENI_PROJE"]

PROJECT_THEMES = {
    # ... mevcut projeler
    "YENI_PROJE": {
        "label":            "YENI_PROJE  —  Aciklama",
        "sheet_color":      "AABBCC",
        "card_accent":      "AABBCC",
        "card_btn":         "AABBCC",
        "card_stat_bg":     "AABBCC",
        "card_stat_border": "AABBCC",
        "badge_color":      "AABBCC",
        "badge_bg":         "AABBCC",
    },
}
```

Hiçbir kod değişmez. Bir sonraki rapor üretiminde yeni proje:
- Excel'e yeni "YENI_PROJE Panosu" sheet eklenir
- Ana Sayfa'ya 5. kart eklenir (otomatik hizalı)
- Yol Haritası'nda yeni proje rozeti çıkar
- Telegram visual'da yeni donut çıkar

### Yeni Bir Cron Job Eklemek

Cron wrapper kullan:
```cron
30 10 * * * python3 /opt/jira_rapor/cron_runner.py cron_yeni.log /opt/jira_rapor/yeni_script.py
```

Avantaj: Script crash ederse Telegram'a otomatik alert gider.

### Cloudflared'den DuckDNS'e Geçiş Hikayesi

İlk versiyon Cloudflare quick tunnel kullandı (`*.trycloudflare.com`). Restart'ta URL değişiyor → Jira webhook her seferinde güncellenmesi gerekiyor → kötü UX.

DuckDNS + Caddy:
- Sabit URL (`gnd-jira.duckdns.org`)
- Let's Encrypt otomatik SSL (60g auto-renew)
- DuckDNS auto-update cron (5dk'da bir IP'yi doğrular)
- Cloudflare hesabı gerekmez

---

## Lisans / Sahiplik

Gündoğdu Gıda Dijital Dönüşüm Ekibi — internal tool.

GitHub: https://github.com/sumorf-r/Jira_rapor

Yazar: Muhammed Yusuf YANIK
