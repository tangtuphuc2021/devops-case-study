import os
import time

from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

APP_NAME = "demo-app"
APP_VERSION = os.getenv("APP_VERSION", "dev")
APP_ENV = os.getenv("APP_ENV", "local")

REQUEST_COUNT = Counter(
    "demo_app_http_requests_total",
    "Total HTTP requests served by the demo application.",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "demo_app_http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ["method", "path"],
)

app = FastAPI(title="DevOps Case Study Demo", version=APP_VERSION)


@app.middleware("http")
async def metrics_middleware(request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    path = request.url.path
    REQUEST_COUNT.labels(request.method, path, response.status_code).inc()
    REQUEST_LATENCY.labels(request.method, path).observe(elapsed)
    return response


@app.get("/")
def root():
    return {
        "service": APP_NAME,
        "version": os.getenv("APP_VERSION", APP_VERSION),
        "environment": os.getenv("APP_ENV", APP_ENV),
        "status": "ok",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/ready")
def ready():
    return {"status": "ready"}


@app.get("/work")
def work(iterations: int = 1000):
    iterations = max(1, min(iterations, 100000))
    total = sum(i * i for i in range(iterations))
    return {"iterations": iterations, "result": total}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

