# DevOps Case Study Demo

Demo repository for the Practical Exercise:

- Task 0: Kubernetes Deployment
- Task 1: Jenkins CI/CD Pipeline
- Task 3: Monitoring & Observability

The demo application is a Python FastAPI service with unit tests, a Docker image,
Helm charts, a Jenkins pipeline, and Prometheus/Grafana monitoring inside a local
Kubernetes cluster.

## Prerequisites

- Docker + Docker Compose
- Local Kubernetes: `kind`, `minikube`, or `k3d`
- `kubectl`
- Public Docker registry account, for example Docker Hub

## Run application locally

```bash
docker compose up --build demo-app
```

Endpoints:

- App: http://localhost:8080
- Health: http://localhost:8080/health
- Metrics: http://localhost:8080/metrics

## Run tests

```bash
python -m pip install -r app/requirements.txt -r app/requirements-dev.txt
pytest app/tests
```

## Deploy to Kubernetes manually with Helm

If the app was previously deployed with raw Kubernetes manifests, clean those resources first:

```bash
kubectl delete deployment,svc,configmap,hpa demo-app --ignore-not-found
```

Build and load image into kind:

```bash
docker build -t devops-case-study/demo-app:local ./app
kind load docker-image devops-case-study/demo-app:local --name devops-demo
helm upgrade --install demo-app helm/demo-app \
  --set image.repository=devops-case-study/demo-app \
  --set image.tag=local \
  --set app.env=dev \
  --set app.version=local \
  --atomic \
  --wait \
  --timeout 120s
kubectl rollout status deployment/demo-app
```

Port forward:

```bash
kubectl port-forward svc/demo-app 8080:80
```

## Deploy monitoring into Kubernetes

Prometheus and Grafana run inside the same kind cluster and Prometheus scrapes the
Kubernetes service `demo-app:80`.

If image pulls are slow or Docker Hub times out, pre-pull and load the monitoring
images into kind:

```bash
docker pull prom/prometheus:v2.54.1
docker pull grafana/grafana:11.2.0
kind load docker-image prom/prometheus:v2.54.1 --name devops-demo
kind load docker-image grafana/grafana:11.2.0 --name devops-demo
```

Install the monitoring chart:

```bash
helm upgrade --install monitoring helm/monitoring \
  --atomic \
  --wait \
  --timeout 180s
kubectl rollout status deployment/prometheus
kubectl rollout status deployment/grafana
```

Open Prometheus:

```bash
kubectl port-forward svc/prometheus 9090:9090
```

Open Grafana in another terminal:

```bash
kubectl port-forward svc/grafana 3000:3000
```

URLs:

- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000

Grafana default login: `admin` / `admin`

## Jenkins demo

Start Jenkins stack:

```bash
docker compose up --build -d jenkins jenkins-agent docker-registry
```

Create Jenkins credentials:

- `docker-registry-credentials`: username/password for Docker Hub or registry
- `kubeconfig`: secret file credential containing kubeconfig for local cluster

Pipeline parameters:

- `IMAGE_REPOSITORY`: default `localhost:5000/demo-app`
- `KUBE_NAMESPACE`: default `default`
- `KIND_CLUSTER_NAME`: default `devops-demo`
- `LOAD_IMAGE_TO_KIND`: default `true` for local kind demos
- `DEPLOY_MONITORING`: default `true`
- `DEPLOY_ENV`: default `dev`

For the local registry included in compose, use:

```text
IMAGE_REPOSITORY=localhost:5000/demo-app
```

The Jenkins deploy stage uses Helm:

```bash
helm upgrade --install demo-app helm/demo-app --atomic --wait --timeout 120s
```

`--atomic` automatically rolls back the release if the upgrade fails.

For local kind clusters, the pipeline also runs:

```bash
kind load docker-image localhost:5000/demo-app:<tag> --name devops-demo
```

This keeps the required image push step while avoiding local registry pull issues inside kind.

When `DEPLOY_MONITORING=true`, Jenkins also deploys Prometheus and Grafana with:

```bash
helm upgrade --install monitoring helm/monitoring --atomic --wait --timeout 180s
```

## Repository layout

```text
.
|-- Jenkinsfile
|-- docker-compose.yml
|-- app/
|-- helm/
|-- jenkins/
`-- report/
```
