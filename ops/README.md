# ops/ — Durcissement de l'origine derrière Cloudflare

La prod est fronted par Cloudflare, mais l'IP de l'origine (`82.66.233.150`, reverse
proxy **OpenResty** sur le Pi) est **joignable en direct** avec un cert Let's Encrypt
valide → on peut contourner CF (WAF, anti-DDoS, cache) et, surtout, **spoofer le
rate-limit** (`api/rate_limit.py` lit désormais `CF-Connecting-IP`, qui n'est fiable
que si seul CF parle à l'origine).

Ce dossier ferme ce trou. Le reverse proxy étant managé **hors de ce repo**, ces
fichiers sont à appliquer manuellement sur le Pi, mais versionnés ici pour relecture.

## 1. Authenticated Origin Pulls (mTLS CF → origine) — recommandé

Force l'origine à n'accepter QUE les connexions présentant le certificat client
Cloudflare. C'est la protection la plus propre (suit l'origine même si l'IP change).

```bash
# Sur le Pi :
sudo mkdir -p /etc/ssl/cloudflare
sudo curl -fsSL \
  https://developers.cloudflare.com/ssl/static/authenticated_origin_pull_ca.pem \
  -o /etc/ssl/cloudflare/authenticated_origin_pull_ca.pem
```

Puis, dashboard Cloudflare → **SSL/TLS → Origin Server → Authenticated Origin Pulls**
→ activer (au niveau zone). Sans cette case, OpenResty rejettera CF aussi.

Enfin, `include` [`cloudflare-origin.conf`](cloudflare-origin.conf) dans **chaque**
bloc `server {}` HTTPS (`monitor.` ET `api-monitor.`) et ajouter les `proxy_set_header`
de la section 3 dans le bloc `location` qui `proxy_pass` vers les conteneurs :

```nginx
server {
    listen 443 ssl;
    server_name api-monitor.gautierchuinard.com;
    # ... ssl_certificate, etc.
    include /etc/openresty/cloudflare-origin.conf;

    location / {
        proxy_set_header Host              $host;
        proxy_set_header CF-Connecting-IP  $remote_addr;   # IP réelle validée via real_ip
        proxy_set_header X-Forwarded-For   $remote_addr;   # écrase toute chaîne client
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_pass http://monitor_api_prod:8000;
    }
}
```

```bash
sudo openresty -t && sudo systemctl reload openresty   # ou: nginx -t && nginx -s reload
```

## 2. Firewall (alternative ou défense en profondeur)

Si tu ne veux pas (ou en plus de) l'AOP : n'ouvrir 80/443 qu'aux plages CF.
Régénère les plages avec [`refresh-cf-ips.sh`](refresh-cf-ips.sh).

```bash
# nftables (exemple)
sudo nft add table inet filter
sudo nft add set inet filter cf_ips '{ type ipv4_addr; flags interval; }'
sudo nft add element inet filter cf_ips "{ $(./refresh-cf-ips.sh nft) }"
sudo nft add chain inet filter input '{ type filter hook input priority 0; }'
sudo nft add rule inet filter input tcp dport { 80, 443 } ip saddr != @cf_ips drop
```

> ⚠️ Garde une règle d'accès SSH (port 22) AVANT le drop, sinon tu te coupes l'accès au Pi.

## 3. Vérification (après application)

```bash
IP=82.66.233.150
# Doit ÉCHOUER maintenant (handshake mTLS refusé / connexion rejetée) :
curl -sS -k --max-time 10 --resolve monitor.gautierchuinard.com:443:$IP \
  https://monitor.gautierchuinard.com/ -o /dev/null -w '%{http_code}\n' || echo "bloqué ✓"

# Doit TOUJOURS marcher via Cloudflare :
curl -sS --max-time 10 https://monitor.gautierchuinard.com/ -o /dev/null -w '%{http_code}\n'
```

Test du rate-limit non spoofable (doit finir par renvoyer 429 malgré un XFF tournant,
car la clé est `CF-Connecting-IP`, posée par CF) :

```bash
for i in $(seq 1 15); do
  curl -sS -o /dev/null -w '%{http_code} ' \
    -H "X-Forwarded-For: 1.2.3.$i" \
    -X POST https://api-monitor.gautierchuinard.com/login \
    -d 'username=x@x.fr&password=x'
done; echo
# attendu : ... 200/401 ... puis 429 (limite atteinte). Avant le fix : jamais de 429.
```

## Lien avec le code

`api/rate_limit.py` clé désormais sur `CF-Connecting-IP` (fallback IP socket en dev).
Cette protection **dépend** de la section 1 ou 2 : sans elle, un attaquant en direct
peut poser lui-même `CF-Connecting-IP`. Les deux volets sont nécessaires.
