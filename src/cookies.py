"""
Cookie handling module
"""

import json
from pathlib import Path


def load_cookies(cookie_file: str) -> list[dict]:
    """
    Load cookies from JSON file and convert to Playwright format
    
    Args:
        cookie_file: Path to cookie JSON file
        
    Returns:
        List of cookies in Playwright format
    """
    with open(cookie_file, "r", encoding="utf-8") as f:
        cookies = json.load(f)
    
    playwright_cookies = []
    for cookie in cookies:
        pw_cookie = {
            "name": cookie["name"],
            "value": cookie["value"],
            "domain": cookie["domain"],
            "path": cookie.get("path", "/"),
            "secure": cookie.get("secure", True),
            "httpOnly": cookie.get("httpOnly", False),
        }
        
        # Handle sameSite
        same_site = cookie.get("sameSite", "Lax")
        if same_site in ["no_restriction", "None"]:
            pw_cookie["sameSite"] = "None"
        elif same_site in ["lax", "Lax"]:
            pw_cookie["sameSite"] = "Lax"
        elif same_site in ["strict", "Strict"]:
            pw_cookie["sameSite"] = "Strict"
        else:
            pw_cookie["sameSite"] = "Lax"
        
        # Add expires if available
        if "expirationDate" in cookie:
            pw_cookie["expires"] = cookie["expirationDate"]
        
        playwright_cookies.append(pw_cookie)
    
    return playwright_cookies


def validate_cookie_file(cookie_file: str) -> bool:
    """Check if cookie file exists and is valid"""
    path = Path(cookie_file)
    if not path.exists():
        return False
    
    try:
        with open(cookie_file, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        return isinstance(cookies, list) and len(cookies) > 0
    except:
        return False
