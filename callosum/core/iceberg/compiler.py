"""Iceberg Compiler main implementation."""

from typing import List
from callosum.common.config import Settings
from callosum.common.utils import estimate_tokens, compute_sha256
from callosum.common.logging import logger
from callosum.schemas.prompt import PromptBlock, VolatilityLevel
from callosum.schemas.request import CompiledRequest
from .barrier import detect_barrier, strip_barrier
from .rules import ScoringRuleEngine


class IcebergCompiler:
    """Compile prompt blocks into cache-optimal layout.

    Reorders prompt blocks by volatility to maximize prefix cache reuse,
    applies dynamic delimiters for external data, and computes cache metadata.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._scoring_engine = ScoringRuleEngine(settings.scoring_rules_path)

    def _score_block(self, block: PromptBlock) -> VolatilityLevel:
        """Score a block using the loaded volatility rules."""
        return self._scoring_engine.score_block(block)

    def _count_tokens(self, content: str) -> int:
        """Count tokens for a block content using rough estimation."""
        return estimate_tokens(content)

    def _apply_dynamic_delimiters(self, content: str) -> str:
        """Wrap external data with tamper-proof delimiters.

        Scans the content for the longest consecutive backtick run (N).
        Uses N+1 backticks as the delimiter to guarantee the content
        cannot contain the closing marker. This is a pure string-structure
        operation — no semantic understanding required.
        """
        max_backticks = 0
        current_run = 0
        for ch in content:
            if ch == '`':
                current_run += 1
                max_backticks = max(max_backticks, current_run)
            else:
                current_run = 0
        
        fence = '`' * max(3, max_backticks + 1)
        return f"<external-data>\n{fence}\n{content}\n{fence}\n</external-data>"

    def compile(self, blocks: List[PromptBlock]) -> CompiledRequest:
        """
        Reorder blocks to maximize prefix cache reuse.

        Args:
            blocks: Original prompt blocks in developer-defined order.

        Returns:
            CompiledRequest with reordered blocks and cache metadata.
        """
        if not blocks:
            return CompiledRequest(
                blocks=[],
                cache_breakpoints=[],
                prefix_hash="",
                total_tokens=0,
                estimated_savings=0,
            )

        # 1. Find first cache barrier
        barrier_index = None
        for i, block in enumerate(blocks):
            if detect_barrier(block.content):
                barrier_index = i
                # Remove barrier marker from content
                block.content = strip_barrier(block.content)
                block.contains_barrier = False
                break

        # 2. Split into reorderable and protected regions
        reorderable = blocks[:barrier_index] if barrier_index is not None else blocks
        protected = blocks[barrier_index:] if barrier_index is not None else []

        # 3. Assign volatility scores using external YAML rules (only if not already set)
        for block in reorderable:
            if block.volatility is None:
                block.volatility = self._score_block(block)

        # 4. Apply delimiter dynamic padding for vFD blocks
        for block in reorderable:
            if block.source and block.source.startswith("{@ref:"):
                block.content = self._apply_dynamic_delimiters(block.content)

        # 5. Sort reorderable blocks by volatility score ascending
        reorderable.sort(key=lambda b: b.volatility.score)

        # 6. Inject attention anchor at the head of deep iceberg layer
        if reorderable and reorderable[0].volatility.score == 0:
            anchor = PromptBlock(
                content="<|attention_anchor|>",
                volatility=VolatilityLevel(score=0, reason="attention_anchor"),
                role="system",
                source=None,
                contains_barrier=False,
            )
            reorderable.insert(0, anchor)

        # 7. Compute cache breakpoints (where volatility score changes)
        breakpoints = []
        compiled_blocks = reorderable + protected
        current_score = None
        token_count = 0
        for i, block in enumerate(compiled_blocks):
            block_tokens = self._count_tokens(block.content)
            if i > 0 and block.volatility.score != current_score:
                breakpoints.append(token_count)
            current_score = block.volatility.score
            token_count += block_tokens

        # 8. Compute prefix hash of static portion (volatility score <= 1)
        static_blocks = [b for b in compiled_blocks if b.volatility.score <= 1]
        static_text = "".join(b.content for b in static_blocks)
        prefix_hash = compute_sha256(static_text)

        # 9. Estimate total tokens and savings
        total_tokens = sum(self._count_tokens(b.content) for b in compiled_blocks)
        static_tokens = sum(self._count_tokens(b.content) for b in static_blocks)
        estimated_savings = static_tokens

        logger.info(
            "Compiled prompt successfully",
            total_blocks=len(blocks),
            reorderable_blocks=len(reorderable),
            protected_blocks=len(protected),
            prefix_hash=prefix_hash,
            estimated_savings=estimated_savings,
        )

        return CompiledRequest(
            blocks=compiled_blocks,
            cache_breakpoints=breakpoints,
            prefix_hash=prefix_hash,
            total_tokens=total_tokens,
            estimated_savings=estimated_savings,
        )