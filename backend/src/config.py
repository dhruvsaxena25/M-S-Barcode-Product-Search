import logging.config
import yaml
from pathlib import Path    
from typing import Dict, Any


class ConfigManager:
    @staticmethod
    def setup_logging(config_path: Path = Path("config/logging.yaml")):
        """Initialize logging from YAML config."""
        if config_path.exists():
            with open(config_path, "r") as f:
                logging.config.dictConfig(yaml.safe_load(f))
        else:
            logging.basicConfig(level=logging.INFO)

    @staticmethod
    def load_config() -> Dict[str, Any]:
        return {"log_level": "INFO", "camera_index": 0}
    

