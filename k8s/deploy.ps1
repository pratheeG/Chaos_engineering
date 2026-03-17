# run.ps1 - Minikube Deploy Script for Chaos POC
$ErrorActionPreference = 'Stop'

Write-Host "Starting Minikube Deployment..." -ForegroundColor Cyan

# 1. Start Minikube
$status = minikube status --format `"`{\`{.Host\`}`}`" 2>$null | Out-String
if ($status -notmatch 'Running') {
    Write-Host "Starting Minikube cluster..." -ForegroundColor Yellow
    minikube start --driver=docker
}

# 2. Addons
Write-Host "Enabling addons..." -ForegroundColor Yellow
minikube addons enable ingress
minikube addons enable metrics-server

# 3. Docker Env
Write-Host "Setting Minikube Docker Env..." -ForegroundColor Yellow
$envLines = minikube -p minikube docker-env --shell powershell
foreach ($line in $envLines) {
    if ($line -match '\$Env:(.*) = "(.*)"') {
        Set-Item -Path "Env:\$($Matches[1])" -Value $Matches[2]
    }
}

# 4. Build Images
Write-Host "Building Backend Image..." -ForegroundColor Yellow
cd ..\backend
docker build -t chaos-backend:latest .

Write-Host "Building Frontend Image..." -ForegroundColor Yellow
cd ..\frontend
docker build -t chaos-frontend:latest .

cd ..\k8s

# 5. Apply Manifests
Write-Host "Applying Kubernetes manifests..." -ForegroundColor Yellow
kubectl apply -f namespace.yaml
Start-Sleep -Seconds 2

kubectl apply -f mongo/
kubectl apply -f backend/
kubectl apply -f frontend/
kubectl apply -f ingress.yaml
kubectl apply -f https://litmuschaos.github.io/litmus/litmus-operator-v3.yaml

# 6. Wait
Write-Host "Waiting for pods to be ready..." -ForegroundColor Yellow
kubectl wait --namespace chaos-ns --for=condition=ready pod --selector=layer=database --timeout=120s
kubectl wait --namespace chaos-ns --for=condition=ready pod --selector=layer=backend --timeout=120s
kubectl wait --namespace chaos-ns --for=condition=ready pod --selector=layer=frontend --timeout=120s

Write-Host "Done!" -ForegroundColor Green

# Unset Docker Env
Write-Host "Restoring Docker Env..." -ForegroundColor DarkGray
$unsetLines = minikube -p minikube docker-env --shell powershell --unset
foreach ($line in $unsetLines) {
    if ($line -match 'Remove-Item Env:\\(.*)') {
        Remove-Item -Path "Env:\$($Matches[1])" -ErrorAction SilentlyContinue
    }
}
