"""YAML-driven dynamic volatility scoring rule engine."""

import yaml
from typing import Dict, Any
from callosum.common.logging import logger
from callosum.schemas.prompt import VolatilityLevel, PromptBlock
from callosum.schemas.exceptions import CompilationError


class ScoringRuleEngine:
    """YAML-driven dynamic scoring rule engine for prompt block volatility."""

    def __init__(self, rules_path: str):
        self.rules_path = rules_path
        self.rules: Dict[str, Dict[str, Any]] = self._load_rules()

    def _load_rules(self) -> Dict[str, Dict[str, Any]]:
        """Load scoring rules from YAML configuration file."""
        try:
            with open(self.rules_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            
            rules = {}
            for rule in data.get("rules", []):
                role = rule["role"]
                rules[role] = {
                    "score": rule["score"],
                    "reason": rule["reason"],
                }
            
            logger.info("Loaded volatility scoring rules", rules=list(rules.keys()))
            return rules
        except Exception as e:
            logger.error("Failed to load scoring rules, cannot continue", error=str(e))
            raise CompilationError(f"Failed to load scoring rules from {self.rules_path}: {e}")

    def score_block(self, block: PromptBlock) -> VolatilityLevel:
        """Score a prompt block based on its role.

        Args:
            block: Prompt block to score.

        Returns:
            VolatilityLevel with score and reason.
        """
        # Use user rule as fallback for unknown roles
        rule = self.rules.get(
            block.role, 
            self.rules.get("user", {"score": 10, "reason": "dynamic_query"})
        )
        
        return VolatilityLevel(
            score=rule["score"],
            reason=rule["reason"],
        )