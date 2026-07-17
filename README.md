# Employee Directory App

A production-grade, cloud-native web application for managing employee records — built on AWS EKS with full observability, automated CI/CD, and security at every layer.

---

## Table of Contents

- [Application Overview](#application-overview)
- [Architecture Design](#architecture-design)
- [Networking Design](#networking-design)
- [Data Flow](#data-flow)
- [Infrastructure Components](#infrastructure-components)
- [Security Model](#security-model)
- [Observability Stack](#observability-stack)
- [CI/CD Pipeline](#cicd-pipeline)
- [Deployment Guide](#deployment-guide)
- [Operations](#operations)

---

## Application Overview

The Employee Directory App is a full-stack application with two containerised services:

| Service | Technology | Responsibility |
|---------|-----------|----------------|
| **Backend** | Python Flask | REST API — CRUD, photo upload, health check, metrics |
| **Frontend** | Nginx + HTML/JS | Single-page UI served as static files |

### Backend API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/employees` | List all employees |
| `POST` | `/api/employees` | Create employee (with optional photo) |
| `PUT` | `/api/employees/<id>` | Update employee record |
| `DELETE` | `/api/employees/<id>` | Delete employee |
| `GET` | `/api/stats` | Aggregated stats (count, departments, latest hire) |
| `GET` | `/api/health` | Liveness/readiness probe — verifies DB connectivity |
| `GET` | `/metrics` | Prometheus metrics (request rate, latency histograms, error counts) |

---

## Architecture Design

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              AWS Account (us-east-1)                         │
│                                                                              │
│  ┌─────────────────────────── VPC: 10.0.0.0/16 ──────────────────────────┐  │
│  │                                                                        │  │
│  │   ┌─── Public Subnets (us-east-1a / 1b) ──────────────────────────┐  │  │
│  │   │                                                                 │  │  │
│  │   │   ┌─────────────────────┐     ┌──────────┐  ┌──────────┐      │  │  │
│  │   │   │  Application LB     │     │  NAT GW  │  │  NAT GW  │      │  │  │
│  │   │   │  (internet-facing)  │     │  (AZ-a)  │  │  (AZ-b)  │      │  │  │
│  │   │   └──────────┬──────────┘     └────┬─────┘  └────┬─────┘      │  │  │
│  │   └──────────────┼────────────────────┼──────────────┼────────────┘  │  │
│  │                  │                    │              │                │  │
│  │   ┌─── Private Subnets ──────────────┼──────────────┼────────────┐  │  │
│  │   │              │                   │              │             │  │  │
│  │   │   ┌──────────▼──────────────────────────────────────────┐    │  │  │
│  │   │   │              EKS Cluster: landmark-cluster-dev       │    │  │  │
│  │   │   │                                                      │    │  │  │
│  │   │   │  ┌─────────────────┐    ┌─────────────────┐         │    │  │  │
│  │   │   │  │   Node (AZ-a)   │    │   Node (AZ-b)   │         │    │  │  │
│  │   │   │  │  t3.medium      │    │  t3.medium      │         │    │  │  │
│  │   │   │  │                 │    │                 │         │    │  │  │
│  │   │   │  │ ┌─────────────┐ │    │ ┌─────────────┐ │         │    │  │  │
│  │   │   │  │ │  backend    │ │    │ │  backend    │ │         │    │  │  │
│  │   │   │  │ │  (replica1) │ │    │ │  (replica2) │ │         │    │  │  │
│  │   │   │  │ ├─────────────┤ │    │ ├─────────────┤ │         │    │  │  │
│  │   │   │  │ │  frontend   │ │    │ │  frontend   │ │         │    │  │  │
│  │   │   │  │ │  (replica1) │ │    │ │  (replica2) │ │         │    │  │  │
│  │   │   │  │ ├─────────────┤ │    │ ├─────────────┤ │         │    │  │  │
│  │   │   │  │ │  prometheus │ │    │ │  grafana    │ │         │    │  │  │
│  │   │   │  │ │  node-exp.  │ │    │ │  kube-state │ │         │    │  │  │
│  │   │   │  │ └─────────────┘ │    │ └─────────────┘ │         │    │  │  │
│  │   │   │  └─────────────────┘    └─────────────────┘         │    │  │  │
│  │   │   └──────────────────────────────────────────────────────┘    │  │  │
│  │   │                                                                │  │  │
│  │   │   ┌──────────────────────────────────────────────────────┐    │  │  │
│  │   │   │              RDS PostgreSQL 15.7                      │    │  │  │
│  │   │   │         landmark-db-dev  (private, encrypted)         │    │  │  │
│  │   │   └──────────────────────────────────────────────────────┘    │  │  │
│  │   └────────────────────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │     ECR      │  │      S3      │  │   Secrets    │  │  CloudWatch    │  │
│  │  (2 repos)   │  │  (photos)    │  │   Manager    │  │  (logs+metrics)│  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Kubernetes Workloads

| Workload | Replicas | Namespace | Purpose |
|----------|----------|-----------|---------|
| `backend` | 2 | `employee-app` | Flask REST API |
| `frontend` | 2 | `employee-app` | Nginx static UI |
| `prometheus` | 1 | `employee-app` | Metrics collection (10Gi EBS) |
| `grafana` | 1 | `employee-app` | Dashboards (NLB exposed) |
| `alertmanager` | 1 | `employee-app` | Alert routing |
| `kube-state-metrics` | 1 | `employee-app` | K8s object metrics |
| `node-exporter` | 1/node | `employee-app` | Host-level metrics |
| `external-secrets` | 1 | `external-secrets` | Syncs Secrets Manager → K8s |
| `aws-load-balancer-controller` | 1 | `kube-system` | Provisions ALB/NLB from Ingress |

---

## Networking Design

```
Internet
    │
    ▼
┌───────────────────────────────────────────────────────┐
│  Application Load Balancer (internet-facing)           │
│  Listener: HTTP :80                                    │
│                                                        │
│  Rules:                                                │
│    /api/*  ──────────────────────▶  backend:5000       │
│    /*       ─────────────────────▶  frontend:80        │
└───────────────────────────────────────────────────────┘
    │                         │
    ▼                         ▼
┌──────────────┐     ┌──────────────────┐
│  Frontend    │     │  Backend         │
│  Service     │     │  Service         │
│  (ClusterIP) │     │  (ClusterIP)     │
│  port 80     │     │  port 5000       │
└──────┬───────┘     └────────┬─────────┘
       │                      │
       ▼                      ▼
┌──────────────┐     ┌──────────────────┐
│  Nginx pods  │     │  Flask pods      │
│  (2 replicas)│     │  (2 replicas)    │
└──────────────┘     └────────┬─────────┘
                               │  TCP 5432
                               ▼
                    ┌──────────────────────┐
                    │  RDS PostgreSQL       │
                    │  (private subnet)     │
                    │  SG: allows 5432 from │
                    │  EKS node SG only     │
                    └──────────────────────┘

Grafana (separate NLB, internet-facing):
Internet ──▶ NLB :80 ──▶ Grafana Service (LoadBalancer) ──▶ Grafana pod :3000
```

### Subnet Layout

| Subnet Type | CIDR Range | Resources |
|-------------|-----------|-----------|
| Public AZ-a | `10.0.101.0/24` | ALB, NAT Gateway |
| Public AZ-b | `10.0.102.0/24` | ALB, NAT Gateway |
| Private AZ-a | `10.0.1.0/24` | EKS nodes, RDS |
| Private AZ-b | `10.0.2.0/24` | EKS nodes, RDS |

### Security Groups

| Security Group | Inbound | Outbound |
|----------------|---------|----------|
| ALB SG | `0.0.0.0/0 :80` | EKS node SG |
| EKS Node SG | ALB SG, cluster SG, node-to-node | `0.0.0.0/0` (via NAT) |
| RDS SG | EKS node SG `:5432`, cluster SG `:5432`, VPC CIDR `:5432` | None |

---

## Data Flow

### User Request Flow

```
Browser
  │
  │  HTTP GET /
  ▼
ALB (internet-facing)
  │
  │  Rule: /* → frontend service
  ▼
Frontend Pod (Nginx)
  │  Serves index.html + static assets
  │
  │  Browser JS calls GET /api/employees
  ▼
ALB
  │
  │  Rule: /api/* → backend service
  ▼
Backend Pod (Flask)
  │
  ├──▶ PostgreSQL (RDS)          — employee records
  ├──▶ S3 (landmark-app-bucket)  — photo storage/retrieval
  └──▶ CloudWatch Logs           — structured JSON request logs
```

### Secret Injection Flow

```
AWS Secrets Manager
  │  landmark-cluster-dev/employee-app
  │  { DB_HOST, DB_USER, DB_PASS, DB_NAME, SECRET_KEY }
  │
  ▼
External Secrets Operator (ESO)
  │  SecretStore → ClusterSecretStore
  │  ExternalSecret → syncs every 1h
  │
  ▼
Kubernetes Secret: db-credentials
  │
  ▼
Backend Pod (env vars injected at runtime)
  │  DATABASE_URL=postgresql://user:pass@host/db
  └──▶ SQLAlchemy connection pool
```

### Image Delivery Flow

```
GitHub Push to main
  │
  ▼
GitHub Actions
  │  docker build → docker push
  │
  ▼
ECR (private)
  │  075120018043.dkr.ecr.us-east-1.amazonaws.com/
  │  ├── employee-backend:be-dev-YYYYMMDD-HHMMSS
  │  └── employee-frontend:fe-dev-YYYYMMDD-HHMMSS
  │
  ▼
EKS (kubelet pulls via IRSA auth)
  │
  ▼
Running Pods
```

### Metrics & Logs Flow

```
Flask Backend
  │  /metrics endpoint (prometheus-flask-exporter)
  │
  ▼
Prometheus (ServiceMonitor scrapes every 30s)
  │  Stores in 10Gi EBS volume (7d retention)
  │
  ▼
Grafana (queries Prometheus datasource)
  │  Application Dashboard: request rate, latency, errors
  │  Platform Dashboard: node CPU/memory, pod counts

Flask Backend
  │  Structured JSON logs (watchtower)
  │
  ▼
CloudWatch Logs: /landmark/employee-app
  │
  ▼
Grafana (queries CloudWatch datasource via IRSA)
  │  CloudWatch Dashboard: Logs Insights queries
  │  Panels: request rate, avg response time, error rate, slowest endpoints
```

---

## Infrastructure Components

### Terraform Modules

| Module | Source | Purpose |
|--------|--------|---------|
| VPC | `terraform-aws-modules/vpc/aws` | VPC, subnets, NAT GW, route tables, subnet tags for LB discovery |
| EKS | `terraform-aws-modules/eks/aws` | Cluster, managed node group, OIDC provider, KMS encryption |
| IRSA | `terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks` | IAM roles bound to K8s service accounts via OIDC |

### IRSA Roles

| Role | K8s Service Account | Permissions |
|------|--------------------|----|
| `landmark-cluster-dev-app-sa` | `employee-app:app-sa`, `employee-app:employee-app-grafana` | S3 read/write, ECR pull, Secrets Manager read, CloudWatch logs/metrics |
| `landmark-cluster-dev-lb-controller` | `kube-system:aws-load-balancer-controller` | EC2/ELB management for ALB/NLB provisioning |
| `landmark-cluster-dev-ebs-csi` | `kube-system:ebs-csi-controller-sa` | EBS volume create/attach/delete for PVC provisioning |

### EKS Add-ons

| Add-on | Version | Purpose |
|--------|---------|---------|
| `aws-ebs-csi-driver` | latest | PVC provisioning (Prometheus storage) |
| `coredns` | managed | Cluster DNS |
| `kube-proxy` | managed | Network proxy |
| `vpc-cni` | managed | Pod networking |

### Terraform State

Remote state stored in S3 bucket `landmark-terraform-state-file` with versioning enabled. State locking via S3 native locking.

### Environment Configuration

```
terraform/env/
├── dev/terraform.tfvars    # 2 nodes, t3.medium, 1-day RDS backup
├── stg/terraform.tfvars    # mirrors prod config for pre-prod testing
└── prod/terraform.tfvars   # multi-AZ RDS, 7-day backup, final snapshot
```

---

## Security Model

### Defence in Depth

```
Layer 1 — Network
  ├── RDS in private subnets (no internet route)
  ├── EKS nodes in private subnets (outbound via NAT only)
  └── ALB is the only internet-facing entry point for the app

Layer 2 — Identity & Access
  ├── IRSA: pods assume IAM roles via OIDC — zero static credentials
  ├── Least-privilege: each role scoped to specific ARNs
  └── ECR: private repos, auth token required to pull

Layer 3 — Secrets
  ├── DB credentials in Secrets Manager (never in code or env files)
  ├── ESO syncs to K8s Secret at runtime
  └── GitHub Secrets for CI/CD credentials

Layer 4 — Encryption
  ├── RDS: storage_encrypted = true (AES-256)
  ├── EKS secrets: KMS-encrypted at rest
  └── S3: server-side encryption, public access fully blocked

Layer 5 — Audit
  ├── EKS control plane logs: api, audit, authenticator, controllerManager, scheduler
  └── Application logs: structured JSON → CloudWatch (14-day retention)
```

---

## Observability Stack

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Grafana (NLB :80)                         │
│                                                             │
│  ┌──────────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Platform Metrics │  │  App Metrics │  │  CW Logs     │  │
│  │ - Node CPU/Mem   │  │ - Req rate   │  │ - Req rate   │  │
│  │ - Pod counts     │  │ - p95 latency│  │ - Error rate │  │
│  │ - Pod restarts   │  │ - 5xx errors │  │ - Slow reqs  │  │
│  └──────────────────┘  └──────────────┘  └──────────────┘  │
└──────────────────────────────────────────────────────────────┘
         │                      │                    │
         ▼                      ▼                    ▼
   Prometheus              Prometheus           CloudWatch
   (kube-state-            (ServiceMonitor      Logs Insights
    metrics,                scrapes /metrics     (/landmark/
    node-exporter)          every 30s)            employee-app)
```

### Dashboards

| Dashboard | Datasource | Key Panels |
|-----------|-----------|------------|
| Platform Metrics | Prometheus | Node CPU, node memory, pod count, pod restarts, per-pod resource usage |
| Application Metrics | Prometheus | HTTP request rate, 5xx error rate, p95 latency, network I/O |
| CloudWatch Logs | CloudWatch | Request rate from logs, avg response time, error rate, slowest endpoints, method breakdown |

---

## CI/CD Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                    GitHub Actions Workflow                        │
│                                                                  │
│  Trigger: push to main  OR  workflow_dispatch                    │
│                                                                  │
│  ┌──────────────┐    ┌──────────────────────┐    ┌───────────┐  │
│  │   Stage 1    │    │       Stage 2         │    │  Stage 3  │  │
│  │    TEST      │───▶│   BUILD & PUSH        │───▶│  DEPLOY   │  │
│  │              │    │                       │    │           │  │
│  │ pip install  │    │ docker build backend  │    │ helm      │  │
│  │ requirements │    │ docker build frontend │    │ upgrade   │  │
│  │ pytest       │    │ push to ECR           │    │ --install │  │
│  │              │    │ tag: be-dev-TIMESTAMP │    │ --wait    │  │
│  │ Gate: fail   │    │ update values.yaml    │    │           │  │
│  │ stops here   │    │ git commit + push     │    │ verify    │  │
│  └──────────────┘    └──────────────────────┘    └───────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Image Tagging Strategy

Tags follow the format `be-dev-YYYYMMDD-HHMMSS` — every build produces a unique, traceable tag. The deployed tag is always visible in `helm/values.yaml` in the repo (GitOps traceability).

### Deployment Strategy

Kubernetes rolling update — new pods become Ready before old pods terminate. Zero downtime deployments.

---

## Deployment Guide

### Prerequisites

- AWS CLI configured with profile `terraform`
- `kubectl`, `helm`, `terraform` installed
- Docker installed and running

### 1. Deploy Infrastructure

```bash
cd terraform
terraform init
terraform apply -var-file=env/dev/terraform.tfvars
```

### 2. Connect to EKS

```bash
aws eks update-kubeconfig --name landmark-cluster-dev --region us-east-1 --profile terraform
```

### 3. Install Cluster Add-ons

```bash
# External Secrets Operator
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets external-secrets/external-secrets \
  -n external-secrets --create-namespace --wait

# AWS Load Balancer Controller
helm repo add eks https://aws.github.io/eks-charts
helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=landmark-cluster-dev \
  --set serviceAccount.create=true \
  --set serviceAccount.name=aws-load-balancer-controller \
  --set serviceAccount.annotations."eks\.amazonaws\.com/role-arn"=$(terraform output -raw lb_controller_role_arn)
```

### 4. Update Helm Values

```bash
# Get outputs
terraform output s3_access_role_arn
terraform output app_bucket_name
```

Update `helm/values.yaml`:
- `serviceAccount.roleArn` ← `s3_access_role_arn`
- `s3.bucket` ← `app_bucket_name`

### 5. Build and Push Images

```bash
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin 075120018043.dkr.ecr.us-east-1.amazonaws.com

cd employee-app/backend
docker build -t 075120018043.dkr.ecr.us-east-1.amazonaws.com/employee-backend:latest .
docker push 075120018043.dkr.ecr.us-east-1.amazonaws.com/employee-backend:latest

cd ../frontend
docker build -t 075120018043.dkr.ecr.us-east-1.amazonaws.com/employee-frontend:latest .
docker push 075120018043.dkr.ecr.us-east-1.amazonaws.com/employee-frontend:latest
```

### 6. Deploy the App

```bash
helm install employee-app helm/ --namespace employee-app --create-namespace
```

### 7. Verify

```bash
kubectl get pods -n employee-app
kubectl get ingress -n employee-app   # ALB URL in ADDRESS column
```

---

## Operations

### Access URLs

| Service | How to get URL |
|---------|---------------|
| App (ALB) | `kubectl get ingress -n employee-app` → ADDRESS column |
| Grafana (NLB) | `kubectl get svc -n employee-app employee-app-grafana` → EXTERNAL-IP |

Grafana default credentials: `admin` / `admin123`

### View Logs

```bash
# Container logs
kubectl logs -n employee-app -l app=backend --follow

# CloudWatch
aws logs tail /landmark/employee-app --follow --profile terraform
```

### Connect to Database

```bash
# Spin up a postgres client pod
kubectl run pg-client --rm -it --image=postgres:15 --namespace=employee-app -- bash

# Get RDS endpoint
aws rds describe-db-instances \
  --db-instance-identifier landmark-db-dev \
  --query "DBInstances[0].Endpoint.Address" \
  --output text --profile terraform

# Connect
psql -h <RDS_ENDPOINT> -U landmark_admin -d employees
```

### Run Tests

```bash
cd employee-app/backend
pip install -r requirements.txt
pytest
```

### Destroy

```bash
helm uninstall employee-app -n employee-app
cd terraform && terraform destroy -var-file=env/dev/terraform.tfvars
```
