# Helix-Callosum

Helix-Callosum: Context Memory Allocator for AI Agents.

A high-performance prefix cache optimizer for LLM inference, designed to maximize cache reuse and reduce inference costs while preserving prompt semantics.

## Features

- **Iceberg Compiler**: Volatility-based prompt reordering to maximize prefix cache reuse
- **vFD Allocator**: Virtual File Descriptor with pluggable LRU/LFU/Hybrid eviction policies
- **Economic Profiler**: Bayesian self-calibrating cost-benefit decision engine
- **Shadow Radix Tree**: Token-level cache hit prediction and TTL self-calibration
- **Multi-backend support**: Native integration with Anthropic, OpenAI, vLLM, and SGLang
- **Full observability**: Structured logging, distributed tracing, and cache performance metrics

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/Jasonmilk/Helix-Callosum.git
cd Helix-Callosum

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies (editable mode with dev tools)
pip install -e ".[dev]"
```

### Configuration

```bash
# Copy example environment file
cp .env.example .env
# Edit .env to add your API keys and configuration
```

### Run the server

```bash
callosum server
```

### Check cache statistics

```bash
callosum stats
```

## Documentation

See the [Engineering Manual](docs/ENGINEERING.md) for detailed design, architecture, and implementation details.

## Development

### Run tests

```bash
# Run all unit tests
pytest -v

# Run with coverage report
pytest --cov=callosum --cov-report=term-missing

# Lint code
ruff check .

# Auto-format code
ruff format .
```

## License

MIT
