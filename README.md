# EKS GitOps Platform

> **Status: work in progress.** Built step by step; the roadmap below shows what is done.

A production-style platform on AWS: a small Python API, containerised with Docker, deployed to
Amazon EKS. Infrastructure is managed with Terraform, delivery runs through GitHub Actions and
ArgoCD (GitOps), and the cluster is monitored with Prometheus and Grafana.

## Goals

- Infrastructure fully defined as code, reproducible with one `terraform apply` and removable with one `terraform destroy`
- No long-lived AWS credentials in CI (GitHub Actions → AWS via OIDC)
- Git as the single source of truth for what runs in the cluster (ArgoCD)
- Secure by default: non-root containers, image vulnerability scanning, least-privilege IAM
- Observable: metrics, dashboards and at least one meaningful alert
- Cost-aware: documented costs and a clean teardown

## Planned architecture

```
Developer ──push──▶ GitHub ──▶ GitHub Actions: test → build → scan → push image (ECR)
                       │
                       └──▶ ArgoCD (in EKS) watches the repo ──▶ deploys Helm chart to EKS
                                                                     │
                                         AWS Load Balancer ◀─────────┘
                                                                     │
                                         Prometheus / Grafana ◀──────┘
```

_A proper diagram will replace this sketch._

## Tech stack

| Area                   | Tools                                              |
| ---------------------- | -------------------------------------------------- |
| Application            | Python, FastAPI, PostgreSQL                        |
| Containers             | Docker, Docker Compose                             |
| Orchestration          | Kubernetes (kind locally, Amazon EKS on AWS), Helm |
| GitOps                 | ArgoCD                                             |
| CI/CD                  | GitHub Actions, Trivy                              |
| Infrastructure as Code | Terraform (VPC, EKS, ECR, IAM)                     |
| Observability          | Prometheus, Grafana                                |

## Roadmap

- [ ] **1. App:** FastAPI service with health check, tests
- [ ] **2. Docker:** small, non-root image; Docker Compose with PostgreSQL
- [ ] **3. Local Kubernetes:** plain manifests on kind, then a Helm chart
- [ ] **4. GitOps & monitoring (local):** ArgoCD, Prometheus, Grafana
- [ ] **5. CI:** GitHub Actions pipeline with tests, image build and vulnerability scan
- [ ] **6. AWS foundation:** Terraform remote state, VPC, ECR
- [ ] **7. EKS:** cluster via Terraform, GitHub OIDC, ArgoCD and Load Balancer Controller on EKS
- [ ] **8. Docs:** architecture diagram, cost table, design decisions

## Repository structure

```
app/                 FastAPI application, tests, Dockerfile
k8s/                 Kubernetes manifests and Helm chart
argocd/              ArgoCD application definitions
monitoring/          Prometheus / Grafana configuration
terraform/           AWS infrastructure (bootstrap + environments)
.github/workflows/   CI pipelines
docs/                Diagrams and design decisions
```

## Run locally

_Coming with milestone 1._

## Deploy to AWS

_Coming with milestone 7._

> ⚠️ **Cost warning:** EKS and NAT gateways are billed per hour while they exist.
> Always run `terraform destroy` when you are done.

## Design decisions

_Coming soon in `docs/decisions.md`._
