# Kubernetes Deployment — Ollive LLM Platform

Self-hosted k8s deployment using Kustomize with dev and prod overlays.

## Structure

```
k8s/
├── base/                    # shared manifests
│   ├── namespace.yaml
│   ├── secrets.yaml
│   ├── ingress.yaml
│   ├── backend/
│   │   ├── configmap.yaml
│   │   ├── deployment.yaml  # 2 replicas, init containers, health checks
│   │   ├── service.yaml
│   │   └── hpa.yaml         # autoscale 2→10 pods on CPU/memory
│   ├── frontend/
│   │   ├── deployment.yaml
│   │   └── service.yaml
│   ├── postgres/
│   │   ├── pvc.yaml         # 5Gi persistent volume
│   │   ├── deployment.yaml
│   │   └── service.yaml
│   └── redis/
│       ├── deployment.yaml
│       └── service.yaml
├── overlays/
│   ├── dev/                 # single replica, NodePort, debug=true
│   │   └── kustomization.yaml
│   └── prod/                # 3 replicas, TLS ingress, HPA
│       └── kustomization.yaml
├── deploy.sh                # one-command deploy script
└── README.md
```

## Quick Deploy

### Prerequisites
- A running k8s cluster (minikube, k3s, kubeadm, or any self-hosted)
- `kubectl` configured
- `kustomize` installed
- Docker (for building images)

### 1. Set your API key
```bash
cp backend/.env.example backend/.env
# Edit backend/.env — set GROQ_API_KEY
```

### 2. Deploy to dev (minikube / local k8s)
```bash
chmod +x k8s/deploy.sh
./k8s/deploy.sh dev

# Access at:
# Frontend: http://<node-ip>:30080
# Backend:  http://<node-ip>:30800/docs
```

### 3. Deploy to prod
```bash
./k8s/deploy.sh prod
# Requires: nginx ingress controller, cert-manager (for TLS)
```

### 4. Check status
```bash
./k8s/deploy.sh status
```

### 5. Teardown
```bash
./k8s/deploy.sh teardown
```

## Manual Deploy (without script)

```bash
# Dev
kustomize build k8s/overlays/dev | kubectl apply -f -

# Prod
kustomize build k8s/overlays/prod | kubectl apply -f -

# Watch rollout
kubectl rollout status deployment/backend -n ollive
kubectl rollout status deployment/frontend -n ollive
```

## Self-Hosted k8s Setup (k3s — lightest option)

```bash
# Install k3s on your server (single node)
curl -sfL https://get.k3s.io | sh -

# Copy kubeconfig
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# Install nginx ingress
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/cloud/deploy.yaml

# Install cert-manager (for TLS)
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/latest/download/cert-manager.yaml

# Deploy Ollive
./k8s/deploy.sh prod
```

## Architecture on k8s

```
Internet
    │
    ▼
┌─────────────────────────────────────────┐
│  nginx Ingress Controller               │
│  ollive.yourdomain.com                  │
│  /api/* → backend:8000                  │
│  /*     → frontend:80                   │
└──────────────┬──────────────────────────┘
               │
    ┌──────────┴──────────┐
    ▼                     ▼
┌─────────┐         ┌──────────┐
│ frontend│         │ backend  │
│ 2-3 pods│         │ 2-10 pods│ ← HPA
│ nginx   │         │ FastAPI  │
└─────────┘         └────┬─────┘
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
         ┌────────┐ ┌────────┐ ┌────────┐
         │postgres│ │ redis  │ │ ollama │
         │ 1 pod  │ │ 1 pod  │ │optional│
         │ 5Gi PVC│ │256MB   │ └────────┘
         └────────┘ └────────┘
```

## CI/CD (GitHub Actions)

The `.github/workflows/ci-cd.yml` pipeline:
1. **test** — Python syntax check + frontend build on every push/PR
2. **build** — builds and pushes Docker images to GitHub Container Registry
3. **deploy** — applies kustomize manifests to your k8s cluster via `KUBECONFIG` secret

To enable auto-deploy, add these GitHub secrets:
- `KUBECONFIG` — base64-encoded kubeconfig: `cat ~/.kube/config | base64`
