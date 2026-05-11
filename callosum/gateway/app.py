"""FastAPI application entry point for Helix-Callosum gateway."""

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
from callosum.schemas.request import CallosumRequest, CompiledRequest
from callosum.schemas.exceptions import VFDResolutionError
from .middleware import TracingMiddleware

# Initialize logging and settings
configure_logging()
settings = get_settings()

# Initialize core components
compiler = IcebergCompiler(settings)
vfd_allocator = VFDAllocator(settings)
economic_profiler = EconomicProfiler(settings)
shadow_tracker = ShadowTracker(settings)
adapters = load_adapters(settings.adapters_config_path)

# Create FastAPI app
app = FastAPI(
    title="Helix-Callosum",
    description="Context Memory Allocator for AI Agents",
    version="0.1.0",
)

# Add middleware
app.add_middleware(TracingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """Health check endpoint."""
    adapter_health = {}
    for name, adapter in adapters.items():
        adapter_health[name] = await adapter.health_check()
    
    return {
        "status": "healthy",
        "adapters": adapter_health,
    }


async def _resolve_vfd_handles(blocks):
    """Resolve all {@ref} handles in the provided blocks."""
    for block in blocks:
        if block.source and block.source.startswith("{@ref:"):
            content = await vfd_allocator.resolve(block.source)
            block.content = content


@app.post("/v1/compile")
async def compile_prompt(request: Request):
    """Compile a prompt into cache‑optimal layout.

    Accepts a CallosumRequest with atomic configuration parameters.
    Returns a CompiledRequest ready for forwarding to the target backend.
    """
    try:
        body = await request.json()
        trace_id = extract_trace_id(dict(request.headers))
        set_trace_context(trace_id)

        callosum_request = CallosumRequest(**body)

        # Step 1: Resolve vFD handles
        vfd_handles = [b.source for b in callosum_request.blocks if b.source and b.source.startswith("{@ref:")]
        vfd_allocator.lock_generation(vfd_handles)
        await _resolve_vfd_handles(callosum_request.blocks)

        # Step 2: Calculate total tokens for economic decision
        total_tokens = sum(estimate_tokens(b.content) for b in callosum_request.blocks)

        # Step 3: Economic decision — should we reorder?
        should_reorder, estimated_savings = economic_profiler.should_reorder(
            callosum_request.blocks, total_tokens
        )

        # Step 4: Compile (only if reorder is justified)
        if should_reorder:
            compiled = compiler.compile(callosum_request.blocks)
        else:
            # Must still compute prefix hash and breakpoints for non-reordered blocks
            static_blocks = [b for b in callosum_request.blocks if b.volatility and b.volatility.score <= 1]
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

    This is the main HTTP proxy that handles the full lifecycle.
    """
    try:
        body = await request.json()
        trace_id = extract_trace_id(dict(request.headers))
        set_trace_context(trace_id)

        callosum_request = CallosumRequest(**body)

        # 1. Resolve vFD handles
        vfd_handles = [b.source for b in callosum_request.blocks if b.source and b.source.startswith("{@ref:")]
        vfd_allocator.lock_generation(vfd_handles)
        await _resolve_vfd_handles(callosum_request.blocks)

        # 2. Economic decision
        total_tokens = sum(estimate_tokens(b.content) for b in callosum_request.blocks)
        should_reorder, _ = economic_profiler.should_reorder(callosum_request.blocks, total_tokens)

        # 3. Compile
        if should_reorder:
            compiled = compiler.compile(callosum_request.blocks)
        else:
            static_blocks = [b for b in callosum_request.blocks if b.volatility and b.volatility.score <= 1]
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
                # Recheck after waiting
                pass

        # 5. Build headers and select adapter
        callosum_headers = build_callosum_headers(callosum_request, compiled)
        adapter = adapters.get(settings.default_backend)
        if not adapter:
            raise HTTPException(status_code=400, detail=f"Unknown adapter: {settings.default_backend}")

        # 6. Forward to backend
        response, cache_trace = await adapter.forward(
            compiled, callosum_request.trace_id, callosum_headers
        )

        # 7. Record statistics and update models
        shadow_tracker.record_cache_interaction(
            cache_trace, callosum_request.sandbox_namespace, adapter.get_adapter_name()
        )
        if cache_trace.hit_verified:
            economic_profiler.update_thresholds(1.0, cache_trace.saved_tokens_verified or 0)

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
    """Return cache performance statistics."""
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