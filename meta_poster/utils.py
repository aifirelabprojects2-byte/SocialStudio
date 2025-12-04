# meta_poster/utils.py
from typing import Optional, List

def build_caption(text: str, hashtags: Optional[List[str]] = None) -> str:
    """Clean text + append hashtags"""
    base = text.strip()
    if not hashtags:
        return base
    
    clean_tags = []
    for tag in hashtags:
        tag = tag.replace(" ", "").strip("# ").strip()
        if tag:
            clean_tags.append(f"#{tag}")
    
    if clean_tags:
        base += "\n" + " ".join(clean_tags)  # New line for better readability
    return base