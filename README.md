# EKS GitOps Platform: Uptime Monitor

> **Status: work in progress.** Built step by step; the roadmap below shows what is done.

A small **uptime monitoring service**, built as a multi-service app and run on a
production-style platform on AWS. Infrastructure is managed with Terraform, delivery runs through
GitHub Actions and ArgoCD (GitOps), and the platform is monitored with Prometheus, Grafana and
Alertmanager.

## What it does

- Register the URLs you want to watch (for example `https://github.com` or your own service)
- A **checker** service checks every target on a schedule and records whether it is up and how fast it responded
- The **API** shows targets, check history and current status
- **Alerts** fire when a target goes down

```
POST /targets   {"url": "https://github.com"}
→ 201 Created   {"id": 1, "url": "https://github.com"}

GET  /status
→ 200 OK        [{"id": 1, "url": "https://github.com", "up": true, "response_ms": 84}]
```

## Planned architecture

```
Request path
  User ──▶ AWS Load Balancer ──▶ api (EKS, autoscaled) ──┐
                                                         ├──▶ PostgreSQL (Amazon RDS)
                                 checker (EKS worker) ───┘
                                     └──▶ checks external URLs

Monitoring
  Prometheus ◀── metrics from api + checker
      ├──▶ Alertmanager ("target down" alerts)
      └──▶ Grafana dashboards

Delivery
  git push ──▶ GitHub Actions: test → build → scan → push images (ECR)
  ArgoCD (in the cluster) watches this repo and deploys the Helm chart
```

_A proper diagram will replace this sketch._

## Why Kubernetes?

For this workload alone, **Amazon ECS Fargate or App Runner would be simpler and cheaper**, and I
have run ECS Fargate in production. I chose EKS deliberately, to learn and demonstrate Kubernetes
operations on a realistic multi-service workload: separate scaling for the API and the checker,
health probes, persistent storage, network policies, GitOps delivery and failure recovery.

## Goals

- Infrastructure fully defined as code, reproducible with one `terraform apply` and removable with one `terraform destroy`
- No long-lived AWS credentials in CI (GitHub Actions → AWS via OIDC)
- Git as the single source of truth for what runs in the cluster (ArgoCD)
- Secure by default: non-root containers, image vulnerability scanning, least-privilege IAM, network policies
- Observable: metrics, dashboards and alerts that mean something
- Resilient: failure scenarios tested on purpose and documented
- Cost-aware: documented costs and a clean teardown

## Tech stack

| Area                   | Tools                                                  |
| ---------------------- | ------------------------------------------------------ |
| Application            | Python, FastAPI, httpx, PostgreSQL                     |
| Containers             | Docker, Docker Compose                                 |
| Orchestration          | Kubernetes (kind locally, Amazon EKS on AWS), Helm     |
| GitOps                 | ArgoCD                                                 |
| CI/CD                  | GitHub Actions, Trivy                                  |
| Infrastructure as Code | Terraform (VPC, EKS, ECR, RDS, IAM)                    |
| Observability          | Prometheus, Grafana, Alertmanager                      |

## Roadmap

- [x] **1. API:** FastAPI service with health check, target endpoints (in memory), tests
- [ ] **2. Docker & database:** small, non-root image; Docker Compose with PostgreSQL; API stores data in PostgreSQL _(in progress: image and Compose setup done)_
- [ ] **3. Checker:** worker that checks targets on a schedule and records results
- [ ] **4. Local Kubernetes:** manifests on kind (Deployments, StatefulSet, Services, NetworkPolicies), then a Helm chart
- [ ] **5. GitOps & monitoring (local):** ArgoCD, Prometheus, Grafana, Alertmanager "target down" alert
- [ ] **6. CI:** GitHub Actions pipeline with tests, image builds and vulnerability scans
- [ ] **7. AWS foundation:** Terraform remote state, VPC, ECR, RDS
- [ ] **8. EKS:** cluster via Terraform, GitHub OIDC, ArgoCD and Load Balancer Controller on EKS
- [ ] **9. Failure drills & docs:** tested failure scenarios, architecture diagram, cost table, design decisions

## Failure drills (planned)

| Scenario                    | Expected behaviour                                                  | Result |
| --------------------------- | ------------------------------------------------------------------- | ------ |
| Delete an API pod           | Kubernetes replaces it; no downtime with 2+ replicas                | _TBD_  |
| Drain a node                | Pods are rescheduled on another node                                | _TBD_  |
| Database unavailable        | Readiness probe fails, traffic stops, alert fires                   | _TBD_  |
| Deploy a broken image       | Probes stop the rollout; roll back through Git and ArgoCD           | _TBD_  |
| A monitored site goes down  | Checker records it, "target down" alert fires                       | _TBD_  |

## Repository structure

```
docker-compose.yml   Local development: API + PostgreSQL
.env.example         Settings template for Docker Compose (copy to .env)
services/
  api/               FastAPI service: targets, results, status (with its Dockerfile)
  checker/           Worker that runs the checks (milestone 3)
k8s/                 Kubernetes manifests and Helm chart
argocd/              ArgoCD application definitions
monitoring/          Prometheus / Grafana / Alertmanager configuration
terraform/           AWS infrastructure (bootstrap + environments)
.github/workflows/   CI pipelines
docs/                Diagrams and design decisions
```

## Run locally

### With Docker Compose

Requirements: Docker Desktop (or Docker Engine with the Compose plugin)

From the repository root:

```bash
cp .env.example .env                 # then set your own password (letters and digits only)
docker compose up --build
```

This starts two containers:

- `db`: PostgreSQL 18, with its data in the named volume `pgdata`, so it survives restarts
- `api`: the API, built from `services/api/Dockerfile`; it starts once the database is healthy

> The API still keeps targets in memory; storing them in PostgreSQL is the next step of milestone 2.

Useful commands:

```bash
docker compose ps                                       # status of both containers
docker compose logs -f api                              # follow the API logs
docker compose exec db psql -U uptime -d uptime         # open a SQL shell in the database
docker compose down                                     # stop and remove the containers, keep the data
docker compose down -v                                  # also delete the volume: all data is lost
```

### Without Docker

Requirements: Python 3.14

```bash
cd services/api
py -3.14 -m venv .venv
source .venv/Scripts/activate        # Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn src.main:app --reload
```

### Try it

Both ways serve the API on port 8000. Interactive API docs: http://localhost:8000/docs

```bash
curl -X POST http://localhost:8000/targets -H "Content-Type: application/json" -d '{"url": "https://github.com"}'
curl http://localhost:8000/targets
```

### Run the tests

From `services/api`, with the virtual environment active:

```bash
python -m pytest -v
```

## Deploy to AWS

_Coming with milestone 8._

> ⚠️ **Cost warning:** EKS, NAT gateways and RDS are billed per hour while they exist.
> Always run `terraform destroy` when you are done.

## Design decisions

_Coming soon in `docs/decisions.md`._
