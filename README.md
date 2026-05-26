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

## Run tests

```bash
python -m pip install -r app/requirements.txt -r app/requirements-dev.txt
pytest app/tests
```

## Deploy to Kubernetes manually with Helm (app and monitoring)

Create a local kind cluster if it does not already exist:

```bash
kind create cluster --name devops-demo
kubectl get nodes
```

If the app was previously deployed with raw Kubernetes manifests, clean those resources first:

```bash
kubectl delete deployment,svc,configmap,hpa demo-app --ignore-not-found
```

Build the app image and load it into kind:

```bash
docker build -t devops-case-study/demo-app:local ./app
kind load docker-image devops-case-study/demo-app:local --name devops-demo
```

Deploy the app with Helm:

```bash
helm upgrade --install demo-app helm/demo-app \
  --set image.repository=devops-case-study/demo-app \
  --set image.tag=local \
  --set app.env=dev \
  --set app.version=local \
  --wait \
  --timeout 120s
kubectl rollout status deployment/demo-app
```

Deploy Prometheus and Grafana into the same Kubernetes cluster. Prometheus
scrapes the in-cluster Kubernetes service `demo-app:80`.

```bash
docker pull prom/prometheus:v2.54.1
docker pull grafana/grafana:11.2.0
docker pull prom/node-exporter:v1.8.2
kind load docker-image prom/prometheus:v2.54.1 --name devops-demo
kind load docker-image grafana/grafana:11.2.0 --name devops-demo
kind load docker-image prom/node-exporter:v1.8.2 --name devops-demo
helm upgrade --install monitoring helm/monitoring \
  --wait \
  --timeout 180s
kubectl rollout status deployment/prometheus
kubectl rollout status deployment/grafana
```

Open the app, Prometheus, and Grafana with port-forwarding:

```bash
kubectl port-forward svc/demo-app 8080:80
```

In separate terminals:

```bash
kubectl port-forward svc/grafana 3000:3000
kubectl port-forward svc/prometheus 9090:9090
```

URLs:

- App: http://localhost:8080
- Health: http://localhost:8080/health
- Metrics: http://localhost:8080/metrics
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000

Grafana default login: `admin` / `admin`

The dashboard includes three monitoring groups:

- Application: request rate and p95 latency.
- Jenkins pipeline: Jenkins scrape health and last build duration.
- System resources: node CPU and memory usage from node-exporter.

## Deploy to Kubernetes automatically (use CI/CD of Jenkins)

Start Jenkins and the local Docker registry. Rebuild Jenkins when plugin or
tooling changes are pulled from Git:

```bash
docker compose build --no-cache jenkins
docker compose up -d jenkins jenkins-agent docker-registry
```

For kind, create a Jenkins-specific kubeconfig because `127.0.0.1` inside the
Jenkins container points to the Jenkins container itself, not the host:

```bash
cp ~/.kube/config ./kubeconfig-jenkins
sed -i 's#server: https://127.0.0.1:[0-9]*#server: https://devops-demo-control-plane:6443#' ./kubeconfig-jenkins
```

Create Jenkins credentials in `Manage Jenkins > Credentials > System > Global credentials`:

- `kubeconfig`: secret file credential using `./kubeconfig-jenkins`.
- `docker-registry-credentials`: username/password credential for external registries. For the local registry demo this can be a dummy value because `localhost:5000` does not require authentication.

Create a Jenkins Pipeline job:

- Definition: `Pipeline script from SCM`
- SCM: `Git`
- Repository URL: your public GitHub repository URL
- Branch: `*/master` or `*/main`
- Script Path: `Jenkinsfile`

Pipeline parameters:

- `IMAGE_REPOSITORY`: default `localhost:5000/demo-app`
- `KUBE_NAMESPACE`: default `default`
- `KIND_CLUSTER_NAME`: default `devops-demo`
- `LOAD_IMAGE_TO_KIND`: default `true` for local kind demos
- `DEPLOY_MONITORING`: default `true`
- `DEPLOY_ENV`: default `dev`

Run `Build with Parameters`. The pipeline executes:

- Checkout from GitHub.
- Unit tests.
- Helm lint and template rendering for app and monitoring charts.
- Docker build.
- Image push to `localhost:5000/demo-app`.
- Image load into kind.
- App deploy with `helm upgrade --install --wait`.
- Monitoring deploy with `helm upgrade --install --wait`.

Verify the deployment:

```bash
kubectl get pods,svc,deploy,hpa
helm list
```

Open Grafana after a successful build:

```bash
kubectl port-forward svc/grafana 3000:3000
```

The app uses a Kubernetes RollingUpdate strategy. If a deployment is unhealthy,
roll back with `helm rollback demo-app <revision>` or `kubectl rollout undo
deployment/demo-app`.

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
