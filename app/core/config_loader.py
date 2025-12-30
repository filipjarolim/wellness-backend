import json
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("app")

CONFIG_PATH = "data/company_config.json"

def load_company_config() -> Dict[str, Any]:
    """
    Loads company configuration from JSON file.
    Raises FileNotFoundError if config is missing.
    Returns: Dict containing config.
    """
    if not os.path.exists(CONFIG_PATH):
        logger.critical(f"❌ Křehká chyba: Konfigurační soubor '{CONFIG_PATH}' nebyl nalezen! Aplikace nemůže startovat.")
        raise FileNotFoundError(f"Configuration file not found at {CONFIG_PATH}")

    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
            logger.info(f"✅ Konfigurace načtena pro: {config.get('company_name', 'Unknown')}")
            return config
    except json.JSONDecodeError as e:
        logger.critical(f"❌ Chyba parsování JSON konfigurace: {e}")
        raise ValueError(f"Invalid JSON in config file: {e}")
    except Exception as e:
        logger.critical(f"❌ Neočekávaná chyba při načítání konfigurace: {e}")
        raise e

def get_business_hours(config: Dict[str, Any], day_name: str) -> Optional[Dict[str, str]]:
    """
    Helper to get business hours for a specific day (monday, tuesday...).
    Returns: Dict {'start': 'HH:MM', 'end': 'HH:MM'} or None if closed.
    """
    hours = config.get("business_hours", {})
    return hours.get(day_name.lower())
