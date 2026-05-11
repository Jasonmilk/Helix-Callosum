"""YAML-declarative adapter loader."""

import yaml
import importlib
from typing import Dict
from callosum.common.config import Settings
from callosum.common.logging import logger
from .base import BaseAdapter


def load_adapters(config_path: str) -> Dict[str, BaseAdapter]:
    """Load adapters from YAML configuration file.

    Dynamically imports and instantiates adapter classes based on
    the declarative configuration.

    Args:
        config_path: Path to the adapters.yaml configuration file.

    Returns:
        Dictionary of adapter name to adapter instance.
    """
    settings = Settings()
    adapters = {}
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        for name, config in data.get("adapters", {}).items():
            if not config.get("enabled", True):
                logger.info("Skipping disabled adapter", adapter=name)
                continue
            
            # Dynamically import the adapter class
            class_path = config["class_path"]
            module_path, class_name = class_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            adapter_cls = getattr(module, class_name)
            
            # Instantiate the adapter with settings
            adapter = adapter_cls(settings)
            adapters[name] = adapter
            logger.info("Loaded backend adapter", adapter=name, class_path=class_path)
        
        return adapters
    except Exception as e:
        logger.error("Failed to load adapters from configuration", error=str(e))
        raise
