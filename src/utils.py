"""
Utility functions
"""

import re
from .config import SKIP_PATTERNS


def clean_post_text(text: str) -> str:
    """
    Clean post content, remove UI elements
    
    Args:
        text: Raw post text
        
    Returns:
        Cleaned text
    """
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        line = line.strip()
        
        # Skip empty lines
        if not line:
            continue
        
        # Skip single character lines (usually garbage)
        if len(line) <= 2 and not line.isdigit():
            continue
            
        # Skip UI patterns
        if any(pattern in line for pattern in SKIP_PATTERNS):
            continue
            
        # Skip lines that are just numbers (reaction counts)
        if line.replace(',', '').replace('.', '').isdigit():
            continue
            
        # Skip short time strings
        if re.match(r'^\d+\s*(giờ|phút|ngày|tuần|tháng|năm|h|m|d|w)', line, re.IGNORECASE):
            continue
            
        cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)


def extract_snippet(text: str, keyword: str, context_length: int = 150) -> str:
    """
    Extract text snippet containing keyword with context
    
    Args:
        text: Full text
        keyword: Keyword to find
        context_length: Number of characters before/after keyword
        
    Returns:
        Snippet with keyword highlighted by context
    """
    text_lower = text.lower()
    keyword_lower = keyword.lower()
    
    pos = text_lower.find(keyword_lower)
    if pos == -1:
        return text[:context_length * 2]
    
    start = max(0, pos - context_length)
    end = min(len(text), pos + len(keyword) + context_length)
    
    snippet = text[start:end].strip()
    
    # Add ellipsis if truncated
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    
    return snippet


def contains_keyword(text: str, keyword: str) -> bool:
    """
    Check if text contains keyword (case-insensitive)
    
    Args:
        text: Text to search
        keyword: Keyword to find
        
    Returns:
        True if keyword found
    """
    return keyword.lower() in text.lower()
