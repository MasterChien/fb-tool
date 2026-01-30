"""
MongoDB database module for storing scan results
"""

import os
from datetime import datetime
from typing import Optional
from rich.console import Console

console = Console(force_terminal=True)

# Collection names
COLLECTION_POSTS = "posts"
COLLECTION_SCANS = "scans"

# Default settings (will be overridden by db_config.txt)
MONGO_URI = "mongodb://localhost:27017"
MONGO_DB = "fb-scan-post"

_client = None
_db = None
_config_loaded = False


def _load_db_config():
    """Load MongoDB config from db_config.txt"""
    global MONGO_URI, MONGO_DB, _config_loaded
    
    if _config_loaded:
        return
    
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db_config.txt")
    
    if not os.path.exists(config_path):
        console.print(f"[yellow]Khong tim thay db_config.txt, dung config mac dinh[/yellow]")
        _config_loaded = True
        return
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip().lower()
                    value = value.strip()
                    
                    if key == "mongo_uri":
                        MONGO_URI = value
                    elif key == "mongo_db":
                        MONGO_DB = value
        
        _config_loaded = True
    except Exception as e:
        console.print(f"[yellow]Loi doc db_config.txt: {e}[/yellow]")


def get_db():
    """Get MongoDB database connection (lazy initialization)"""
    global _client, _db
    
    # Load config from file first
    _load_db_config()
    
    if _db is None:
        try:
            from pymongo import MongoClient
            _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            # Test connection
            _client.admin.command('ping')
            _db = _client[MONGO_DB]
            console.print(f"[green][OK][/green] Da ket noi MongoDB: {MONGO_DB}")
        except Exception as e:
            console.print(f"[red][X] Loi ket noi MongoDB: {e}[/red]")
            return None
    
    return _db


def close_db():
    """Close MongoDB connection"""
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None


def save_post_to_db(
    post: dict,
    group_id: str,
    keyword: str,
    scan_id: str = None
) -> Optional[str]:
    """
    Save a single post to MongoDB
    
    Args:
        post: Post data dictionary
        group_id: Facebook group ID
        keyword: Matched keyword
        scan_id: Optional scan session ID
        
    Returns:
        Inserted document ID or None if failed
    """
    db = get_db()
    if db is None:
        return None
    
    try:
        doc = {
            "group_id": group_id,
            "keyword": keyword,
            "author": post.get("author", "Unknown"),
            "author_link": post.get("author_link", ""),
            "snippet": post.get("snippet", ""),
            "link": post.get("link", ""),
            "full_text": post.get("full_text", ""),
            "found_at": post.get("found_at", datetime.now().isoformat()),
            "created_at": datetime.now(),
            "scan_id": scan_id
        }
        
        # Upsert based on full_text hash to avoid duplicates
        content_hash = hash(doc["full_text"][:500]) if doc["full_text"] else None
        if content_hash:
            doc["content_hash"] = content_hash
            result = db[COLLECTION_POSTS].update_one(
                {"content_hash": content_hash, "group_id": group_id},
                {"$set": doc},
                upsert=True
            )
            return str(result.upserted_id) if result.upserted_id else "updated"
        else:
            result = db[COLLECTION_POSTS].insert_one(doc)
            return str(result.inserted_id)
            
    except Exception as e:
        console.print(f"[red]Loi luu post vao MongoDB: {e}[/red]")
        return None


def save_posts_to_db(
    posts: list[dict],
    group_id: str,
    keyword: str,
    scan_id: str = None
) -> int:
    """
    Save multiple posts to MongoDB
    
    Args:
        posts: List of post dictionaries
        group_id: Facebook group ID
        keyword: Matched keyword
        scan_id: Optional scan session ID
        
    Returns:
        Number of posts saved/updated
    """
    if not posts:
        return 0
    
    db = get_db()
    if db is None:
        return 0
    
    saved_count = 0
    for post in posts:
        result = save_post_to_db(post, group_id, keyword, scan_id)
        if result:
            saved_count += 1
    
    return saved_count


def save_scan_session(
    config_summary: dict,
    results_summary: dict
) -> Optional[str]:
    """
    Save scan session metadata to MongoDB
    
    Args:
        config_summary: Configuration used for scan
        results_summary: Summary of scan results
        
    Returns:
        Scan session ID or None if failed
    """
    db = get_db()
    if db is None:
        return None
    
    try:
        doc = {
            "started_at": datetime.now(),
            "config": config_summary,
            "results": results_summary
        }
        result = db[COLLECTION_SCANS].insert_one(doc)
        return str(result.inserted_id)
    except Exception as e:
        console.print(f"[red]Loi luu scan session: {e}[/red]")
        return None


def get_posts_by_keyword(keyword: str, limit: int = 100) -> list[dict]:
    """Query posts by keyword"""
    db = get_db()
    if db is None:
        return []
    
    try:
        cursor = db[COLLECTION_POSTS].find(
            {"keyword": keyword}
        ).sort("created_at", -1).limit(limit)
        return list(cursor)
    except Exception as e:
        console.print(f"[red]Loi query: {e}[/red]")
        return []


def get_posts_by_group(group_id: str, limit: int = 100) -> list[dict]:
    """Query posts by group"""
    db = get_db()
    if db is None:
        return []
    
    try:
        cursor = db[COLLECTION_POSTS].find(
            {"group_id": group_id}
        ).sort("created_at", -1).limit(limit)
        return list(cursor)
    except Exception as e:
        console.print(f"[red]Loi query: {e}[/red]")
        return []


def get_stats() -> dict:
    """Get database statistics"""
    db = get_db()
    if db is None:
        return {}
    
    try:
        return {
            "total_posts": db[COLLECTION_POSTS].count_documents({}),
            "total_scans": db[COLLECTION_SCANS].count_documents({}),
            "unique_groups": len(db[COLLECTION_POSTS].distinct("group_id")),
            "unique_keywords": len(db[COLLECTION_POSTS].distinct("keyword"))
        }
    except Exception as e:
        console.print(f"[red]Loi get stats: {e}[/red]")
        return {}
