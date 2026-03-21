# 🔥 CLI-Based Chaos Experiment Runner

Automated PowerShell script to run LitmusChaos pod-deletion experiments on Kubernetes targets without using the Chaos Center dashboard.

## Prerequisites

- **Kubernetes Cluster**: Minikube or any K8s cluster (Windows 10/11)
- **Tools**:
  - `kubectl` configured to your cluster
  - `minikube` (if using Minikube)
  - PowerShell 5.1+
- **Deployed Stack**: The chaos-ns namespace with backend/frontend pods running (via `k8s/deploy.ps1`)
- **LitmusChaos Operator**: Installed in the cluster (via `k8s/deploy.ps1`)

## Folder Structure

```
chaos-cli/
├── README.md                 # This file
├── chaos.ps1                 # Main CLI experiment runner script
└── pod-delete/
    ├── rbac.yaml            # ServiceAccount + Role + RoleBinding
    ├── experiment.yaml      # ChaosExperiment definition (pod-delete)
    ├── engine-backend.yaml  # ChaosEngine targeting backend pods
    ├── engine-frontend.yaml # ChaosEngine targeting frontend pods
    └── engine-mongo.yaml    # ChaosEngine targeting MongoDB (deprecated - uses Atlas now)
```

## Quick Start

### 1. Ensure LitmusChaos Operator is Installed

The operator must already be running in your cluster. If not:

```powershell
# From the parent litmus directory
cd ..
kubectl apply -f operator-install.yaml
kubectl wait -n litmus --for=condition=ready pod -l app.kubernetes.io/component=operator --timeout=120s
cd chaos-cli
```

### 2. Run Pod-Delete Experiment on Backend

```powershell
.\chaos.ps1 -Target backend
```

### 3. Run Pod-Delete Experiment on Frontend

```powershell
.\chaos.ps1 -Target frontend
```

### 4. Run Pod-Delete Experiment on MongoDB (optional - no longer needed since using Atlas)

```powershell
.\chaos.ps1 -Target mongo
```

## Script Overview

The `chaos.ps1` script automates the entire workflow:

| Step | Description |
|------|-------------|
| **1** | Applies RBAC (ServiceAccount, Role, RoleBinding) |
| **2** | Installs the Pod-Delete ChaosExperiment definition |
| **3** | Runs pre-flight checks (verifies target pods exist) |
| **4** | Cleans up any previous ChaosEngine instances |
| **5** | Launches the ChaosEngine for the specified target |
| **6** | Monitors experiment execution (180s timeout) |
| **7** | Displays final results (ChaosEngine status, results) |

## Parameters

```powershell
.\chaos.ps1 [-Target <backend|frontend|mongo>]
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `-Target` | `backend` | Pod target for chaos experiment |

## Example Runs

### Scenario 1: Kill Backend Pod (Default)

```powershell
# Deletes the chaos-backend pod, observing recovery
.\chaos.ps1
```

**Expected Behavior:**
- Backend pod is killed and restarts
- UI shows health status: 🔴 DOWN → 🟢 UP (after recovery)
- ProductList shows temporary unavailability

### Scenario 2: Kill Frontend Pod

```powershell
# Deletes the chaos-frontend pod
.\chaos.ps1 -Target frontend
```

**Expected Behavior:**
- Frontend pod is killed and restarts
- UI becomes unreachable briefly
- Service recovers automatically via Kubernetes

### Scenario 3: Chain Multiple Experiments

```powershell
# Run backend experiment
.\chaos.ps1 -Target backend

# Wait for recovery
Start-Sleep -Seconds 30

# Run frontend experiment
.\chaos.ps1 -Target frontend
```

## Manual Monitoring (During Experiment)

While the script runs, you can monitor in another PowerShell terminal:

```powershell
# Watch pod status in real-time
kubectl get pods -n chaos-ns -w

# Check ChaosEngine status
kubectl get chaosengine -n chaos-ns

# View experiment details
kubectl describe chaosengine -n chaos-ns

# See final results
kubectl get chaosresult -n chaos-ns
kubectl describe chaosresult -n chaos-ns
```

## Output Example

```
========================================
 Step 1: Applying Chaos RBAC
========================================
RBAC created (ServiceAccount: pod-delete-sa)

========================================
 Step 2: Installing Pod-Delete Experiment
========================================
ChaosExperiment 'pod-delete' installed in chaos-ns

========================================
 Step 3: Pre-flight Checks
========================================
Verifying target pods are running...
Target pods:
chaos-backend-5b498bdb6b-2lwdl   1/1     Running

========================================
 Step 4: Cleaning Previous Chaos Engine (if any)...
========================================
No existing engine found.

========================================
 Step 5: Launching Pod-Delete on BACKEND
========================================
ChaosEngine 'backend-pod-delete' created!

========================================
 Step 6: Monitoring Experiment
========================================
  [10s] Engine: running | Experiment: running
  [20s] Engine: running | Experiment: running
  [30s] Engine: completed | Experiment: Passed

========================================
 Step 7: Results
========================================
NAME                  NAMESPACE  ENGINE STATUS    ...
backend-pod-delete    chaos-ns   completed        ...
```

## Troubleshooting

### Error: "No pods found with label 'app=chaos-backend'"

**Cause**: Backend pod not running or incorrect label

**Solution**:
```powershell
# Check deployed pods
kubectl get pods -n chaos-ns

# Ensure deployment is running
kubectl get deployment -n chaos-ns
kubectl describe deployment chaos-backend -n chaos-ns
```

### Error: "ChaosExperiment 'pod-delete' not found"

**Cause**: Experiment definition not applied

**Solution**:
```powershell
# Apply the experiment manifest
kubectl apply -f pod-delete/experiment.yaml
```

### Pod Doesn't Recover

**Cause**: Pod might be stuck in CrashLoopBackOff due to MongoDB Atlas connection issues

**Solution**:
```powershell
# Check logs
kubectl logs -n chaos-ns deployment/chaos-backend

# Verify MongoDB Atlas credentials in secret
kubectl get secret -n chaos-ns mongodb-atlas-secret -o yaml

# Restart deployment
kubectl rollout restart deployment/chaos-backend -n chaos-ns
```

### Experiment Times Out

**Cause**: Pod recovery is taking longer than 180 seconds

**Solution**: The script will show the last known status. Check manually:
```powershell
kubectl get chaosresult -n chaos-ns -o wide
```

## YAML Manifests Reference

### rbac.yaml
Creates a ServiceAccount (`pod-delete-sa`) with permissions to:
- Create and manage Pods
- Read ConfigMaps
- Read Events

### experiment.yaml
Defines the ChaosExperiment `pod-delete`:
- **Duration**: 30 seconds
- **Pods**: Randomly deletes target pod
- **Recovery**: Waits for pod to be ready
- **Exit Code**: 0 (will always exit cleanly)

### engine-{target}.yaml
Triggers the experiment on a specific target:
- **engine-backend.yaml**: Targets pods with `app=chaos-backend`
- **engine-frontend.yaml**: Targets pods with `app=chaos-frontend`
- **engine-mongo.yaml**: Targets pods with `app=mongo` (not needed with Atlas)

## Advanced Usage

### Run Multiple Targets in Sequence

```powershell
foreach ($target in @("backend", "frontend")) {
    Write-Host "`nRunning experiment on $target..." -ForegroundColor Cyan
    .\chaos.ps1 -Target $target
    Start-Sleep -Seconds 20  # Wait between runs
}
```

### Suppress Output

```powershell
# Redirect verbose output
.\chaos.ps1 -Target backend 6>$null
```

### Extract Results Programmatically

```powershell
# Check if experiment passed
$result = kubectl get chaosresult -n chaos-ns -o json | ConvertFrom-Json
$finalVerdict = $result.items[0].status.experimentStatus.verdict
Write-Host "Verdict: $finalVerdict"
```

## Next Steps

- **Dashboard**: For visual monitoring, use the Chaos Center dashboard
- **Automation**: Integrate this script into CI/CD pipelines for automated resilience testing
- **Custom Experiments**: Modify YAML manifests to run other LitmusChaos experiments (CPU hog, memory hog, network latency, etc.)

## References

- [LitmusChaos Documentation](https://docs.litmuschaos.io/)
- [Pod-Delete Experiment](https://docs.litmuschaos.io/docs/chaosengine/pod-delete/)
- [Litmus Concepts](https://docs.litmuschaos.io/docs/getstarted/concepts/)
