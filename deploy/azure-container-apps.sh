#!/usr/bin/env bash
# Deploy the app to Azure Container Apps.
#
# Prerequisites: `az login`, the containerapp extension (`az extension add -n containerapp`),
# and TOMTOM_API_KEY in the environment. Run from the repository root:
#
#   TOMTOM_API_KEY=... ./deploy/azure-container-apps.sh
#
# Optional: SUBSCRIPTION, RG, LOCATION, APP, ENV_NAME (defaults below).
set -euo pipefail

: "${TOMTOM_API_KEY:?Set TOMTOM_API_KEY}"
RG=${RG:-truck-routing-rg}
LOCATION=${LOCATION:-eastus}
APP=${APP:-truck-routing}
ENV_NAME=${ENV_NAME:-truck-routing-env}

if [[ -n "${SUBSCRIPTION:-}" ]]; then
  az account set --subscription "$SUBSCRIPTION"
fi

echo "Resource group $RG in $LOCATION"
az group create --name "$RG" --location "$LOCATION" --output none

# Builds the Dockerfile in Azure (creates a container registry) and creates the app.
az containerapp up \
  --name "$APP" \
  --resource-group "$RG" \
  --location "$LOCATION" \
  --environment "$ENV_NAME" \
  --source . \
  --ingress external \
  --target-port 8000

FQDN=$(az containerapp show --name "$APP" --resource-group "$RG" \
  --query properties.configuration.ingress.fqdn --output tsv)
DJANGO_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(50))")

# Keys live in Container Apps secrets, never in the image or the repository.
az containerapp secret set --name "$APP" --resource-group "$RG" \
  --secrets tomtom-key="$TOMTOM_API_KEY" django-secret="$DJANGO_SECRET" --output none

# One replica always running, so a reviewer never waits for a cold start.
az containerapp update --name "$APP" --resource-group "$RG" \
  --min-replicas 1 --max-replicas 2 \
  --set-env-vars \
    TOMTOM_API_KEY=secretref:tomtom-key \
    DJANGO_SECRET_KEY=secretref:django-secret \
    DJANGO_DEBUG=false \
    DJANGO_ALLOWED_HOSTS="$FQDN" \
    DJANGO_CSRF_TRUSTED_ORIGINS="https://$FQDN" \
  --output none

echo "Deployed: https://$FQDN"
curl --silent --fail "https://$FQDN/api/health/" && echo
