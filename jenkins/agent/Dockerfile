FROM jenkins/inbound-agent:latest-jdk17

ARG DOCKER_CLI_VERSION=27.3.1

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends python-is-python3 python3 python3-pip python3-venv curl ca-certificates tar \
    && curl -fsSL -o /tmp/docker.tgz "https://download.docker.com/linux/static/stable/x86_64/docker-${DOCKER_CLI_VERSION}.tgz" \
    && tar -xzf /tmp/docker.tgz -C /tmp \
    && mv /tmp/docker/docker /usr/local/bin/docker \
    && rm -rf /tmp/docker /tmp/docker.tgz \
    && curl -fsSL -o /usr/local/bin/kubectl "https://dl.k8s.io/release/v1.31.2/bin/linux/amd64/kubectl" \
    && chmod +x /usr/local/bin/kubectl \
    && curl -fsSL -o /usr/local/bin/kind "https://kind.sigs.k8s.io/dl/v0.25.0/kind-linux-amd64" \
    && chmod +x /usr/local/bin/kind \
    && curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER jenkins
