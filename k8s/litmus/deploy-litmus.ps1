# deploy-litmus.ps1 - LitmusChaos Setup & Pod-Delete Experiment Runner
# ──────────────────────────────────────────────────────────────────────
# Prerequisites:
#   - Minikube running with the app deployed (run k8s/deploy.ps1 first)
#   - kubectl configured to the Minikube context
#
# Usage:
#   .\deploy-litmus.ps1                    # Install Litmus + Chaos Center + run backend pod-delete
#   .\deploy-litmus.ps1 -Target frontend   # Run pod-delete on frontend
#   .\deploy-litmus.ps1 -Target mongo      # Run pod-delete on MongoDB
#   .\deploy-litmus.ps1 -SkipInstall       # Skip operator/center install, just run experiment
#   .\deploy-litmus.ps1 -NoDashboard       # Install operator only (no Chaos Center UI)
#   .\deploy-litmus.ps1 -Cleanup           # Remove all chaos resources
# ──────────────────────────────────────────────────────────────────────

param(
    [ValidateSet("backend", "frontend", "mongo")]
    [string]$Target = "backend",

    [switch]$SkipInstall,
    [switch]$NoDashboard,
    [switch]$Cleanup
)

$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# ── Cleanup Mode ──────────────────────────────────────────────────────────────
if ($Cleanup) {
    Write-Host "$([char]10)[Cleanup] Removing chaos engines..." -ForegroundColor Yellow
    kubectl delete chaosengine --all -n chaos-ns 2>$null
    Write-Host "[Cleanup] Removing chaos experiments..." -ForegroundColor Yellow
    kubectl delete chaosexperiment --all -n chaos-ns 2>$null
    Write-Host "[Cleanup] Removing chaos results..." -ForegroundColor Yellow
    kubectl delete chaosresult --all -n chaos-ns 2>$null
    Write-Host "[Cleanup] Removing RBAC..." -ForegroundColor Yellow
    kubectl delete -f "$scriptDir\pod-delete\rbac.yaml" 2>$null
    Write-Host "[Cleanup] Done!" -ForegroundColor Green
    exit 0
}

# ── Step 1: Install Litmus Operator ───────────────────────────────────────────
if (-not $SkipInstall) {
    Write-Host "$([char]10)========================================" -ForegroundColor Cyan
    Write-Host " Step 1: Installing LitmusChaos Operator" -ForegroundColor Cyan
    Write-Host "========================================$([char]10)" -ForegroundColor Cyan

    helm repo add litmuschaos https://litmuschaos.github.io/litmus-helm/
    helm repo list

    kubectl create ns litmus

    helm install chaos litmuschaos/litmus --namespace=litmus --set portal.frontend.service.type=NodePort
    
    Write-Host "Waiting for Litmus pods to initialize..." -ForegroundColor Yellow
    # TODO UnComment the below code and remove the static sleep once the operator is stable and ready to create the ChaosCenter resources
    # Start-Sleep -Seconds 20

    kubectl apply -f ingress.yaml
    
    # Port-forward to allow access via localhost:9091
    Write-Host "Setting up port-forward to expose Litmus on localhost:9091..." -ForegroundColor Yellow
    Start-Job -ScriptBlock {
        kubectl port-forward svc/chaos-litmus-frontend-service 9091:9091 -n litmus
    } | Out-Null

    Write-Host "Installation complete!" -ForegroundColor Green
    Write-Host "Access Litmus via:" -ForegroundColor Green
    Write-Host "  1. Ingress (Domain):  http://litmus.local" -ForegroundColor Cyan
    Write-Host "  2. Port-forward:      http://localhost:9091" -ForegroundColor Cyan
    Write-Host "Default credentials: admin / litmus" -ForegroundColor Green
} else {
    Write-Host ([environment]::NewLine + 'Skipping operator installation (--SkipInstall)') -ForegroundColor Yellow
}