"""
Output handling module - save and display results
"""

import json
import os
from datetime import datetime
from pathlib import Path
from rich.console import Console
from rich.table import Table

console = Console(force_terminal=True)

# Default output directory
OUTPUT_DIR = "results"


def ensure_output_dir():
    """Create output directory if it doesn't exist"""
    Path(OUTPUT_DIR).mkdir(exist_ok=True)


def display_results(posts: list[dict], keyword: str):
    """
    Display search results in a table
    
    Args:
        posts: List of found posts
        keyword: Search keyword
    """
    console.print(f"\n[bold green]=== KET QUA ===[/bold green]")
    console.print(f"Tim thay [bold]{len(posts)}[/bold] bai viet chua '[bold]{keyword}[/bold]'\n")
    
    if not posts:
        return
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=4)
    table.add_column("Tac gia", width=15)
    table.add_column("Noi dung", width=55)
    table.add_column("Link", width=20)
    
    for idx, post in enumerate(posts, 1):
        snippet = post.get("snippet", "")[:100].replace("\n", " ")
        link = post.get("link", "")
        if len(link) > 25:
            link = link[:22] + "..."
        
        table.add_row(
            str(idx),
            post.get("author", "Unknown")[:15],
            snippet,
            link
        )
    
    console.print(table)


def enrich_posts(posts: list[dict], group_id: str, keyword: str) -> list[dict]:
    """
    Add group_id and keyword to each post for easy filtering
    
    Args:
        posts: List of post dictionaries
        group_id: Facebook group ID
        keyword: Search keyword
        
    Returns:
        Enriched posts with group_id and keyword
    """
    enriched = []
    for post in posts:
        enriched_post = {
            "group_id": group_id,
            "keyword": keyword,
            **post
        }
        enriched.append(enriched_post)
    return enriched


def save_results(
    posts: list[dict], 
    group_id: str, 
    keyword: str, 
    output_file: str = None
) -> str:
    """
    Save results to JSON file (individual file for this group+keyword pair)
    
    Args:
        posts: List of found posts
        group_id: Facebook group ID
        keyword: Search keyword
        output_file: Custom output file path
        
    Returns:
        Path to saved file
    """
    ensure_output_dir()
    
    # Enrich posts with group_id and keyword
    enriched_posts = enrich_posts(posts, group_id, keyword)
    
    if output_file is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # Clean group and keyword for filename
        safe_group = "".join(c if c.isalnum() else "_" for c in group_id)
        safe_keyword = "".join(c if c.isalnum() else "_" for c in keyword)
        output_file = os.path.join(OUTPUT_DIR, f"{safe_group}_{safe_keyword}_{timestamp}.json")
    
    result = {
        "group_id": group_id,
        "keyword": keyword,
        "scan_time": datetime.now().isoformat(),
        "total_posts": len(enriched_posts),
        "posts": enriched_posts
    }
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    console.print(f"\n[green][OK][/green] Da luu ket qua vao: [bold]{output_file}[/bold]")
    
    return output_file


def save_consolidated_results(all_results: list[dict], output_file: str = None) -> str:
    """
    Save all results to a single consolidated JSON file for easy filtering
    
    Args:
        all_results: List of result dictionaries from batch scan
        output_file: Custom output file path
        
    Returns:
        Path to saved file
    """
    ensure_output_dir()
    
    if output_file is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join(OUTPUT_DIR, f"all_results_{timestamp}.json")
    
    # Flatten: hỗ trợ cả result có "posts" (cũ) và "keyword_posts" (gom nhóm keyword)
    all_posts = []
    groups_scanned = set()
    keywords_scanned = set()
    
    for result in all_results:
        group_id = result.get("group_id", "")
        groups_scanned.add(group_id)
        
        keyword_posts = result.get("keyword_posts", {})
        if keyword_posts:
            for keyword, posts in keyword_posts.items():
                keywords_scanned.add(keyword)
                for post in posts:
                    enriched_post = {"group_id": group_id, "keyword": keyword, **post}
                    all_posts.append(enriched_post)
        else:
            keyword = result.get("keyword", "")
            posts = result.get("posts", [])
            keywords_scanned.add(keyword)
            for post in posts:
                enriched_post = {"group_id": group_id, "keyword": keyword, **post}
                all_posts.append(enriched_post)
    
    consolidated = {
        "scan_time": datetime.now().isoformat(),
        "summary": {
            "total_posts": len(all_posts),
            "total_searches": len(all_results),
            "groups_scanned": sorted(list(groups_scanned)),
            "keywords_scanned": sorted(list(keywords_scanned))
        },
        "posts": all_posts
    }
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(consolidated, f, ensure_ascii=False, indent=2)
    
    console.print(f"\n[green][OK][/green] Da luu ket qua tong hop vao: [bold]{output_file}[/bold]")
    
    return output_file


def filter_results(
    results_file: str,
    group_id: str = None,
    keyword: str = None
) -> list[dict]:
    """
    Filter results from a consolidated results file
    
    Args:
        results_file: Path to consolidated results JSON file
        group_id: Filter by group ID (optional)
        keyword: Filter by keyword (optional)
        
    Returns:
        Filtered list of posts
    """
    with open(results_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    posts = data.get("posts", [])
    
    # Apply filters
    if group_id:
        posts = [p for p in posts if p.get("group_id") == group_id]
    
    if keyword:
        posts = [p for p in posts if p.get("keyword") == keyword]
    
    return posts


def get_unique_groups(results_file: str) -> list[str]:
    """Get list of unique groups from results file"""
    with open(results_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("summary", {}).get("groups_scanned", [])


def get_unique_keywords(results_file: str) -> list[str]:
    """Get list of unique keywords from results file"""
    with open(results_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("summary", {}).get("keywords_scanned", [])
