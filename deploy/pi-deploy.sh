#!/bin/bash
# Déploiement de Monitor sur le Pi. Ce script ne se lance pas à la main : il est
# exécuté par /usr/local/sbin/gotyeah-deploy (commande forcée de la clé
# DEPLOY_SSH_KEY dans authorized_keys), juste après le git pull de main, depuis
# /home/pi/sites/gotyeah-monitor. Argument : le commit déployé avant celui-ci.
# Modifier ce fichier suffit : le prochain déploiement lance la version de main.
# Si l'API ou le front ne deviennent pas sains, retour au commit d'avant.
set -uo pipefail

avant=${1:?commit précédent attendu en argument}

compose() {
  docker compose -f docker-compose.prod.yml --env-file .env "$@"
}

# Attend qu'un conteneur passe « healthy » (healthchecks du compose).
wait_healthy() {
  local cname=$1 timeout=150 elapsed=0 health
  while true; do
    health=$(docker inspect --format '{{.State.Health.Status}}' "$cname" 2>/dev/null || echo absent)
    [ "$health" = healthy ] && return 0
    [ "$health" = absent ] && { echo "Conteneur $cname introuvable"; return 1; }
    [ "$elapsed" -ge "$timeout" ] && { echo "$cname non healthy après ${timeout}s (état : $health)"; return 1; }
    sleep 5
    elapsed=$((elapsed + 5))
  done
}

rollback() {
  echo "::error::Déploiement KO, retour arrière vers $avant"
  git reset --hard "$avant"
  compose up -d --build --force-recreate
  exit 1
}

compose up -d --build --force-recreate || rollback
wait_healthy monitor_api_prod || rollback
wait_healthy monitor_front_prod || rollback
echo "Déploiement OK : api + front healthy"
