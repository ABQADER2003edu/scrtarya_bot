import json
import os
from thefuzz import process, fuzz
import difflib

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {"categories": {}}
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def identify_category(text: str) -> tuple:
    """
    Identifies the category based on keywords in the text.
    Returns (category_name, color_id) or (None, None).
    """
    config = load_config()
    categories = config.get("categories", {})
    
    text = text.lower()
    
    # 1. Exact/Keyword match
    for cat_name, info in categories.items():
        for keyword in info.get("keywords", []):
            if keyword.lower() in text:
                return cat_name, info.get("color_id")
    
    # 2. Could add fuzzy match for keywords here if needed
    
    return None, None

def get_all_categories():
    config = load_config()
    return list(config.get("categories", {}).keys())
