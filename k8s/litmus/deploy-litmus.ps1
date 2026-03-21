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
    Write-Host "`n[Cleanup] Removing chaos engines..." -ForegroundColor Yellow
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
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host " Step 1: Installing LitmusChaos Operator" -ForegroundColor Cyan
    Write-Host "========================================`n" -ForegroundColor Cyan

    # Check if operator is already running
    $existingPods = kubectl get pods -n litmus --no-headers 2>$null | Out-String
    if ($existingPods -match 'chaos-operator') {
        Write-Host "Litmus operator already installed, skipping..." -ForegroundColor Yellow
    } else {
        Write-Host "Applying Litmus operator manifests..." -ForegroundColor Yellow
        kubectl apply -f "$scriptDir\operator-install.yaml"

        Write-Host "Waiting for Litmus operator to be ready..." -ForegroundColor Yellow
        kubectl wait --namespace litmus `
            --for=condition=ready pod `
            --selector=app.kubernetes.io/component=operator `
            --timeout=120s
        Write-Host "Litmus operator is running!" -ForegroundColor Green
    }

    # ── Install Chaos Center (Dashboard) ──────────────────────────────────────
    if (-not $NoDashboard) {
        Write-Host "`n========================================" -ForegroundColor Cyan
        Write-Host " Step 1b: Installing Chaos Center (Dashboard)" -ForegroundColor Cyan
        Write-Host "========================================`n" -ForegroundColor Cyan

        $existingFrontend = kubectl get pods -n litmus -l app.kubernetes.io/component=frontend --no-headers 2>$null | Out-String
        if ($existingFrontend -match 'litmus-frontend') {
            Write-Host "Chaos Center already installed, skipping..." -ForegroundColor Yellow
        } else {
            Write-Host "Deploying Chaos Center components..." -ForegroundColor Yellow
            kubectl apply -f "$scriptDir\chaos-center.yaml"

            Write-Host "Waiting for Chaos Center MongoDB..." -ForegroundColor Yellow
            kubectl wait --namespace litmus `
                --for=condition=ready pod `
                --selector=app.kubernetes.io/component=database `
                --timeout=120s

            Write-Host "Waiting for Auth Server..." -ForegroundColor Yellow
            kubectl wait --namespace litmus `
                --for=condition=ready pod `
                --selector=app.kubernetes.io/component=auth-server `
                --timeout=120s

            Write-Host "Waiting for Litmus Server..." -ForegroundColor Yellow
            kubectl wait --namespace litmus `
                --for=condition=ready pod `
                --selector=app.kubernetes.io/component=server `
                --timeout=180s

            Write-Host "Waiting for Chaos Center Frontend..." -ForegroundColor Yellow
            kubectl wait --namespace litmus `
                --for=condition=ready pod `
                --selector=app.kubernetes.io/component=frontend `
                --timeout=120s

            Write-Host "Chaos Center is running!" -ForegroundColor Green
        }

        # Apply Ingress for dashboard access
        Write-Host "Applying Chaos Center Ingress..." -ForegroundColor Yellow
        kubectl apply -f "$scriptDir\ingress.yaml"

        Write-Host ""
        Write-Host "  ┌────────────────────────────────────────────────┐" -ForegroundColor Green
        Write-Host "  │  Chaos Center Dashboard: http://litmus.local   │" -ForegroundColor Green
        Write-Host "  │  Login: admin / litmus                         │" -ForegroundColor Green
        Write-Host "  │                                                │" -ForegroundColor Green
        Write-Host "  │  Requires:                                     │" -ForegroundColor Green
        Write-Host "  │   1. minikube tunnel (running)                 │" -ForegroundColor Green
        Write-Host "  │   2. hosts file: 127.0.0.1 litmus.local        │" -ForegroundColor Green
        Write-Host "  └────────────────────────────────────────────────┘" -ForegroundColor Green
        Write-Host ""
    }
} else {
    Write-Host "`nSkipping operator installation (--SkipInstall)" -ForegroundColor Yellow
}

# ── Step 2: Apply RBAC ───────────────────────────────────────────────────────
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " Step 2: Applying Chaos RBAC" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

kubectl apply -f "$scriptDir\pod-delete\rbac.yaml"
Write-Host "RBAC created (ServiceAccount: pod-delete-sa)" -ForegroundColor Green

# ── Step 3: Install Pod-Delete Experiment ─────────────────────────────────────
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " Step 3: Installing Pod-Delete Experiment" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

kubectl apply -f "$scriptDir\pod-delete\experiment.yaml"
Write-Host "ChaosExperiment 'pod-delete' installed in chaos-ns" -ForegroundColor Green

# ── Step 4: Pre-flight Checks ────────────────────────────────────────────────
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " Step 4: Pre-flight Checks" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "Verifying target pods are running..." -ForegroundColor Yellow
switch ($Target) {
    "backend"  { $label = "app=chaos-backend" }
    "frontend" { $label = "app=chaos-frontend" }
    "mongo"    { $label = "app=mongo" }
}

$targetPods = kubectl get pods -n chaos-ns -l $label --no-headers | Out-String
if ([string]::IsNullOrWhiteSpace($targetPods)) {
    Write-Host "ERROR: No pods found with label '$label' in chaos-ns!" -ForegroundColor Red
    exit 1
}
Write-Host "Target pods:`n$targetPods" -ForegroundColor White

Write-Host "Current pods in chaos-ns:" -ForegroundColor Yellow
kubectl get pods -n chaos-ns -o wide

# ── Step 5: Clean Previous Engine (if any) ───────────────────────────────────
$engineName = "$Target-pod-delete"
$existingEngine = kubectl get chaosengine $engineName -n chaos-ns --no-headers 2>$null | Out-String
if (-not [string]::IsNullOrWhiteSpace($existingEngine)) {
    Write-Host "`nRemoving previous ChaosEngine '$engineName'..." -ForegroundColor Yellow
    kubectl delete chaosengine $engineName -n chaos-ns
    Start-Sleep -Seconds 3
}

# ── Step 6: Launch Chaos Experiment ──────────────────────────────────────────
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " Step 5: Launching Pod-Delete on $($Target.ToUpper())" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$engineFile = "$scriptDir\pod-delete\engine-$Target.yaml"
if (-not (Test-Path $engineFile)) {
    Write-Host "ERROR: Engine file not found: $engineFile" -ForegroundColor Red
    exit 1
}

kubectl apply -f $engineFile
Write-Host "ChaosEngine '$engineName' created!" -ForegroundColor Green

# ── Step 7: Monitor Experiment ───────────────────────────────────────────────
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " Step 6: Monitoring Experiment" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "Waiting for experiment to complete (timeout: 180s)..." -ForegroundColor Yellow
Write-Host "You can also monitor in another terminal:" -ForegroundColor DarkGray
Write-Host "  kubectl get pods -n chaos-ns -w" -ForegroundColor DarkGray
Write-Host "  kubectl get chaosengine -n chaos-ns" -ForegroundColor DarkGray
Write-Host "  kubectl describe chaosresult -n chaos-ns`n" -ForegroundColor DarkGray

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
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " Results" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "ChaosEngine status:" -ForegroundColor Yellow
kubectl get chaosengine -n chaos-ns

Write-Host "`nChaosResult:" -ForegroundColor Yellow
kubectl get chaosresult -n chaos-ns

Write-Host "`nDetailed result:" -ForegroundColor Yellow
$resultName = kubectl get chaosresult -n chaos-ns --no-headers -o custom-columns=":metadata.name" 2>$null | Out-String
$resultName = $resultName.Trim()
if (-not [string]::IsNullOrWhiteSpace($resultName)) {
    foreach ($r in $resultName -split "`n") {
        $r = $r.Trim()
        if ($r) {
            Write-Host "`n--- $r ---" -ForegroundColor Magenta
            kubectl get chaosresult $r -n chaos-ns -o jsonpath='{.status}' | ConvertFrom-Json | ConvertTo-Json -Depth 5
        }
    }
}

Write-Host "`nPod status after chaos:" -ForegroundColor Yellow
kubectl get pods -n chaos-ns -o wide

# Show Chaos Center reminder
if (-not $NoDashboard) {
    Write-Host "`n  View results in Chaos Center: http://litmus.local" -ForegroundColor Cyan
    Write-Host "  Login: admin / litmus" -ForegroundColor Cyan
}

Write-Host "`nDone!" -ForegroundColor Green
