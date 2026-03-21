# ⚡ Chaos Engineering POC

> Spring Boot 3.2 · MongoDB · React + TypeScript · LitmusChaos

A full-stack demo application purpose-built for **Chaos Engineering experiments** using [LitmusChaos](https://litmuschaos.io). The system exposes Spring Boot Actuator health endpoints that the React UI polls in real time, so you can visually observe service disruptions during chaos runs.

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────┐
│                  Browser (React + TS)             │
│  ChaosStatus ──polls──▶ /actuator/health (5s)     │
│  ProductList ──────────▶ /api/products            │
└───────────────────┬──────────────────────────────┘
                    │ HTTP
┌───────────────────▼──────────────────────────────┐
│          Spring Boot 3.2 (:8080)                  │
│  GET /api/products     GET /api/products/{id}     │
│  GET /api/health       POST /api/products         │
│  GET /actuator/health  GET /actuator/metrics      │
└───────────────────┬──────────────────────────────┘
                    │ MongoDB Wire Protocol
┌───────────────────▼──────────────────────────────┐
│              MongoDB 7 (:27017)                   │
│              Database: chaosdb                    │
│              Collection: products                 │
└──────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Option A – Local Development (No Docker)

**Prerequisites**: Java 17+, Maven 3.9+, MongoDB running on `localhost:27017`, Node 20+

```bash
# 1. Start MongoDB (if not running)
mongod --dbpath /data/db

# 2. Start Spring Boot backend
cd backend
mvn spring-boot:run
# API available at http://localhost:8080

# 3. Start React frontend (new terminal)
cd frontend
npm install
npm run dev
# UI available at http://localhost:5173
```

### Option B – Docker Compose (Recommended)

**Prerequisites**: Docker Desktop

```bash
# Build and start all 3 services
docker compose up --build

# UI:     http://localhost
# API:    http://localhost:8080/api/products
# Health: http://localhost:8080/actuator/health
```

To stop:
```bash
docker compose down          # keep MongoDB data
docker compose down -v       # wipe MongoDB volume too
```

### Option C – Minikube / Kubernetes (Windows)

We provide raw Kubernetes manifests and a one-shot PowerShell script that builds the images directly into Minikube's Docker daemon.

**Prerequisites**: [Minikube](https://minikube.sigs.k8s.io/docs/start/), [kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl-windows/), Docker Desktop

```powershell
# Run the automated deployment script
cd k8s
.\deploy.ps1
```

The script will automatically start Minikube, enable Nginx Ingress, build the images, and apply the manifests to the `chaos-ns` namespace.

**Post-Deploy Windows Steps:**
1. Open a **new Administrator Terminal** and run:
   ```powershell
   minikube tunnel
   ```
   *(Keep this terminal open)*
2. Open `C:\Windows\System32\drivers\etc\hosts` as Administrator and add:
   ```
   127.0.0.1    chaos.local
   ```
3. Access the app at **http://chaos.local**

To clean up the Kubernetes resources:
```powershell
kubectl delete namespace chaos-ns
```

---

## 📡 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/products` | List all products (optional `?category=electronics`) |
| `GET`  | `/api/products/{id}` | Get product by ID |
| `GET`  | `/api/products/category/{cat}` | Filter by category |
| `POST` | `/api/products` | Create a product |
| `PUT`  | `/api/products/{id}` | Update a product |
| `DELETE` | `/api/products/{id}` | Delete a product |
| `GET`  | `/api/health` | App-level health |
| `GET`  | `/actuator/health` | Spring Actuator health (includes MongoDB) |
| `GET`  | `/actuator/metrics` | Micrometer metrics |

---

## 🔥 LitmusChaos Experiments

The backend container is labelled with `litmuschaos.io/chaos: "true"` in docker-compose.yml.  
For Kubernetes deployments, apply the same labels to your Pod spec and use the experiments below:

### Suggested Experiments

| Experiment | Target | Expected Observation |
|---|---|---|
| **Pod Kill** | `chaos-backend` | ChaosStatus turns 🔴 DOWN, recovers after restart |
| **CPU Hog** | `chaos-backend` | API latency spikes, health may degrade |
| **Memory Hog** | `chaos-backend` | OOM possible, pod restart observable |
| **Pod Network Loss** | `chaos-backend` | MongoDB connection failures, 503 responses |
| **MongoDB Kill** | `chaos-mongo` | Backend health shows `mongo: DOWN` |
| **Network Latency** | `chaos-net` | Slow API responses visible in UI |

### Install LitmusChaos & Run Pod-Delete (Kubernetes)

All Litmus manifests are in `k8s/litmus/`. A single PowerShell script handles installation, RBAC, experiment setup, and execution.

```powershell
# 1. Install Litmus operator + Chaos Center + run pod-delete on the BACKEND (default)
cd k8s/litmus
.\deploy-litmus.ps1

# 2. Run pod-delete on FRONTEND (operator already installed)
.\deploy-litmus.ps1 -Target frontend -SkipInstall

# 3. Run pod-delete on MONGODB
.\deploy-litmus.ps1 -Target mongo -SkipInstall

# 4. Install without dashboard (operator-only, CLI mode)
.\deploy-litmus.ps1 -NoDashboard

# 5. Clean up all chaos resources
.\deploy-litmus.ps1 -Cleanup
```

### Chaos Center Dashboard

The script installs **Chaos Center** — a web dashboard to schedule, visualize, and monitor all chaos experiments.

**Access the Dashboard:**
```powershell
# Option 1: Use minikube service
minikube service litmus-frontend -n litmus

# Option 2: Port-forward
kubectl port-forward svc/litmus-frontend 9091:9091 -n litmus
# Then open http://localhost:9091
```

**Default login:** `admin` / `litmus`

From the dashboard you can:
- Connect your cluster as a Chaos Infrastructure
- Schedule and run experiments (pod-delete, network chaos, CPU hog, etc.)
- View real-time experiment progress and logs
- Analyze resilience scores and past experiment results

**Manual step-by-step (if you prefer):**

```powershell
# Install Litmus operator (creates 'litmus' namespace)
kubectl apply -f k8s/litmus/operator-install.yaml

# Wait for operator
kubectl wait -n litmus --for=condition=ready pod -l app.kubernetes.io/component=operator --timeout=120s

# Create RBAC + experiment definition
kubectl apply -f k8s/litmus/pod-delete/rbac.yaml
kubectl apply -f k8s/litmus/pod-delete/experiment.yaml

# Trigger pod-delete on the backend
kubectl apply -f k8s/litmus/pod-delete/engine-backend.yaml

# Watch the chaos
kubectl get pods -n chaos-ns -w

# Check results
kubectl get chaosresult -n chaos-ns
kubectl describe chaosresult -n chaos-ns
```

#### Litmus File Structure

```
k8s/litmus/
├── operator-install.yaml              # CRDs, operator deployment, RBAC
├── chaos-center.yaml                  # Chaos Center dashboard (UI + API + Auth + Mongo)
├── deploy-litmus.ps1                  # Automated setup & run script
└── pod-delete/
    ├── rbac.yaml                      # ServiceAccount + Role + RoleBinding
    ├── experiment.yaml                # ChaosExperiment definition
    ├── engine-backend.yaml            # ChaosEngine → backend pods
    ├── engine-frontend.yaml           # ChaosEngine → frontend pods
    └── engine-mongo.yaml              # ChaosEngine → MongoDB pods
```

---

## 🗂️ Project Structure

```
Chaos Engineering/
├── backend/                  # Spring Boot 3.2
│   ├── src/main/java/com/chaos/app/
│   │   ├── ChaosApp.java
│   │   ├── config/CorsConfig.java
│   │   ├── controller/ProductController.java
│   │   ├── dto/ApiResponse.java
│   │   ├── model/Product.java
│   │   ├── repository/ProductRepository.java
│   │   └── service/ProductService.java     ← seeds 6 products on startup
│   ├── src/main/resources/application.yml
│   ├── pom.xml
│   └── Dockerfile
├── frontend/                 # React 18 + TypeScript 5 + Vite 5
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChaosStatus.tsx    ← live health polling
│   │   │   ├── ProductCard.tsx
│   │   │   └── ProductList.tsx
│   │   ├── services/api.ts        ← typed Axios layer
│   │   ├── types/index.ts         ← shared interfaces
│   │   ├── App.tsx
│   │   └── index.css              ← dark glass-morphism theme
│   ├── nginx.conf
│   ├── vite.config.ts
│   └── Dockerfile
├── k8s/
│   ├── deploy.ps1                 # Main Minikube deployment script
│   ├── namespace.yaml
│   ├── ingress.yaml
│   ├── backend/                   # Backend K8s manifests
│   ├── frontend/                  # Frontend K8s manifests
│   ├── mongo/                     # MongoDB K8s manifests
│   └── litmus/                    # LitmusChaos configuration
│       ├── operator-install.yaml
│       ├── chaos-center.yaml      # Dashboard UI + API stack
│       ├── deploy-litmus.ps1
│       └── pod-delete/            # Pod-delete experiment
│           ├── rbac.yaml
│           ├── experiment.yaml
│           ├── engine-backend.yaml
│           ├── engine-frontend.yaml
│           └── engine-mongo.yaml
├── docker-compose.yml
└── README.md
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Spring Boot 3.2, Spring Data MongoDB, Actuator |
| Database | MongoDB 7 |
| Frontend | React 18, TypeScript 5, Vite 5, Axios |
| Container | Docker, Docker Compose |
| Chaos | LitmusChaos 3.x |
