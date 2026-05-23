# DevOps Case Study Report

Candidate scope: Task 0 Kubernetes Deployment, Task 1 Jenkins CI/CD Pipeline, Task 3 Monitoring & Observability.

## 1. Architecture

The demo repository contains a Python FastAPI service, a Jenkins pipeline, Helm charts for the application and monitoring stack, and a lightweight Prometheus/Grafana deployment for a local Kubernetes cluster. The application exposes `/`, `/health`, `/ready`, `/work`, and `/metrics`. Prometheus scrapes application metrics through the in-cluster Kubernetes service `demo-app:80`, and Grafana provisions a dashboard for request rate and latency.

Local components:

- `demo-app`: FastAPI application.
- `jenkins`: Jenkins controller with Docker, Python, kubectl, and pipeline plugins.
- `jenkins-agent`: optional inbound agent image.
- `docker-registry`: local registry for image push demos.
- `monitoring` Helm release: Prometheus and Grafana running inside Kubernetes.

Some credentials are intentionally mocked or created manually in Jenkins because the submitted repository must not contain secrets.

## 2. Pipeline Design

The `Jenkinsfile` is a multi-stage pipeline:

1. Checkout source code.
2. Validate and Test in parallel:
   - Python unit tests with JUnit report publishing.
   - Helm chart linting and manifest rendering.
3. Docker Build with BuildKit and immutable image tag.
4. Image Push to local registry or authenticated external registry.
5. Load the image into kind for local demos when enabled.
6. Deploy to Kubernetes with `helm upgrade --install`, image overrides, environment overrides, `--atomic`, `--wait`, and rollout status verification.
7. Deploy Prometheus and Grafana to Kubernetes with the `helm/monitoring` chart when enabled.

Error handling is implemented with Helm `--atomic` for automatic rollback and `post { failure { ... } }`, which collects Kubernetes deployment, service, HPA, pod, and Helm release history to speed up troubleshooting. The pipeline disables concurrent builds to avoid two deployments racing on the same namespace.

Image versioning uses:

```text
BUILD_NUMBER-GIT_SHA_SHORT
```

This makes each deployment traceable while still pushing `latest` for local demo convenience.

For local kind demos, the pipeline can run `kind load docker-image` after image push. This keeps the required registry push stage while avoiding the common kind issue where pods cannot pull `localhost:5000` from inside the Kubernetes node.

## 3. Kubernetes Deployment

The primary Kubernetes deployment path uses the Helm chart in `helm/demo-app/`:

- `values.yaml`: default image, environment, replicas, resources, probes, service, and HPA settings.
- `templates/deployment.yaml`: two replicas, rolling update strategy, probes, resource requests and limits.
- `templates/service.yaml`: internal ClusterIP service.
- `templates/configmap.yaml`: environment-specific non-secret configuration.
- `templates/hpa.yaml`: optional HorizontalPodAutoscaler.

The deployment uses a RollingUpdate strategy with `maxUnavailable: 0` and `maxSurge: 1` so a new pod must become ready before old capacity is removed. Readiness and liveness probes reduce the chance of routing traffic to unhealthy pods.

This demo uses Helm in the Jenkins deployment stage because the pipeline needs repeatable releases, per-environment overrides, release history, and rollback support. `kubectl apply` is still useful for small manual tests, but Helm is a better fit for CI/CD because one command can install or upgrade the release and `--atomic` can automatically roll back when the deployment does not become healthy.

## 4. Rollback and Scaling

Rollback:

```bash
helm rollback demo-app
kubectl rollout status deployment/demo-app
```

For a specific revision:

```bash
helm history demo-app
helm rollback demo-app <revision>
```

In Jenkins, rollback is automatic during deployment because `helm upgrade --install` runs with `--atomic --wait --timeout 120s`. If new pods fail readiness checks or the deployment times out, Helm reverts the release to the previous working revision.

Scaling can be done manually:

```bash
kubectl scale deployment/demo-app --replicas=4
```

Or automatically through the Helm chart HPA template, which targets 70 percent CPU utilization and scales between two and five replicas.

## 5. Monitoring and Observability

The app exposes Prometheus metrics via `/metrics`. The monitoring stack is deployed into the same kind cluster with the `helm/monitoring` chart:

- `prometheus`: scrapes `demo-app:80/metrics` inside the cluster.
- `grafana`: uses Prometheus as a provisioned datasource.
- `grafana-dashboard-demo-app`: provisions the demo dashboard from a ConfigMap.

Application metrics:

- `demo_app_http_requests_total`
- `demo_app_http_request_duration_seconds`

Important metrics:

- Request rate by path.
- HTTP 5xx rate.
- p95/p99 latency.
- Pod CPU and memory usage.
- Kubernetes restart count.
- Jenkins build duration and failure rate.

The current implementation focuses on application metrics and Prometheus self-monitoring. Jenkins pipeline observability is represented by Jenkins build status, build duration, and stage logs. In a production setup, Jenkins metrics can be added by installing the Jenkins Prometheus plugin and scraping the Jenkins `/prometheus` endpoint from Prometheus.

Alert examples:

- p95 latency above 1 second for 5 minutes.
- 5xx error rate above 2 percent for 5 minutes.
- Pod restarts greater than 3 in 10 minutes.
- Jenkins pipeline failure on the main branch.

Production debugging flow:

1. Check Grafana for latency, error rate, and saturation changes.
2. Inspect recent deployment revision and image tag.
3. Check pod logs and Kubernetes events.
4. Compare CPU/memory usage against resource limits.
5. Roll back if user impact is high, then investigate root cause.

## 6. Troubleshooting

Common Kubernetes deployment issues:

- `ImagePullBackOff`: wrong image tag, registry authentication failure, or local cluster cannot access local registry.
- Helm ownership conflict: resources were previously created by `kubectl apply`; delete or migrate them before installing the Helm release.
- `CrashLoopBackOff`: application startup error, missing environment variable, or invalid command.
- Readiness probe failure: wrong path, wrong port, slow startup, or dependency unavailable.
- Pending pods: insufficient CPU/memory or node scheduling constraints.
- Service unreachable: selector labels do not match pod labels or wrong target port.

Useful commands:

```bash
kubectl get pods,svc,deploy
kubectl describe pod <pod>
kubectl logs deploy/demo-app
kubectl rollout status deployment/demo-app
kubectl get events --sort-by=.lastTimestamp
```

## 7. Run Demo

Start app and monitoring:

```bash
docker compose up --build demo-app
```

Start Jenkins stack:

```bash
docker compose up --build -d jenkins docker-registry
```

Deploy manually to local Kubernetes:

```bash
docker build -t devops-case-study/demo-app:local ./app
kind load docker-image devops-case-study/demo-app:local
helm upgrade --install demo-app helm/demo-app \
  --set image.repository=devops-case-study/demo-app \
  --set image.tag=local \
  --set app.env=dev \
  --set app.version=local \
  --atomic \
  --wait \
  --timeout 120s
kubectl rollout status deployment/demo-app
kubectl port-forward svc/demo-app 8080:80
```

Deploy monitoring to the same Kubernetes cluster:

```bash
helm upgrade --install monitoring helm/monitoring \
  --atomic \
  --wait \
  --timeout 180s
kubectl rollout status deployment/prometheus
kubectl rollout status deployment/grafana
kubectl port-forward svc/grafana 3000:3000
kubectl port-forward svc/prometheus 9090:9090
```

Jenkins requires two credentials:

- `docker-registry-credentials` for external registry push.
- `kubeconfig` as a secret file for Kubernetes deployment.

For the included local registry, use `IMAGE_REPOSITORY=localhost:5000/demo-app`.

## 8. Design Decisions

FastAPI was selected because it is small, easy to test, and can expose metrics without extra infrastructure. Helm was selected for CI/CD deployment because it provides release history, value overrides, and automatic rollback with `--atomic`. The Docker Compose stack includes Jenkins, an optional agent image, a local registry, app, Prometheus, and Grafana so the reviewer can run the whole demo locally.

The repository keeps secrets out of source control. Jenkins credentials and kubeconfig are injected at runtime. This mirrors production CI/CD behavior while keeping the public repository safe.
