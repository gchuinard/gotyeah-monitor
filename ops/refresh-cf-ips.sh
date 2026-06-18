#!/usr/bin/env bash
# Régénère la liste `set_real_ip_from` (plages IP Cloudflare) pour
# ops/cloudflare-origin.conf, et les éléments nftables pour l'allowlist firewall.
# Cloudflare change rarement ses plages, mais re-lancer ce script de temps en temps.
#
#   ./refresh-cf-ips.sh nginx   > /tmp/cf-real-ip.conf    # bloc set_real_ip_from
#   ./refresh-cf-ips.sh nft                                 # éléments { ... } nftables
set -euo pipefail

fetch_ips() {
  curl -fsSL --max-time 15 https://www.cloudflare.com/ips-v4
  echo
  curl -fsSL --max-time 15 https://www.cloudflare.com/ips-v6
}

mode="${1:-nginx}"
case "$mode" in
  nginx)
    fetch_ips | grep -E '[0-9a-fA-F:.]+/[0-9]+' | while read -r cidr; do
      printf 'set_real_ip_from %s;\n' "$cidr"
    done
    ;;
  nft)
    # Pour : nft add element inet filter cf_ips { ... }
    fetch_ips | grep -E '[0-9a-fA-F:.]+/[0-9]+' | paste -sd, -
    ;;
  *)
    echo "usage: $0 [nginx|nft]" >&2
    exit 2
    ;;
esac
