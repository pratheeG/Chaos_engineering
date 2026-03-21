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

# ── Step 2: Apply RBAC ───────────────────────────────────────────────────────
Write-Host "$([char]10)========================================" -ForegroundColor Cyan
Write-Host " Step 2: Applying Chaos RBAC" -ForegroundColor Cyan
Write-Host "========================================$([char]10)" -ForegroundColor Cyan

kubectl apply -f "$scriptDir\pod-delete\rbac.yaml"
Write-Host "RBAC created (ServiceAccount: pod-delete-sa)" -ForegroundColor Green

# ── Step 3: Install Pod-Delete Experiment ─────────────────────────────────────
Write-Host "$([char]10)========================================" -ForegroundColor Cyan
Write-Host " Step 3: Installing Pod-Delete Experiment" -ForegroundColor Cyan
Write-Host "========================================$([char]10)" -ForegroundColor Cyan

kubectl apply -f "$scriptDir\pod-delete\experiment.yaml"
Write-Host "ChaosExperiment 'pod-delete' installed in chaos-ns" -ForegroundColor Green

# ── Step 4: Pre-flight Checks ────────────────────────────────────────────────
Write-Host "$([char]10)========================================" -ForegroundColor Cyan
Write-Host " Step 4: Pre-flight Checks" -ForegroundColor Cyan
Write-Host "========================================$([char]10)" -ForegroundColor Cyan

Write-Host "Verifying target pods are running..." -ForegroundColor Yellow
switch ($Target) {
    "backend"  { $label = "app=chaos-backend" }
    "frontend" { $label = "app=chaos-frontend" }
    "mongo"    { $label = "app=mongo" }
}

$targetPods = try { kubectl get pods -n chaos-ns -l $label --no-headers | Out-String } catch { "" }
if ([string]::IsNullOrWhiteSpace($targetPods)) {
    Write-Host "ERROR: No pods found with label '$label' in chaos-ns!" -ForegroundColor Red
    exit 1
}
Write-Host "Target pods:$([char]10)$targetPods" -ForegroundColor White

Write-Host "Current pods in chaos-ns:" -ForegroundColor Yellow
kubectl get pods -n chaos-ns -o wide

# ── Step 5: Clean Previous Engine (if any) ───────────────────────────────────
$engineName = "$Target-pod-delete"
Write-Host "$([char]10)Checking for existing ChaosEngine '$engineName'..." -ForegroundColor Yellow
$existingEngine = try { kubectl get chaosengine $engineName -n chaos-ns --no-headers 2>$null | Out-String } catch { "" }
Write-Host "Existing engine found: $([char]10)$existingEngine" -ForegroundColor Gray
if (-not [string]::IsNullOrWhiteSpace($existingEngine)) {
    Write-Host "$([char]10)Removing previous ChaosEngine '$engineName'..." -ForegroundColor Yellow
    kubectl delete chaosengine $engineName -n chaos-ns
    Start-Sleep -Seconds 3
}

# ── Step 6: Launch Chaos Experiment ──────────────────────────────────────────
Write-Host "$([char]10)========================================" -ForegroundColor Cyan
Write-Host " Step 5: Launching Pod-Delete on $($Target.ToUpper())" -ForegroundColor Cyan
Write-Host "========================================$([char]10)" -ForegroundColor Cyan

$engineFile = "$scriptDir\pod-delete\engine-$Target.yaml"
Write-Host "Using ChaosEngine file: $engineFile" -ForegroundColor Yellow
if (-not (Test-Path $engineFile)) {
    Write-Host "ERROR: Engine file not found: $engineFile" -ForegroundColor Red
    exit 1
}

kubectl apply -f $engineFile
Write-Host "ChaosEngine '$engineName' created!" -ForegroundColor Green

# ── Step 7: Monitor Experiment ───────────────────────────────────────────────
Write-Host "$([char]10)========================================" -ForegroundColor Cyan
Write-Host " Step 6: Monitoring Experiment" -ForegroundColor Cyan
Write-Host "========================================$([char]10)" -ForegroundColor Cyan

Write-Host "Waiting for experiment to complete (timeout: 180s)..." -ForegroundColor Yellow
Write-Host "You can also monitor in another terminal:" -ForegroundColor DarkGray
Write-Host "  kubectl get pods -n chaos-ns -w" -ForegroundColor DarkGray
Write-Host "  kubectl get chaosengine -n chaos-ns" -ForegroundColor DarkGray
Write-Host "  kubectl describe chaosresult -n chaos-ns$([char]10)" -ForegroundColor DarkGray

$elapsed = 0
$maxWait = 180
while ($elapsed -lt $maxWait) {
    Start-Sleep -Seconds 10
    $elapsed += 10

    $engineStatus = kubectl get chaosengine $engineName -n chaos-ns -o jsonpath='{.status.engineStatus}' 2>$null
    $expStatus = kubectl get chaosengine $engineName -n chaos-ns -o jsonpath='{.status.experiments[0].status}' 2>$null

    Write-Host "  [$($elapsed)s] Engine: $engineStatus | Experiment: $expStatus" -ForegroundColor Gray

    if ($engineStatus -eq "completed" -or $engineStatus -eq "stopped") {
        break
    }
}

# ── Step 8: Results ──────────────────────────────────────────────────────────
Write-Host "$([char]10)========================================" -ForegroundColor Cyan
Write-Host " Results" -ForegroundColor Cyan
Write-Host "========================================$([char]10)" -ForegroundColor Cyan

Write-Host "ChaosEngine status:" -ForegroundColor Yellow
kubectl get chaosengine -n chaos-ns

Write-Host "$([char]10)ChaosResult:" -ForegroundColor Yellow
kubectl get chaosresult -n chaos-ns

Write-Host "$([char]10)Detailed result:" -ForegroundColor Yellow
$resultName = kubectl get chaosresult -n chaos-ns --no-headers -o custom-columns=":metadata.name" 2>$null | Out-String
$resultName = $resultName.Trim()
if (-not [string]::IsNullOrWhiteSpace($resultName)) {
    foreach ($r in $resultName -split "`n") {
        $r = $r.Trim()
        if ($r) {
            Write-Host "$([char]10)--- $r ---" -ForegroundColor Magenta
            kubectl get chaosresult $r -n chaos-ns -o jsonpath='{.status}' | ConvertFrom-Json | ConvertTo-Json -Depth 5
        }
    }
}

Write-Host "$([char]10)Pod status after chaos:" -ForegroundColor Yellow
kubectl get pods -n chaos-ns -o wide

# Show Chaos Center reminder
if (-not $NoDashboard) {
    Write-Host "$([char]10)  View results in Chaos Center: http://litmus.local" -ForegroundColor Cyan
    Write-Host "  Login: admin / litmus" -ForegroundColor Cyan
}

Write-Host "$([char]10)Done!" -ForegroundColor Green
