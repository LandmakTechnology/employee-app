# ArgoCD — Definition, Installation, Setup & Usage

## Table of Contents
- [What is ArgoCD](#what-is-argocd)
- [How It Works](#how-it-works)
- [Installation](#installation)
- [UI Access](#ui-access)
- [Deploying Applications](#deploying-applications)
- [GitHub Webhook Setup](#github-webhook-setup)
- [GitOps Flow](#gitops-flow)
- [Troubleshooting](#troubleshooting)

---

## What is ArgoCD

ArgoCD is a declarative, GitOps continuous delivery tool for Kubernetes. It watches a Git repository and automatically syncs the desired state defined in Git to the actual state running in the cluster.

**Key concepts:**
- **Desired state** — what is defined in your Git repo (Helm charts, manifests, values.yaml)
- **Live state** — what is actually running in the cluster
- **Sync** — the process of making live state match desired state
- **Self-heal** — automatically corrects any manual changes made to the cluster that drift from Git

---

## How It Works

```
Developer pushes code
        │
        ▼
GitHub (source of truth)
        │
        │  webhook triggers instantly
        ▼
ArgoCD detects change in repo
        │
        │  compares desired vs live state
        ▼
ArgoCD syncs cluster to match Git
        │
        ▼
Kubernetes applies new resources
```

---

## Installation

### Prerequisites
- EKS cluster running and `kubectl` configured
- AWS Load Balancer Controller installed
- Helm installed

### Step 1 — Add the Argo Helm repo

```bash
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update
```

### Step 2 — Create the namespace

```bash
kubectl create namespace argocd
```

### Step 3 — Install ArgoCD via Helm

This installs ArgoCD with an internet-facing NLB and insecure mode (plain HTTP) so the UI is accessible via the load balancer:

```bash
helm install argocd argo/argo-cd \
  --namespace argocd \
  --set server.service.type=LoadBalancer \
  --set configs.params."server\.insecure"=true \
  --set "server.service.annotations.service\.beta\.kubernetes\.io/aws-load-balancer-scheme=internet-facing" \
  --set "server.service.annotations.service\.beta\.kubernetes\.io/aws-load-balancer-type=nlb"
```

> **Why `server.insecure=true`?**  
> By default ArgoCD enforces HTTPS and redirects HTTP traffic. Since the NLB terminates at port 80, setting insecure mode allows the UI to be served over plain HTTP without SSL passthrough issues.

> **Why `internet-facing`?**  
> Without this annotation, EKS creates an internal NLB (only accessible within the VPC). The `internet-facing` annotation makes it publicly accessible.

### Step 4 — Verify installation

```bash
kubectl get pods -n argocd
kubectl get svc argocd-server -n argocd
```

All 7 pods should be `Running`:
- `argocd-server`
- `argocd-application-controller`
- `argocd-applicationset-controller`
- `argocd-dex-server`
- `argocd-notifications-controller`
- `argocd-redis`
- `argocd-repo-server`

---

## UI Access

### Step 1 — Get the NLB URL

```bash
kubectl get svc argocd-server -n argocd
```

Copy the value under `EXTERNAL-IP` — this is your ArgoCD URL.

### Step 2 — Verify the NLB is internet-facing and active

```bash
aws elbv2 describe-load-balancers \
  --profile terraform \
  --region us-east-1 \
  --query "LoadBalancers[?contains(DNSName, 'argocd')].{DNS:DNSName,Scheme:Scheme,State:State.Code}" \
  --output table
```

Wait until `State` shows `active` (takes 2-3 minutes after install).

### Step 3 — Get the initial admin password

```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d
```

### Step 4 — Login

Open your browser:
```
http://<EXTERNAL-IP>
```

- Username: `admin`
- Password: output from Step 3

> **Note:** Delete the initial secret after changing your password:
> ```bash
> kubectl delete secret argocd-initial-admin-secret -n argocd
> ```

---

## Deploying Applications

Applications are deployed by creating ArgoCD `Application` manifests and applying them once. ArgoCD then manages all future syncs automatically.

### Employee App (Helm chart from Git)

```yaml
# argocd-app.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: employee-app
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/LandmakTechnology/employee-app.git
    targetRevision: main
    path: helm
    helm:
      valueFiles:
        - values.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: employee-app
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

```bash
kubectl apply -f argocd-app.yaml
```

### Monitoring Stack (Helm chart from Helm repo)

The monitoring stack is deployed as a separate ArgoCD Application into its own `monitoring` namespace. `ServerSideApply=true` and `Replace=true` are required because the kube-prometheus-stack CRDs have annotations that exceed the 262KB kubectl apply limit.

```yaml
# argocd-monitoring.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: monitoring
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://prometheus-community.github.io/helm-charts
    chart: kube-prometheus-stack
    targetRevision: "72.6.2"
    helm:
      values: |
        alertmanager:
          enabled: false
        grafana:
          adminPassword: admin123
          service:
            type: LoadBalancer
            annotations:
              service.beta.kubernetes.io/aws-load-balancer-scheme: internet-facing
              service.beta.kubernetes.io/aws-load-balancer-nlb-target-type: ip
          sidecar:
            dashboards:
              enabled: true
              label: grafana_dashboard
              labelValue: "1"
              searchNamespace: ALL
          serviceAccount:
            annotations:
              eks.amazonaws.com/role-arn: "arn:aws:iam::075120018043:role/landmark-cluster-dev-app-sa"
        prometheus:
          prometheusSpec:
            serviceMonitorSelectorNilUsesHelmValues: false
            podMonitorSelectorNilUsesHelmValues: false
            serviceMonitorNamespaceSelector: {}
            retention: 7d
            storageSpec:
              volumeClaimTemplate:
                spec:
                  storageClassName: gp2
                  accessModes: ["ReadWriteOnce"]
                  resources:
                    requests:
                      storage: 10Gi
        nodeExporter:
          enabled: true
        kubeStateMetrics:
          enabled: true
  destination:
    server: https://kubernetes.default.svc
    namespace: monitoring
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
      - Replace=true
      - ServerSideApply=true
```

```bash
kubectl apply -f argocd-monitoring.yaml
```

---

## GitHub Webhook Setup

Without a webhook, ArgoCD polls the repo every 3 minutes. A webhook makes ArgoCD sync **instantly** on every push.

### Step 1 — Get your ArgoCD URL

```bash
kubectl get svc argocd-server -n argocd -o jsonpath="{.status.loadBalancer.ingress[0].hostname}"
```

### Step 2 — Add webhook in GitHub

1. Go to your repo → **Settings** → **Webhooks** → **Add webhook**
2. Fill in:

| Field | Value |
|-------|-------|
| Payload URL | `http://<ARGOCD-URL>/api/webhook` |
| Content type | `application/json` |
| Secret | *(leave blank)* |
| Events | `Just the push event` |

3. Click **Add webhook**

From this point, every `git push` to `main` instantly triggers ArgoCD to sync.

---

## GitOps Flow

With ArgoCD managing deployments, the CI/CD pipeline is split into two clear responsibilities:

```
GitHub Actions (CI)          ArgoCD (CD)
──────────────────           ───────────
Run tests                    Watch Git repo
Build Docker images          Detect changes in values.yaml
Push to ECR                  Sync cluster to match Git
Update helm/values.yaml      Roll out new pods
Git push new tags            Self-heal any drift
```

**GitHub Actions workflow stages:**
1. `test` — runs pytest
2. `build-and-push` — builds images, pushes to ECR with timestamp tag
3. `update-image-tags` — updates `helm/values.yaml` with new tags, commits and pushes to Git

ArgoCD detects the `values.yaml` change via webhook and rolls out the new images automatically.

> **Important:** The GitHub Actions pipeline must NOT run `helm upgrade` directly — this conflicts with ArgoCD's management of the cluster. ArgoCD is the single source of truth for what runs in the cluster.

---

## Troubleshooting

### NLB shows internal instead of internet-facing
The default Kubernetes `LoadBalancer` service on EKS creates an internal NLB. Always set the annotation:
```bash
helm upgrade argocd argo/argo-cd --namespace argocd \
  --set server.service.type=LoadBalancer \
  --set configs.params."server\.insecure"=true \
  --set "server.service.annotations.service\.beta\.kubernetes\.io/aws-load-balancer-scheme=internet-facing" \
  --set "server.service.annotations.service\.beta\.kubernetes\.io/aws-load-balancer-type=nlb"
```

### ArgoCD shows OutOfSync / Degraded after moving monitoring to separate namespace
This happens when ArgoCD has stale resources in its state from a previous Helm release. Fix:
```bash
# Delete the ArgoCD application
kubectl delete application employee-app -n argocd

# Force delete the stuck namespace
kubectl delete namespace employee-app --force --grace-period=0

# If namespace is stuck in Terminating, clear hook finalizers
kubectl patch job <job-name> -n employee-app \
  --type merge -p '{"metadata":{"finalizers":null}}'

# Recreate the application fresh
kubectl apply -f argocd-app.yaml
```

### CRD annotations too large (kube-prometheus-stack)
```
metadata.annotations: Too long: may not be more than 262144 bytes
```
Add `ServerSideApply=true` and `Replace=true` to the Application syncOptions:
```yaml
syncOptions:
  - CreateNamespace=true
  - Replace=true
  - ServerSideApply=true
```

### ArgoCD not syncing after git push
1. Check webhook is configured in GitHub → Settings → Webhooks
2. Verify the webhook delivery shows a green tick (200 response)
3. If no webhook, ArgoCD polls every 3 minutes — wait or trigger manually:
```bash
kubectl patch application employee-app -n argocd \
  --type merge \
  -p '{"operation":{"initiatedBy":{"username":"admin"},"sync":{"revision":"main"}}}'
```

### Chart.lock causes manifest generation error
```
cannot load Chart.lock: error unmarshaling JSON: parsing time ""
```
Delete the `Chart.lock` file if there are no subchart dependencies:
```bash
rm helm/Chart.lock
git add . && git commit -m "fix: remove invalid Chart.lock" && git push origin main
```
Then hard refresh ArgoCD:
```bash
kubectl patch application employee-app -n argocd \
  --type merge \
  -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"hard"}}}'
```
