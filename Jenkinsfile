pipeline {
  agent any

  options {
    timestamps()
    ansiColor('xterm')
    disableConcurrentBuilds()
    buildDiscarder(logRotator(numToKeepStr: '10'))
  }

  parameters {
    string(name: 'IMAGE_REPOSITORY', defaultValue: 'localhost:5000/demo-app', description: 'Docker image repository')
    string(name: 'KUBE_NAMESPACE', defaultValue: 'default', description: 'Kubernetes namespace')
    string(name: 'KIND_CLUSTER_NAME', defaultValue: 'devops-demo', description: 'Local kind cluster name for image loading')
    booleanParam(name: 'LOAD_IMAGE_TO_KIND', defaultValue: true, description: 'Load the built image into kind for local demo clusters')
    booleanParam(name: 'DEPLOY_MONITORING', defaultValue: true, description: 'Deploy Prometheus and Grafana into Kubernetes with Helm')
    choice(name: 'DEPLOY_ENV', choices: ['dev', 'staging', 'prod'], description: 'Deployment environment')
  }

  environment {
    APP_NAME = 'demo-app'
    IMAGE_TAG = 'pending'
    DOCKER_BUILDKIT = '0'
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
        script {
          env.IMAGE_TAG = "${env.BUILD_NUMBER}-${env.GIT_COMMIT.take(7)}"
        }
      }
    }

    stage('Validate and Test') {
      parallel {
        stage('Unit tests') {
          steps {
            dir('app') {
              sh 'python3 -m venv .venv'
              sh '. .venv/bin/activate && python -m pip install --upgrade pip'
              sh '. .venv/bin/activate && python -m pip install -r requirements.txt -r requirements-dev.txt'
              sh '. .venv/bin/activate && pytest tests --junitxml=pytest-report.xml'
            }
          }
          post {
            always {
              junit allowEmptyResults: true, testResults: 'app/pytest-report.xml'
            }
          }
        }

        stage('Helm chart validation') {
          steps {
            sh 'helm lint helm/demo-app'
            sh 'helm template ${APP_NAME} helm/demo-app --namespace ${KUBE_NAMESPACE} > rendered-manifests.yaml'
            sh 'helm lint helm/monitoring'
            sh 'helm template monitoring helm/monitoring --namespace ${KUBE_NAMESPACE} > rendered-monitoring.yaml'
          }
        }
      }
    }

    stage('Docker Build') {
      steps {
        sh '''
          docker build \
            --label org.opencontainers.image.revision=${GIT_COMMIT} \
            --build-arg APP_VERSION=${IMAGE_TAG} \
            -t ${IMAGE_REPOSITORY}:${IMAGE_TAG} \
            -t ${IMAGE_REPOSITORY}:latest \
            ./app
        '''
      }
    }

    stage('Image Push') {
      steps {
        script {
          if (params.IMAGE_REPOSITORY.startsWith('localhost:5000/')) {
            sh 'docker push ${IMAGE_REPOSITORY}:${IMAGE_TAG}'
            sh 'docker push ${IMAGE_REPOSITORY}:latest'
          } else {
            withCredentials([usernamePassword(credentialsId: 'docker-registry-credentials', usernameVariable: 'REGISTRY_USER', passwordVariable: 'REGISTRY_PASSWORD')]) {
              sh 'echo "$REGISTRY_PASSWORD" | docker login -u "$REGISTRY_USER" --password-stdin'
              sh 'docker push ${IMAGE_REPOSITORY}:${IMAGE_TAG}'
              sh 'docker push ${IMAGE_REPOSITORY}:latest'
            }
          }
        }
      }
    }

    stage('Load image to kind') {
      when {
        expression { return params.LOAD_IMAGE_TO_KIND }
      }
      steps {
        sh 'kind load docker-image ${IMAGE_REPOSITORY}:${IMAGE_TAG} --name ${KIND_CLUSTER_NAME}'
      }
    }

    stage('Deploy to Kubernetes with Helm') {
      steps {
        withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG_FILE')]) {
          sh '''
            export KUBECONFIG=${KUBECONFIG_FILE}
            kubectl create namespace ${KUBE_NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -

            helm upgrade --install ${APP_NAME} helm/demo-app \
              --namespace ${KUBE_NAMESPACE} \
              --set image.repository=${IMAGE_REPOSITORY} \
              --set image.tag=${IMAGE_TAG} \
              --set app.env=${DEPLOY_ENV} \
              --set app.version=${IMAGE_TAG} \
              --wait \
              --timeout 120s

            kubectl -n ${KUBE_NAMESPACE} rollout status deployment/${APP_NAME} --timeout=120s
          '''
        }
      }
    }

    stage('Deploy monitoring to Kubernetes') {
      when {
        expression { return params.DEPLOY_MONITORING }
      }
      steps {
        withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG_FILE')]) {
          sh '''
            export KUBECONFIG=${KUBECONFIG_FILE}

            helm upgrade --install monitoring helm/monitoring \
              --namespace ${KUBE_NAMESPACE} \
              --wait \
              --timeout 180s

            kubectl -n ${KUBE_NAMESPACE} rollout status deployment/prometheus --timeout=120s
            kubectl -n ${KUBE_NAMESPACE} rollout status deployment/grafana --timeout=120s
            kubectl -n ${KUBE_NAMESPACE} rollout status daemonset/node-exporter --timeout=120s
          '''
        }
      }
    }
  }

  post {
    success {
      echo "Deployment completed for ${IMAGE_REPOSITORY}:${IMAGE_TAG}"
    }
    failure {
      echo 'Pipeline failed. Collecting Kubernetes context for troubleshooting.'
      withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG_FILE')]) {
        sh '''
          export KUBECONFIG=${KUBECONFIG_FILE}
          kubectl -n ${KUBE_NAMESPACE} get pods,svc,deploy,hpa || true
          helm -n ${KUBE_NAMESPACE} history ${APP_NAME} || true
          helm -n ${KUBE_NAMESPACE} history monitoring || true
          kubectl -n ${KUBE_NAMESPACE} describe deployment/${APP_NAME} || true
          kubectl -n ${KUBE_NAMESPACE} describe deployment/prometheus || true
          kubectl -n ${KUBE_NAMESPACE} describe deployment/grafana || true
        '''
      }
    }
    cleanup {
      sh 'docker logout || true'
    }
  }
}
