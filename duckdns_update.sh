#!/bin/bash
# DuckDNS IP auto-update
# Cron: her 5 dakikada calisir
#
# Kullanim:
#   1) duckdns.org'a kaydol, bir subdomain olustur, token al
#   2) Asagidaki DOMAIN ve TOKEN degerlerini kendi degerlerinle degistir
#   3) chmod +x duckdns_update.sh
#   4) crontab: */5 * * * * /opt/jira_rapor/duckdns_update.sh

DOMAIN="your-subdomain"          # ornek: gnd-jira  (sadece subdomain kismi, .duckdns.org olmadan)
TOKEN="your-duckdns-token-uuid"  # duckdns.org panelinden al
LOG="/opt/jira_rapor/duckdns.log"

RESULT=$(curl -s "https://www.duckdns.org/update?domains=$DOMAIN&token=$TOKEN&ip=")
echo "[$(date '+%Y-%m-%d %H:%M:%S')] $RESULT" >> "$LOG"
