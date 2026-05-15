# ⚡ Chaos Engineering POC

> Spring Boot 3.2 · MongoDB · React + TypeScript · LitmusChaos · LangGraph AI Agent

A full-stack chaos engineering platform combining a **target application** (Spring Boot + React) with an **AI-powered orchestration agent** that autonomously plans, executes, observes, and analyses LitmusChaos experiments using a multi-agent LangGraph pipeline.

---

## 🏗️ Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                    Browser (React + TS)                        │
│  SystemStatus ──polls──▶ /actuator/health (5s)                 │
│  ProductList ──────────▶ /api/products                         │
└─────────────────────────┬──────────────────────────────────────┘
                          │ HTTP
┌─────────────────────────▼──────────────────────────────────────┐
│               Spring Boot 3.2 (:8080)                          │
│  GET /api/products        GET /api/products/{id}               │
│  POST /api/products       PUT  /api/products/{id}              │
│  DELETE /api/products/{id}                                     │
│  GET /api/health          GET /actuator/health                 │
│  GET /actuator/metrics                                         │
└─────────────────────────┬──────────────────────────────────────┘
                          │ MongoDB Wire Protocol
┌─────────────────────────▼──────────────────────────────────────┐
│                  MongoDB 7 (:27017)                            │
│                  Database: chaosdb · Collection: products      │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│          AI Chaos Orchestrator (FastAPI :8000 + Streamlit)     │
│                                                                │
│   Supervisor → Planner → Executor → Observer → Feedback        │
│        ↑_______________ human_feedback ____________________↑   │
│                                                                │
│   Tools: LitmusChaos GraphQL · kubectl · Prometheus PromQL    │
│   LLMs:  Groq (llama-3.3-70b) · OpenAI (gpt-4o) · Ollama     │
└────────────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────▼──────────────────────────────────────┐
│           Kubernetes (Minikube / cluster)                      │
│  chaos-ns: backend · frontend · mongo                          │
│  litmus:   LitmusChaos operator + experiments                  │
│  monitoring: Prometheus · Grafana · Node Exporter              │
└────────────────────────────────────────────────────────────────┘
```

---

## 🤖 AI Agent — Multi-Agent Orchestration

The `agent/` directory contains a **LangGraph state machine** that autonomously drives the full chaos lifecycle.

### Agent Graph

```
User Input
    │
    ▼
┌──────────────┐
│  Supervisor  │  ← Routes intent to the right agent
└──────┬───────┘
       │
  ┌────┴──────┬────────────┬──────────┐
  ▼           ▼            ▼          ▼
Planner   Executor    Observer   Feedback
  │           │            │          │
  ▼           ▼            ▼          ▼
(tools)   (tools)      (tools)    (tools)
  │           │            │          │
  └───────────┴────────────┴──────────┘
                    │
              human_feedback  ← interrupt_before here
                    │
                    ▼
               Supervisor (re-routes on resume)
```

### Agents & Responsibilities

| Agent | Role |
|---|---|
| **Supervisor** | Analyses user intent and routes to the appropriate specialist agent |
| **Planner** | Discovers deployments, queries the fault registry, and designs an experiment plan for human review |
| **Executor** | Installs CRDs, generates engine YAMLs via Jinja2 templates, applies them to Kubernetes |
| **Observer** | Queries LitmusChaos results + Kubernetes events + Prometheus metrics to verify outcomes |
| **Feedback** | Provides post-experiment analysis, resilience scoring, and answers follow-up questions |

### Supported Faults (Fault Registry)

| Fault | Description |
|---|---|
| `pod-delete` | Deletes pods to test restart recovery |
| `pod-cpu-hog` | Stresses CPU to test throttling and performance degradation |
| `pod-memory-hog` | Stresses memory to test OOM handling and eviction |

> Adding a new fault requires **zero code changes** — just add an entry to `fault_registry.json` and drop the `.yaml.j2` + `install.yaml` files in `agent/app/fault_configs/`.

### LLM Providers

Configurable via `LLM_PROVIDER` in `.env`:

| Provider | Default Model | Config Key |
|---|---|---|
| **Groq** (default) | `llama-3.3-70b-versatile` | `GROQ_API_KEY` |
| **OpenAI** | `gpt-4o` | `OPENAI_API_KEY` |
| **Ollama** (local) | `llama3` | `OLLAMA_BASE_URL` |

---

## 🚀 Quick Start

### Option A – Local Development (No Docker)

**Prerequisites**: Java 17+, Maven 3.9+, MongoDB running on `localhost:27017`, Node 20+, Python 3.11+

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

# 4. Start AI Agent (new terminal)
cd agent
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
# Agent API available at http://localhost:8000

# 5. Start Streamlit UI (new terminal, same venv)
streamlit run ui.py
# Chat UI available at http://localhost:8501
```

### Option B – Docker Compose (Recommended)

**Prerequisites**: Docker Desktop

**Setup:**

1. Copy `.env.example` to `.env` and fill in your values:
   ```
   DB_PASSWORD=your_mongodb_atlas_password
   LLM_PROVIDER=groq
   GROQ_API_KEY=your_groq_api_key
   ```

2. Build and start all 3 services (backend, frontend, agent):
   ```bash
   docker compose up --build
   ```

**Access:**
| Service | URL |
|---|---|
| React UI | http://localhost |
| Spring Boot API | http://localhost:8080/api/products |
| Spring Actuator | http://localhost:8080/actuator/health |
| Agent API | http://localhost:8000 |
| Agent Chat UI | http://localhost:8501 |

> The backend connects to MongoDB Atlas at: `mongodb+srv://lang_ai_user:<DB_PASSWORD>@langgraph-test.unh8kt7.mongodb.net/chaosdb`

To stop:
```bash
docker compose down          # keep MongoDB data
docker compose down -v       # wipe MongoDB volume too
```

### Option C – Minikube / Kubernetes (Windows)

**Prerequisites**: [Minikube](https://minikube.sigs.k8s.io/docs/start/), [kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl-windows/), Docker Desktop

```powershell
# Run the automated deployment script
cd k8s
.\deploy.ps1
```

The script starts Minikube, enables Nginx Ingress, builds images into Minikube's Docker daemon, and applies all manifests to the `chaos-ns` namespace.

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

To clean up:
```powershell
kubectl delete namespace chaos-ns
```

---

## 📡 API Reference

### Spring Boot Backend (`/api`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/api/products` | List all products (optional `?category=electronics`) |
| `GET`  | `/api/products/{id}` | Get product by ID |
| `GET`  | `/api/products/category/{cat}` | Filter by category |
| `POST` | `/api/products` | Create a product |
| `PUT`  | `/api/products/{id}` | Update a product |
| `DELETE` | `/api/products/{id}` | Delete a product |
| `GET`  | `/api/health` | App-level health |
| `GET`  | `/actuator/health` | Spring Actuator health (includes MongoDB component) |
| `GET`  | `/actuator/metrics` | Micrometer metrics |

### AI Agent API (`/` on port 8000)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/chat` | Unified chat endpoint — plan, execute, observe, or ask follow-ups |
| `GET`  | `/state/{thread_id}` | Inspect the current state of a conversation thread |
| `DELETE` | `/state/{thread_id}` | Reset / clear a conversation thread |
| `GET`  | `/health` | Agent health + active LLM provider |
| `GET`  | `/observer/verify/{experiment_id}` | Directly trigger Observer verification |
| `GET`  | `/k8s/pods` | List pods in a namespace |
| `GET`  | `/k8s/pods/resources` | Pod CPU & memory usage (requires metrics-server) |
| `GET`  | `/k8s/pods/{pod}/events` | Events for a specific pod |
| `GET`  | `/k8s/pods/{pod}/logs` | Logs from a pod container |
| `GET`  | `/k8s/events` | All events in a namespace |
| `POST` | `/k8s/observe` | Run full chaos observation (correlates LitmusChaos + K8s) |

**Chat Request schema:**
```json
{
  "thread_id": "chaos-test-1",
  "message": "I want to test pod-delete on the backend deployment."
}
```

**Chat Response schema:**
```json
{
  "thread_id": "chaos-test-1",
  "status": "waiting_for_user",
  "message": "Here is the experiment plan. Shall I proceed?",
  "active_agent": "supervisor",
  "pending_nodes": ["human_feedback"]
}
```

---

## 🔥 LitmusChaos Experiments

### Suggested Experiments

| Experiment | Target | Expected Observation |
|---|---|---|
| **Pod Delete** | `chaos-backend` | ChaosStatus turns 🔴 DOWN, recovers after restart |
| **CPU Hog** | `chaos-backend` | API latency spikes, health may degrade |
| **Memory Hog** | `chaos-backend` | OOM possible, pod restart observable |
| **Pod Network Loss** | `chaos-backend` | MongoDB connection failures, 503 responses |
| **MongoDB Kill** | `chaos-mongo` | Backend health shows `mongo: DOWN` |

### Install LitmusChaos & Run Experiments (Kubernetes)

All Litmus manifests are in `k8s/litmus/`. Two approaches:

#### ⚡ Approach 1: CLI-Based Runner (Recommended)

```powershell
# 1. Deploy the full stack (includes LitmusChaos operator)
cd k8s
.\deploy.ps1

# 2. Run pod-delete experiment on backend
cd litmus/chaos-cli
.\chaos.ps1 -Target backend

# 3. Run pod-delete experiment on frontend
.\chaos.ps1 -Target frontend
```

For detailed usage, see [`k8s/litmus/chaos-cli/README.md`](k8s/litmus/chaos-cli/README.md)

#### 🎨 Approach 2: Dashboard-Based Runner (Chaos Center)

```powershell
# Install LitmusChaos with Chaos Center dashboard
cd k8s/litmus
.\deploy-litmus.ps1

# Access the dashboard
kubectl port-forward svc/litmus-frontend 9091:9091 -n litmus
# Open http://localhost:9091 (login: admin/litmus)
```

#### 🔧 Manual Step-by-Step

```powershell
# Install Litmus operator
kubectl apply -f k8s/litmus/operator-install.yaml

# Wait for operator to be ready
kubectl wait -n litmus --for=condition=ready pod -l app.kubernetes.io/component=operator --timeout=120s

# Create RBAC + experiment definition
kubectl apply -f k8s/litmus/chaos-cli/pod-delete/rbac.yaml
kubectl apply -f k8s/litmus/chaos-cli/pod-delete/experiment.yaml

# Trigger pod-delete on the backend
kubectl apply -f k8s/litmus/chaos-cli/pod-delete/engine-backend.yaml

# Watch chaos in real time
kubectl get pods -n chaos-ns -w

# Check results
kubectl get chaosresult -n chaos-ns
kubectl describe chaosresult -n chaos-ns
```

### Deploy Monitoring Stack (Prometheus + Grafana)

```powershell
cd k8s/litmus
.\deploy-monitoring.ps1
```

This deploys Prometheus, Grafana, and Node Exporter into the `monitoring` namespace. The Agent's Observer uses Prometheus PromQL to correlate chaos impact with historical metric baselines.

---

## 🗂️ Project Structure

```
chaos_engineering/
├── backend/                        # Spring Boot 3.2 target application
│   ├── src/main/java/com/chaos/app/
│   │   ├── ChaosApp.java
│   │   ├── config/CorsConfig.java
│   │   ├── controller/ProductController.java
│   │   ├── dto/ApiResponse.java
│   │   ├── model/Product.java
│   │   ├── repository/ProductRepository.java
│   │   └── service/ProductService.java      ← seeds 6 products on startup
│   ├── src/main/resources/application.yml
│   ├── pom.xml
│   └── Dockerfile
│
├── frontend/                       # React 18 + TypeScript 5 + Vite 5
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChaosStatus.tsx     ← live health polling (/actuator/health every 5s)
│   │   │   ├── ProductCard.tsx
│   │   │   └── ProductList.tsx
│   │   ├── services/api.ts         ← typed Axios layer
│   │   ├── types/index.ts          ← shared interfaces
│   │   ├── App.tsx
│   │   └── index.css               ← dark glass-morphism theme
│   ├── nginx.conf
│   ├── vite.config.ts
│   └── Dockerfile
│
├── agent/                          # AI Orchestration Agent (Python)
│   ├── app/
│   │   ├── graph/                  # LangGraph state machine
│   │   │   ├── master.py           ← graph builder (all nodes + edges)
│   │   │   ├── state.py            ← ChaosState definition
│   │   │   ├── llm.py              ← LLM provider factory
│   │   │   ├── planner.py          ← planner sub-graph
│   │   │   ├── executor.py         ← executor sub-graph
│   │   │   └── nodes/              ← individual node implementations
│   │   │       ├── supervisor.py
│   │   │       ├── planner.py
│   │   │       ├── executor.py
│   │   │       ├── observer.py
│   │   │       ├── feedback.py
│   │   │       ├── human_feedback.py
│   │   │       └── routing.py
│   │   ├── tools/                  # LangChain tools
│   │   │   ├── litmus.py           ← LitmusChaos GraphQL tools
│   │   │   ├── yaml_builder.py     ← Jinja2 engine YAML generator
│   │   │   ├── observer_tools.py   ← experiment verification tools
│   │   │   ├── k8s_tools.py        ← Kubernetes observation tools
│   │   │   └── config_tool.py      ← cluster config tools
│   │   ├── services/               # Service clients
│   │   │   ├── k8s_client.py       ← Kubernetes API client
│   │   │   ├── litmus_client.py    ← LitmusChaos GraphQL client
│   │   │   ├── observer_service.py ← chaos result correlation service
│   │   │   └── prometheus_client.py← Prometheus PromQL client
│   │   ├── api/                    # FastAPI routes
│   │   │   ├── routes.py           ← /chat, /state, /health, /observer
│   │   │   └── k8s_routes.py       ← /k8s/* observation endpoints
│   │   ├── prompts/
│   │   │   └── chaos_prompts.py    ← all agent system prompts
│   │   ├── fault_configs/          ← Jinja2 templates + install YAMLs
│   │   │   ├── pod-delete-engine.yaml.j2
│   │   │   ├── pod-delete-install.yaml
│   │   │   ├── pod-cpu-hog-engine.yaml.j2
│   │   │   ├── pod-cpu-hog-install.yaml
│   │   │   ├── pod-memory-hog-engine.yaml.j2
│   │   │   └── pod-memory-hog-install.yaml
│   │   ├── fault_registry.json     ← fault catalog (data-driven)
│   │   ├── config.py               ← pydantic-settings config
│   │   └── main.py                 ← FastAPI app entry point
│   ├── ui.py                       ← Streamlit chat interface
│   ├── requirements.txt
│   └── readme.md
│
├── k8s/                            # Kubernetes manifests
│   ├── deploy.ps1                  ← one-shot Minikube deployment script
│   ├── namespace.yaml
│   ├── ingress.yaml
│   ├── backend/                    ← backend K8s manifests
│   ├── frontend/                   ← frontend K8s manifests
│   └── litmus/                     ← LitmusChaos configuration
│       ├── deploy-litmus.ps1       ← Chaos Center setup script
│       ├── deploy-monitoring.ps1   ← Prometheus/Grafana setup script
│       ├── ingress.yaml
│       ├── chaos-cli/              ← CLI-based experiment runner
│       │   ├── README.md
│       │   ├── chaos.ps1
│       │   └── pod-delete/
│       │       ├── rbac.yaml
│       │       ├── experiment.yaml
│       │       ├── engine-backend.yaml
│       │       ├── engine-frontend.yaml
│       │       └── engine-mongo.yaml
│       ├── chaos-center/           ← Chaos Center dashboard manifests
│       └── monitoring/             ← Prometheus + Grafana manifests
│           ├── prometheus/
│           ├── grafana/
│           └── metrics-exporters/
│
├── docker-compose.yml              ← 3 services: backend, frontend, agent
├── .env.example
└── README.md
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Spring Boot 3.2, Spring Data MongoDB, Actuator, Micrometer |
| Database | MongoDB 7 (Atlas or local) |
| Frontend | React 18, TypeScript 5, Vite 5, Axios, react-hot-toast |
| AI Agent | Python 3.11, LangGraph, LangChain, FastAPI, Streamlit |
| LLMs | Groq (llama-3.3-70b), OpenAI (gpt-4o), Ollama (local) |
| Chaos | LitmusChaos 3.x, Jinja2 YAML templating |
| Observability | Prometheus, Grafana, Node Exporter, Kubernetes Events API |
| Container | Docker, Docker Compose |
| Orchestration | Kubernetes (Minikube), Nginx Ingress |
| Tracing | LangSmith (optional) |

---

## ⚙️ Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Description | Default |
|---|---|---|
| `DB_PASSWORD` | MongoDB Atlas password | — |
| `LLM_PROVIDER` | LLM backend: `groq`, `openai`, or `ollama` | `groq` |
| `GROQ_API_KEY` | Groq API key | — |
| `GROQ_MODEL` | Groq model name | `llama-3.3-70b-versatile` |
| `OPENAI_API_KEY` | OpenAI API key | — |
| `OPENAI_MODEL` | OpenAI model name | `gpt-4o` |
| `OLLAMA_BASE_URL` | Ollama server URL | `http://localhost:11434` |
| `OLLAMA_MODEL` | Ollama model name | `llama3` |
| `CHAOS_CENTER_ENDPOINT` | LitmusChaos API endpoint | `http://localhost:9002` |
| `LITMUS_PROJECT_ID` | LitmusChaos project ID | — |
| `LITMUS_ACCESS_TOKEN` | LitmusChaos access token | — |
| `LITMUS_INFRA_ID` | Target infrastructure ID | — |
| `PROMETHEUS_URL` | Prometheus server URL | `http://localhost:9090` |
| `LANGSMITH_TRACING` | Enable LangSmith tracing | `false` |
| `LANGSMITH_API_KEY` | LangSmith API key | — |
