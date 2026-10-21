#!/usr/bin/env bash
# Deploy the app to Azure Container Apps.
#
# Prerequisites: `az login`, the containerapp extension (`az extension add -n containerapp`),
# and TOMTOM_API_KEY in the environment. Run from the repository root:
#
#   TOMTOM_API_KEY=... ./deploy/azure-container-apps.sh
#
# Optional: SUBSCRIPTION, RG, LOCATION, APP, ENV_NAME, ACR, TAG, CUSTOM_HOST (defaults below).
# Some subscriptions (Azure for Students among them) only allow a few regions; check with
# `az policy assignment list` and set LOCATION to one of them.
set -euo pipefail

: "${TOMTOM_API_KEY:?Set TOMTOM_API_KEY}"
RG=${RG:-truck-routing-rg}
LOCATION=${LOCATION:-centralindia}
APP=${APP:-truck-routing}
ENV_NAME=${ENV_NAME:-truck-routing-env}
ACR=${ACR:-truckrouting$RANDOM}
TAG=${TAG:-$(git rev-parse --short HEAD)}

if [[ -n "${SUBSCRIPTION:-}" ]]; then
  az account set --subscription "$SUBSCRIPTION"
fi

echo "Resource group $RG in $LOCATION"
az group create --name "$RG" --location "$LOCATION" --output none
az acr show --name "$ACR" --output none 2>/dev/null ||
  az acr create --name "$ACR" --resource-group "$RG" --location "$LOCATION" \
    --sku Basic --admin-enabled true --output none

# Build the Dockerfile in Azure; no local Docker needed. .dockerignore keeps .env out.
az acr build --registry "$ACR" --image "$APP:$TAG" --platform linux/amd64 . --no-logs
IMAGE="$ACR.azurecr.io/$APP:$TAG"

az containerapp env show --name "$ENV_NAME" --resource-group "$RG" --output none 2>/dev/null ||
  az containerapp env create --name "$ENV_NAME" --resource-group "$RG" \
    --location "$LOCATION" --output none

if az containerapp show --name "$APP" --resource-group "$RG" --output none 2>/dev/null; then
  az containerapp update --name "$APP" --resource-group "$RG" --image "$IMAGE" --output none
else
  DJANGO_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(50))")
  ACR_PASSWORD=$(az acr credential show --name "$ACR" --query "passwords[0].value" --output tsv)
  # Keys live in Container Apps secrets, never in the image or the repository.
  # One replica always running, so a reviewer never waits for a cold start.
  az containerapp create --name "$APP" --resource-group "$RG" --environment "$ENV_NAME" \
    --image "$IMAGE" --registry-server "$ACR.azurecr.io" \
    --registry-username "$ACR" --registry-password "$ACR_PASSWORD" \
    --target-port 8000 --ingress external --cpu 0.5 --memory 1.0Gi \
    --min-replicas 1 --max-replicas 2 \
    --secrets tomtom-key="$TOMTOM_API_KEY" django-secret="$DJANGO_SECRET" \
    --env-vars TOMTOM_API_KEY=secretref:tomtom-key DJANGO_SECRET_KEY=secretref:django-secret \
      DJANGO_DEBUG=false --output none
fi

FQDN=$(az containerapp show --name "$APP" --resource-group "$RG" \
  --query properties.configuration.ingress.fqdn --output tsv)
HOSTS=$FQDN
ORIGINS=https://$FQDN
if [[ -n "${CUSTOM_HOST:-}" ]]; then
  HOSTS="$HOSTS,$CUSTOM_HOST"
  ORIGINS="$ORIGINS,https://$CUSTOM_HOST"
fi
az containerapp update --name "$APP" --resource-group "$RG" \
  --set-env-vars DJANGO_ALLOWED_HOSTS="$HOSTS" DJANGO_CSRF_TRUSTED_ORIGINS="$ORIGINS" \
  --output none

echo "Deployed: https://$FQDN"
curl --silent --fail --retry 10 --retry-delay 5 --retry-all-errors "https://$FQDN/api/health/" && echo
