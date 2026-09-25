#!/bin/bash
# Déploiement de Monitor sur le Pi. Ce script ne se lance pas à la main : il est
# exécuté par /usr/local/sbin/gotyeah-deploy (commande forcée de la clé
# DEPLOY_SSH_KEY dans authorized_keys), depuis /home/pi/sites/gotyeah-monitor, après un git fetch.
# Variables reçues : CIBLE (commit à déployer), AVANT (commit en place).
# Le script est lu dans le commit CIBLE : le modifier sur main suffit.
# Si l'API ou le front ne deviennent pas sains, retour au commit AVANT.
set -uo pipefail

git merge --ff-only "$CIBLE" || exit 1

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
  echo "::error::Déploiement KO, retour arrière vers $AVANT"
  git reset --hard "$AVANT"
  compose up -d --build --force-recreate
  exit 1
}

compose up -d --build --force-recreate || rollback
wait_healthy monitor_api_prod || rollback
wait_healthy monitor_front_prod || rollback
echo "Déploiement OK : api + front healthy"
