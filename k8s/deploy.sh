#!/bin/bash
# ──────────────────────────────────────────────────────────────────────────────
# Ollive LLM Platform — Self-Hosted Kubernetes Deploy Script
# Usage:
#   ./k8s/deploy.sh dev      # deploy to dev (NodePort, single replica)
#   ./k8s/deploy.sh prod     # deploy to prod (Ingress, HPA, TLS)
#   ./k8s/deploy.sh status   # show current state
#   ./k8s/deploy.sh teardown # remove everything
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail

ENV=${1:-dev}
NAMESPACE="ollive"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${BLUE}[ollive]${NC} $1"; }
ok()   { echo -e "${GREEN}[ok]${NC} $1"; }
warn() { echo -e "${YELLOW}[warn]${NC} $1"; }
err()  { echo -e "${RED}[error]${NC} $1"; exit 1; }

# ── Prerequisites check ───────────────────────────────────────────────────────
check_prereqs() {
  command -v kubectl  >/dev/null 2>&1 || err "kubectl not found"
  command -v kustomize >/dev/null 2>&1 || err "kustomize not found. Install: https://kustomize.io"
  kubectl cluster-info >/dev/null 2>&1 || err "Cannot connect to k8s cluster. Check your kubeconfig."
  ok "Prerequisites OK"
}

# ── Build images locally (for self-hosted / minikube) ────────────────────────
build_images() {
  log "Building Docker images..."

  # If using minikube, point docker to minikube's daemon
  if command -v minikube >/dev/null 2>&1; then
    warn "Detected minikube — using minikube docker daemon"
    eval $(minikube docker-env)
  fi

  docker build -t ollive-backend:latest ./backend
  docker build -t ollive-frontend:latest ./frontend
  ok "Images built"
}

# ── Deploy ────────────────────────────────────────────────────────────────────
deploy() {
  log "Deploying to environment: ${ENV}"

  # Create namespace if it doesn't exist
  kubectl get namespace ${NAMESPACE} >/dev/null 2>&1 || \
    kubectl create namespace ${NAMESPACE}

  # Apply secrets (update GROQ_API_KEY before running)
  if [ -f "backend/.env" ]; then
    log "Creating secret from backend/.env..."
    kubectl create secret generic ollive-secrets \
      --from-env-file=backend/.env \
      --namespace=${NAMESPACE} \
      --dry-run=client -o yaml | kubectl apply -f -
    ok "Secret applied"
  else
    warn "backend/.env not found — using placeholder secrets from k8s/base/secrets.yaml"
  fi

  # Apply kustomize overlay
  log "Applying kustomize overlay: k8s/overlays/${ENV}"
  kustomize build k8s/overlays/${ENV} | kubectl apply -f -

  # Wait for rollouts
  log "Waiting for deployments to be ready..."
  kubectl rollout status deployment/postgres  -n ${NAMESPACE} --timeout=120s || true
  kubectl rollout status deployment/redis     -n ${NAMESPACE} --timeout=60s  || true
  kubectl rollout status deployment/backend   -n ${NAMESPACE} --timeout=120s
  kubectl rollout status deployment/frontend  -n ${NAMESPACE} --timeout=60s

  ok "Deployment complete!"
  status
}

# ── Status ────────────────────────────────────────────────────────────────────
status() {
  echo ""
  log "=== Pods ==="
  kubectl get pods -n ${NAMESPACE} -o wide

  echo ""
  log "=== Services ==="
  kubectl get svc -n ${NAMESPACE}

  echo ""
  log "=== Ingress ==="
  kubectl get ingress -n ${NAMESPACE} 2>/dev/null || echo "No ingress found"

  echo ""
  log "=== HPA ==="
  kubectl get hpa -n ${NAMESPACE} 2>/dev/null || echo "No HPA found"

  if [ "${ENV}" = "dev" ]; then
    echo ""
    NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
    ok "Frontend: http://${NODE_IP}:30080"
    ok "Backend:  http://${NODE_IP}:30800"
    ok "API Docs: http://${NODE_IP}:30800/docs"
  fi
}

# ── Teardown ──────────────────────────────────────────────────────────────────
teardown() {
  warn "Removing all Ollive resources from namespace: ${NAMESPACE}"
  read -p "Are you sure? (yes/no): " confirm
  [ "${confirm}" = "yes" ] || { log "Aborted."; exit 0; }

  kustomize build k8s/overlays/${ENV} | kubectl delete -f - --ignore-not-found
  kubectl delete namespace ${NAMESPACE} --ignore-not-found
  ok "Teardown complete"
}

# ── Main ──────────────────────────────────────────────────────────────────────
check_prereqs

case "${ENV}" in
  dev|prod)
    build_images
    deploy
    ;;
  status)
    status
    ;;
  teardown)
    teardown
    ;;
  *)
    err "Unknown command: ${ENV}. Use: dev | prod | status | teardown"
    ;;
esac
