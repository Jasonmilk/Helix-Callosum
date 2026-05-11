# Helix-Callosum v0.2.0

**Helix-Callosum** is the context memory allocator of the Helix ecosystem — a deterministic, protocol‑first prefix cache optimizer that bridges the gap between what an LLM *remembers* and what it *pays for*.

> *Callosum is not a cache. It is a commissural bridge — reordering the past so the future costs less.*

---

## What is Helix-Callosum?

Every LLM request carries a prefix. Most of that prefix is static — system prompts, tool definitions, virtual file descriptors. Yet without intervention, dynamic user content fragments the prefix and destroys cache reuse.

Callosum solves this by treating every prompt as a layered **iceberg**:

| Layer | Content | Volatility |
|:---|:---|:---|
| Deep Ice (static) | System prompts, tool schemas | 0 |
| Mid Water (semi‑static) | Virtual file descriptors, RAG context | 1 |
| Surface (dynamic) | User queries, live data | 10 |

The **Iceberg Compiler** reorders blocks so that static content forms a contiguous prefix — maximising KV Cache hits without altering semantics. A **Shadow Radix Tree** predicts commercial API cache behaviour, an **Economic Profiler** decides *whether* to reorder at all, and a **vFD Allocator** manages external context with request‑boundary eviction.

**New in v0.2.0:** The **Composite Router** can distribute requests across multiple backends (e.g. Tuck, Anthropic, OpenAI) using configurable strategies — **first‑healthy**, **round‑robin**, and **latency‑weighted** — with automatic health monitoring and detailed failure tracking.

The result: **fewer tokens billed, faster time‑to‑first‑token, zero semantic degradation.**

---

## Why Helix-Callosum?

| Problem | Callosum Answer |
|:---|:---|
| LLM API costs scale with prompt length | Static prefix caching eliminates redundant token billing |
| Prefix cache is fragmented by dynamic content | Iceberg Compiler reorders by volatility — static first |
| Manual cache optimisation is brittle | Shadow Radix Tree self‑calibrates TTL from API `usage` fields |
| Reordering risks semantic corruption | Economic Profiler blocks reorder unless safe (barrier, static‑only, or sufficient savings) |
| External data opens prompt injection vectors | Dynamic delimiter padding neutralises escape attacks |
| Multi‑backend setups multiply complexity | YAML‑declarative adapters with abstract base — one interface, any backend |
| Single backend is a single point of failure | Composite Router pools backends, monitors health, fails over automatically |
| Unbalanced traffic hurts latency | Latency‑weighted routing favours faster backends |

---

## Quick Start

### Prerequisites

- Python 3.11+
- One or more LLM backends (Anthropic, OpenAI, vLLM, SGLang, or Tuck proxy)

### Installation

```bash
git clone https://github.com/Jasonmilk/Helix-Callosum.git
cd Helix-Callosum

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -e ".[dev]"

cp .env.example .env
```

### One‑Click Setup & Test

```bash
bash scripts/setup.sh
```

This single command handles everything: virtualenv → dependencies → Tuck check → unit tests → gateway smoke test → Cellrix manifest validation (if Cellrix is installed). The script is designed to be non‑blocking: any optional component (Tuck, Cellrix) that is missing only generates a warning, never a failure.

### Start the Gateway

```bash
callosum server start
```

The gateway listens on `http://0.0.0.0:8687` by default.

### Health Check

```bash
curl http://localhost:8687/health
```

In **single‑backend mode** (default), you get a list of registered adapters and their health.  
In **composite mode** (when `config/backends.yaml` is present and non‑empty), you get per‑backend health status including latency, consecutive failures, and last error.

### Compile a Prompt

```bash
curl -s -X POST http://localhost:8687/v1/compile \
  -H "Content-Type: application/json" \
  -H "X-Trace-Id: demo-001" \
  -d '{
    "blocks": [
      {"content": "System: You are a helpful assistant.", "volatility": {"score": 0, "reason": "system_prompt"}, "role": "system"},
      {"content": "User: What is 2+2?", "volatility": {"score": 10, "reason": "dynamic_query"}, "role": "user"}
    ],
    "trace_id": "demo-001"
  }'
```

Returns a `CompiledRequest` with reordered blocks, prefix hash, and estimated savings.

### View Cache Statistics

```bash
callosum stats show
```

### Enabling Composite Backend Routing

1. Edit `config/backends.yaml` and list your backends:
```yaml
backends:
  - name: tuck
    base_url: http://<tuck-host>:8015/v1
    adapter: openai
    weight: 1.0
    enabled: true
  - name: direct-anthropic
    base_url: https://api.anthropic.com/v1
    adapter: anthropic
    weight: 0.5
    enabled: true
```
2. Set the routing strategy via environment: `CALLOSUM_ROUTING_STRATEGY=latency_weighted` (options: `first_healthy`, `round_robin`, `latency_weighted`).  
3. Restart the gateway. The `/health` endpoint will now show composite mode and detailed health metrics for each backend.

If `config/backends.yaml` is absent or empty, Callosum automatically falls back to the single‑backend mode defined by `CALLOSUM_DEFAULT_BACKEND`.

---

## Core Modules

| Module | Responsibility | Key Algorithm |
|:---|:---|:---|
| **Iceberg Compiler** | Reorder prompt blocks by volatility; inject attention anchors | Barrier detection → YAML scoring → volatility sort → delimiter padding |
| **vFD Allocator** | Resolve `{@ref}` handles; maintain SQLite index; evict at boundaries | WAL‑mode SQLite + pluggable LRU/LFU/Hybrid policies |
| **Economic Profiler** | Decide whether reordering is justified | Bayesian self‑calibration + hard clamp + Epsilon‑Greedy exploration |
| **Shadow Radix Tree** | Predict commercial API cache hits; self‑calibrate TTL | Token‑level path‑compressed radix tree |
| **Composite Router** | Pool multiple backends, health‑monitor, and route by strategy | YAML‑driven pool → HealthMonitor → configurable router (first‑healthy, round‑robin, latency‑weighted) |
| **Adapters** | Abstract multi‑backend differences | YAML‑declarative loader; Anthropic, OpenAI, vLLM, SGLang |
| **Gateway** | HTTP entry point; trace propagation; stats aggregation | FastAPI + structlog + W3C Trace Context |

---

## API Endpoints

| Method | Path | Description |
|:---|:---|:---|
| `GET` | `/health` | Adapter or backend health status (depends on mode); includes failure details in composite mode |
| `POST` | `/v1/compile` | Compile a `CallosumRequest` into `CompiledRequest` |
| `POST` | `/v1/chat/completions` | Full lifecycle: compile → decide → forward → return |
| `GET` | `/v1/usage-stats?namespace=&model=` | Cache performance metrics, filterable |

---

## Repository Layout

```
Helix-Callosum/
├── callosum/
│   ├── gateway/          # FastAPI HTTP entry point + tracing middleware
│   ├── core/
│   │   ├── iceberg/      # Iceberg Compiler + barrier detection + scoring rules
│   │   ├── vfd/          # Virtual File Descriptor allocator + indexer + policies
│   │   ├── economic/     # Economic Profiler (Bayesian decision engine)
│   │   ├── shadow/       # Shadow Radix Tree + tracker + icebreaker manager
│   │   ├── composite/    # Composite backend pool + health monitor + router (v0.2.0)
│   │   └── adapters/     # Abstract base + loader + backend implementations
│   ├── schemas/          # Pydantic DTO contracts (single source of truth)
│   ├── common/           # Config, logging, tracing, utilities
│   └── cli/              # CLI entry points (server, stats)
├── config/
│   ├── adapters.yaml     # Declarative adapter registration
│   ├── scoring_rules.yaml # Volatility scoring rules
│   └── backends.yaml     # Composite backend pool definition (v0.2.0)
├── tests/                # Unit tests (mirrors callosum/)
├── scripts/
│   ├── setup.sh          # One‑click environment setup & test
│   └── test_endpoints.sh # Automated endpoint test suite (tolerates degraded health)
├── docs/
│   └── ENGINEERING.md    # Full engineering manual (4 rounds)
├── .env.example
├── pyproject.toml
└── README.md
```

---

## Quality Gates

```bash
bash scripts/setup.sh         # All in one (pytest + gateway smoke + Cellrix check)
pytest -v                      # 34/34 passing
ruff check .                   # Zero warnings
ruff format . --check          # Consistent formatting
```

---

## Roadmap

| Milestone | Status |
|:---|:---|
| **v0.1.0** — Physical skeleton, DTO contracts, config management | ✅ Complete |
| **v0.1.4** — Iceberg Compiler, vFD, Economic Profiler, Shadow Tree, adapters, gateway | ✅ Complete |
| **v0.2.0** — Composite backend routing, health monitoring, latency‑weighted strategy, enhanced observability | ✅ Complete |
| **v0.3.0** — FlowModus scheduler feedback loop, dynamic weight adjustment | Next |
| **v1.0.0** — Production‑grade memory allocator | Planned |

---

## Documentation

- **[Engineering Manual](docs/ENGINEERING.md)** — Complete design, algorithms, DTO contracts, AI Coder iron laws, and test specifications (4 rounds, 21 chapters).

---

## License

MIT © [Jason Milk](https://github.com/Jasonmilk)

---

*Callosum does not remember for you. It rearranges what you already know so the machine remembers less — and you pay for even less.*
