"""FastAPI application entry point for Helix-Callosum gateway (v0.2.0)."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from callosum.common.config import get_settings
from callosum.common.logging import configure_logging, logger
from callosum.common.tracing import extract_trace_id, set_trace_context
from callosum.common.utils import estimate_tokens, compute_sha256
from callosum.core.iceberg.compiler import IcebergCompiler
from callosum.core.vfd.allocator import VFDAllocator
from callosum.core.economic.profiler import EconomicProfiler
from callosum.core.shadow.tracker import ShadowTracker
from callosum.core.adapters.loader import load_adapters
from callosum.core.headers import build_callosum_headers
from callosum.core.composite.pool import BackendPool
from callosum.core.composite.health_monitor import HealthMonitor
from callosum.core.composite.router import CompositeRouter
from callosum.schemas.request import CallosumRequest, CompiledRequest
from callosum.schemas.exceptions import VFDResolutionError
from .middleware import TracingMiddleware

# ── Initialization ──────────────────────────────────────────────

configure_logging()
settings = get_settings()

compiler = IcebergCompiler(settings)
vfd_allocator = VFDAllocator(settings)
economic_profiler = EconomicProfiler(settings)
shadow_tracker = ShadowTracker(settings)
adapters = load_adapters(settings.adapters_config_path)

# ── Composite backend pool (v0.2.0) ─────────────────────────────

backends_pool = BackendPool(settings.backends_config_path)
backends_pool.load()
_use_composite = backends_pool.is_active

if _use_composite:
    health_monitor = HealthMonitor(backends_pool, settings)
    router = CompositeRouter(backends_pool, settings.routing_strategy)
else:
    health_monitor = None
    router = None

# ── FastAPI application ─────────────────────────────────────────

app = FastAPI(
    title="Helix-Callosum",
    description="Context Memory Allocator for AI Agents",
    version="0.2.0",
)

app.add_middleware(TracingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup() -> None:
    """Start background services when the application boots."""
    if health_monitor is not None:
        await health_monitor.start()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    """Gracefully stop background services on shutdown."""
    if health_monitor is not None:
        await health_monitor.stop()


# ── Endpoints ───────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict:
    """Health check endpoint.

    In composite mode, returns health status for every backend in the pool.
    In single-backend mode, returns health status for all registered adapters.
    """
    if _use_composite:
        backend_status = {}
        for entry in backends_pool.entries:
            backend_status[entry.config.name] = {
                "healthy": entry.healthy,
                "latency_ms": round(entry.latency_ms, 1),
                "base_url": entry.config.base_url,
                "adapter": entry.config.adapter,
            }
        return {
            "status": "healthy" if backends_pool.healthy_entries() else "degraded",
            "mode": "composite",
            "backends": backend_status,
        }

    # Single-backend mode (backward compatible)
    adapter_health = {}
    for name, adapter in adapters.items():
        adapter_health[name] = await adapter.health_check()
    return {
        "status": "healthy",
        "mode": "single",
        "adapters": adapter_health,
    }


async def _resolve_vfd_handles(blocks) -> None:
    """Resolve all {@ref} handles in the provided blocks."""
    for block in blocks:
        if block.source and block.source.startswith("{@ref:"):
            content = await vfd_allocator.resolve(block.source)
            block.content = content


def _select_adapter():
    """Select the appropriate adapter for the current request.

    In composite mode, uses the router to pick a healthy backend
    and overrides its base_url dynamically.
    In single-backend mode, returns the default adapter.

    Returns:
        Tuple of (adapter_instance, backend_name).
    """
    if _use_composite:
        selected = router.select()
        if selected is None:
            raise HTTPException(status_code=503, detail="No healthy backend available")
        adapter = adapters.get(selected.config.adapter)
        if adapter is None:
            raise HTTPException(
                status_code=400,
                detail=f"Adapter '{selected.config.adapter}' not found for backend '{selected.config.name}'",
            )
        # Dynamically override base_url for this request only.
        # All adapters expose base_url as a public attribute.
        adapter.base_url = selected.config.base_url.rstrip("/")
        return adapter, selected.config.name

    # Single-backend mode (backward compatible)
    adapter = adapters.get(settings.default_backend)
    if adapter is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown adapter: {settings.default_backend}",
        )
    return adapter, settings.default_backend


@app.post("/v1/compile")
async def compile_prompt(request: Request):
    """Compile a prompt into cache-optimal layout.

    Accepts a CallosumRequest with atomic configuration parameters.
    Returns a CompiledRequest ready for forwarding to the target backend.
    """
    try:
        body = await request.json()
        trace_id = extract_trace_id(dict(request.headers))
        set_trace_context(trace_id)

        callosum_request = CallosumRequest(**body)

        # Step 1: Resolve vFD handles
        vfd_handles = [
            b.source for b in callosum_request.blocks
            if b.source and b.source.startswith("{@ref:")
        ]
        vfd_allocator.lock_generation(vfd_handles)
        await _resolve_vfd_handles(callosum_request.blocks)

        # Step 2: Calculate total tokens for economic decision
        total_tokens = sum(
            estimate_tokens(b.content) for b in callosum_request.blocks
        )

        # Step 3: Economic decision — should we reorder?
        should_reorder, estimated_savings = economic_profiler.should_reorder(
            callosum_request.blocks, total_tokens
        )

        # Step 4: Compile (only if reorder is justified)
        if should_reorder:
            compiled = compiler.compile(callosum_request.blocks)
        else:
            static_blocks = [
                b for b in callosum_request.blocks
                if b.volatility and b.volatility.score <= 1
            ]
            static_text = "".join(b.content for b in static_blocks)
            prefix_hash = compute_sha256(static_text)
            compiled = CompiledRequest(
                blocks=callosum_request.blocks,
                cache_breakpoints=[],
                prefix_hash=prefix_hash,
                total_tokens=total_tokens,
                estimated_savings=0,
            )

        # Step 5: Return compiled request as per contract
        return JSONResponse(content=compiled.model_dump())

    except VFDResolutionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Compilation failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Internal compilation error")
    finally:
        vfd_allocator.unlock_generation()
        await vfd_allocator.evict_lru_if_needed()


@app.post("/v1/chat/completions")
async def proxy_chat_completion(request: Request):
    """Internal endpoint: compile, decide, forward, and return normalized response.

    In composite mode (v0.2.0), the backend is selected dynamically by the
    CompositeRouter. In single-backend mode, the default_backend is used.
    """
    try:
        body = await request.json()
        trace_id = extract_trace_id(dict(request.headers))
        set_trace_context(trace_id)

        callosum_request = CallosumRequest(**body)

        # 1. Resolve vFD handles
        vfd_handles = [
            b.source for b in callosum_request.blocks
            if b.source and b.source.startswith("{@ref:")
        ]
        vfd_allocator.lock_generation(vfd_handles)
        await _resolve_vfd_handles(callosum_request.blocks)

        # 2. Economic decision
        total_tokens = sum(
            estimate_tokens(b.content) for b in callosum_request.blocks
        )
        should_reorder, _ = economic_profiler.should_reorder(
            callosum_request.blocks, total_tokens
        )

        # 3. Compile
        if should_reorder:
            compiled = compiler.compile(callosum_request.blocks)
        else:
            static_blocks = [
                b for b in callosum_request.blocks
                if b.volatility and b.volatility.score <= 1
            ]
            static_text = "".join(b.content for b in static_blocks)
            compiled = CompiledRequest(
                blocks=callosum_request.blocks,
                cache_breakpoints=[],
                prefix_hash=compute_sha256(static_text),
                total_tokens=total_tokens,
                estimated_savings=0,
            )

        # 4. Shadow prediction and icebreaker logic
        if not shadow_tracker.predict_hit(compiled.prefix_hash):
            is_probe = await shadow_tracker.wait_for_icebreaker(compiled.prefix_hash)
            if not is_probe:
                pass  # Recheck after waiting

        # 5. Build headers and select adapter (composite or single)
        callosum_headers = build_callosum_headers(callosum_request, compiled)
        adapter, backend_name = _select_adapter()

        # 6. Forward to backend
        response, cache_trace = await adapter.forward(
            compiled, callosum_request.trace_id, callosum_headers
        )

        # 7. Record statistics and update models
        shadow_tracker.record_cache_interaction(
            cache_trace,
            callosum_request.sandbox_namespace,
            backend_name,
        )
        if cache_trace.hit_verified:
            economic_profiler.update_thresholds(
                1.0,
                cache_trace.saved_tokens_verified or 0,
            )

        shadow_tracker.complete_icebreaker(compiled.prefix_hash)

        return JSONResponse(content=adapter.normalize_response(response))

    except VFDResolutionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Request processing failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Internal processing error")
    finally:
        vfd_allocator.unlock_generation()
        await vfd_allocator.evict_lru_if_needed()


@app.get("/v1/usage-stats")
async def usage_stats(namespace: str = None, model: str = None):
    """Return cache performance statistics.

    In composite mode, the ``model`` query parameter filters by backend name.
    """
    return shadow_tracker.get_stats(namespace, model)


def run_server():
    """Run the Uvicorn server."""
    import uvicorn
    uvicorn.run(
        "callosum.gateway.app:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )
