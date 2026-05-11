# callosum/core/economic/profiler.py

"""Economic Profiler main implementation."""

import random
from typing import List, Tuple
from callosum.common.config import Settings
from callosum.common.utils import estimate_tokens
from callosum.common.logging import logger
from callosum.schemas.prompt import PromptBlock


class EconomicProfiler:
    """Decide whether reordering is economically justified.

    Core principle:能省则省，省不了绝不硬省，绝对不牺牲质量。
    Uses Bayesian self-calibrating thresholds with hard clamping and
    Epsilon-Greedy exploration to prevent death spiral and adapt to changing conditions.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._threshold: float = settings.initial_min_savings
        self._skip_tokens: int = settings.initial_skip_tokens
        self._force_reorder_probe: bool = False

    def should_reorder(self, blocks: List[PromptBlock], total_tokens: int) -> Tuple[bool, int]:
        """
        Determine if reordering should proceed.

        Args:
            blocks: Original prompt blocks.
            total_tokens: Estimated total token count.

        Returns:
            Tuple of (should_reorder: bool, estimated_savings: int)
        """
        # Force probe if Epsilon-Greedy exploration triggered
        if self._force_reorder_probe:
            logger.info("Forcing reorder probe (Epsilon-Greedy exploration)")
            self._force_reorder_probe = False
            static_tokens = sum(
                estimate_tokens(b.content) for b in blocks if b.volatility and b.volatility.score <= 1
            )
            return True, static_tokens

        # Condition 1: Explicit barrier permits safe reordering (regardless of savings)
        if any(b.contains_barrier for b in blocks):
            logger.debug("Reordering permitted: explicit barrier present")
            static_tokens = sum(
                estimate_tokens(b.content) for b in blocks if b.volatility and b.volatility.score <= 1
            )
            return True, static_tokens

        # Condition 2: All blocks are system or vFD (safe to reorder, regardless of savings)
        if all(b.role in ("system", "vfd") for b in blocks):
            logger.debug("Reordering permitted: all blocks are static")
            static_tokens = sum(
                estimate_tokens(b.content) for b in blocks if b.volatility and b.volatility.score <= 1
            )
            return True, static_tokens

        # Condition 3: Skip if total tokens below dynamic threshold
        if total_tokens < self._skip_tokens:
            logger.debug(
                "Skipping reorder: total tokens below threshold", 
                total=total_tokens, 
                threshold=self._skip_tokens
            )
            return False, 0

        # Condition 4: Compute estimated savings from static portion
        static_tokens = sum(
            estimate_tokens(b.content) for b in blocks if b.volatility and b.volatility.score <= 1
        )
        estimated_savings = static_tokens

        # Condition 5: Savings must exceed dynamic threshold (unless barrier/static-only already matched)
        if estimated_savings < self._threshold:
            logger.debug(
                "Skipping reorder: insufficient savings", 
                savings=estimated_savings, 
                threshold=self._threshold
            )
            return False, estimated_savings

        # Condition 6: User content present but savings justify the risk (rare edge case)
        logger.debug("Reordering permitted: sufficient savings for mixed content")
        return True, estimated_savings

    def update_thresholds(self, observed_hit_rate: float, observed_savings: int):
        """Bayesian self-calibration: update thresholds based on observed data.

        Args:
            observed_hit_rate: Observed cache hit rate for the last request.
            observed_savings: Observed actual token savings for the last request.
        """
        # Bayesian update (simplified: weighted moving average)
        alpha = 0.1  # Learning rate
        self._threshold = (1 - alpha) * self._threshold + alpha * observed_savings

        # Hard clamp: threshold must stay within configured bounds to prevent death spiral
        self._threshold = max(
            self.settings.min_savings_threshold,
            min(self.settings.max_savings_threshold, self._threshold)
        )

        # Epsilon-Greedy: force reorder probe with small probability to explore
        if random.random() < self.settings.epsilon_greedy_probability:
            self._force_reorder_probe = True
            logger.debug("Epsilon-Greedy: scheduled next reorder probe")

        logger.debug(
            "Updated economic thresholds",
            new_threshold=self._threshold,
            observed_savings=observed_savings,
        )
