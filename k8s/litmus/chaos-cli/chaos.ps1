
param(
    [ValidateSet("backend", "frontend", "mongo")]
    [string]$Target = "backend"
)

$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "`n⚡ LitmusChaos CLI Experiment Runner" -ForegroundColor Cyan
Write-Host "Target: $Target`n" -ForegroundColor Yellow

# ── Step 1: Apply RBAC ───────────────────────────────────────────────────────
Write-Host "$([char]10)========================================" -ForegroundColor Cyan
Write-Host " Step 1: Applying Chaos RBAC" -ForegroundColor Cyan
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

# ── Step 4: Clean Previous Engine (if any) ───────────────────────────────────
$engineName = "$Target-pod-delete"
Write-Host "$([char]10)========================================" -ForegroundColor Cyan
Write-Host " Step 4: Cleaning Previous Chaos Engine (if any)..." -ForegroundColor Cyan
Write-Host "========================================$([char]10)" -ForegroundColor Cyan
Write-Host "Checking for existing ChaosEngine '$engineName'..." -ForegroundColor Yellow
$existingEngine = try { kubectl get chaosengine $engineName -n chaos-ns --no-headers 2>$null | Out-String } catch { "" }
Write-Host "Existing engine found: $([char]10)$existingEngine" -ForegroundColor Gray
if (-not [string]::IsNullOrWhiteSpace($existingEngine)) {
    Write-Host "$([char]10)Removing previous ChaosEngine '$engineName'..." -ForegroundColor Yellow
    kubectl delete chaosengine $engineName -n chaos-ns
    Start-Sleep -Seconds 3
}

# ── Step 5: Launch Chaos Experiment ──────────────────────────────────────────
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

# ── Step 6: Monitor Experiment ───────────────────────────────────────────────
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

# ── Step 7: Results ──────────────────────────────────────────────────────────
Write-Host "$([char]10)========================================" -ForegroundColor Cyan
Write-Host " Step 7: Results" -ForegroundColor Cyan
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
