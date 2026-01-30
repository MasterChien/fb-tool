"""
Batch runner module - runs multiple scans concurrently with browser reuse
"""

import asyncio
from datetime import datetime
from rich.console import Console
from rich.table import Table

from .config_parser import ScanConfig
from .config import DELAY_BETWEEN_PAIRS
from .cookies import validate_cookie_file
from .browser import create_browser, create_context_with_cookies, create_page, navigate_to_group_search
from .scanner import scroll_and_collect_posts
from .output import save_results, save_consolidated_results
from .database import save_posts_to_db, get_db, close_db

console = Console(force_terminal=True)


async def scan_with_page(
    page,
    pair_id: int,
    group_id: str,
    search_term: str,
    keyword_list: list[str],
    max_scrolls: int,
    extract_links: bool = False
) -> dict:
    """
    Scan một cặp (group, search_term) với danh sách keyword cùng tiền tố.
    Search FB bằng search_term; mỗi post được phân loại theo matched_keywords.
    Lưu kết quả theo từng keyword (group_id, keyword).
    """
    result = {
        "pair_id": pair_id,
        "group_id": group_id,
        "search_term": search_term,
        "keyword_list": keyword_list,
        "keyword_posts": {},  # keyword -> list of posts (chỉ post fields, không có matched_keywords)
        "success": False,
        "error": None,
    }
    
    try:
        if not await navigate_to_group_search(page, group_id, search_term):
            result["error"] = "Navigation failed"
            return result
        
        posts = await scroll_and_collect_posts(
            page, search_term=search_term, keyword_list=keyword_list, max_scrolls=max_scrolls,
            extract_links_by_click=extract_links
        )
        result["success"] = True
        
        # Chia post theo keyword: mỗi post có matched_keywords, thêm vào từng keyword
        for kw in keyword_list:
            result["keyword_posts"][kw] = []
        for p in posts:
            for kw in p.get("matched_keywords", []):
                if kw in result["keyword_posts"]:
                    out = {k: v for k, v in p.items() if k != "matched_keywords"}
                    result["keyword_posts"][kw].append(out)
        
        for kw, plist in result["keyword_posts"].items():
            if plist:
                # Save to JSON file
                save_results(plist, group_id, kw)
                # Save to MongoDB
                saved_to_db = save_posts_to_db(plist, group_id, kw)
                if saved_to_db > 0:
                    console.print(f"[dim]  -> Luu {saved_to_db} posts vao MongoDB (keyword: {kw})[/dim]")
        
        return result
        
    except Exception as e:
        result["error"] = str(e)
        console.print(f"[red][X] Error scanning {group_id} + '{search_term}': {e}[/red]")
        return result


async def worker(
    worker_id: int,
    queue: asyncio.Queue,
    cookie_file: str,
    max_scrolls: int,
    headless: bool,
    results: list,
    extract_links: bool = False
):
    """
    Worker that processes pairs from queue - REUSES browser for multiple pairs
    
    Args:
        worker_id: ID for this worker (1-based)
        queue: Queue of (pair_id, group_id, search_term, keyword_list) tuples
        cookie_file: Path to cookie file
        max_scrolls: Maximum scrolls
        headless: Run headless
        results: List to store results
        extract_links: Extract post links by clicking (slower)
    """
    browser = None
    playwright = None
    page = None
    pairs_processed = 0
    
    try:
        # Create browser ONCE for this worker
        console.print(f"[cyan]Worker {worker_id}: Khoi tao browser...[/cyan]")
        browser, playwright = await create_browser(headless=headless, browser_index=worker_id - 1)
        
        # Create context with cookies
        context = await create_context_with_cookies(browser, cookie_file)
        
        # Create page
        page = await create_page(context)
        console.print(f"[green]Worker {worker_id}: Browser san sang![/green]")
        
        while True:
            try:
                # Get next pair from queue (with timeout to check if done)
                pair_data = await asyncio.wait_for(queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                # Check if queue is empty and no more items coming
                if queue.empty():
                    break
                continue

            pair_id, group_id, search_term, keyword_list = pair_data

            # Add delay between pairs (except first one) to avoid rate limiting
            if pairs_processed > 0:
                console.print(f"[dim]Worker {worker_id}: Cho {DELAY_BETWEEN_PAIRS}s truoc khi tiep tuc...[/dim]")
                await asyncio.sleep(DELAY_BETWEEN_PAIRS)

            console.print(f"\n[yellow]Worker {worker_id} - Pair {pair_id}: {group_id} + '{search_term}' -> {keyword_list}[/yellow]")

            result = await scan_with_page(
                page=page,
                pair_id=pair_id,
                group_id=group_id,
                search_term=search_term,
                keyword_list=keyword_list,
                max_scrolls=max_scrolls,
                extract_links=extract_links
            )

            results.append(result)
            queue.task_done()
            pairs_processed += 1

            total_posts = sum(len(plist) for plist in result.get("keyword_posts", {}).values())
            console.print(f"[green]Worker {worker_id} xong pair {pair_id}: {total_posts} posts (phan loai theo {len(keyword_list)} keyword)[/green]")

    except Exception as e:
        console.print(f"[red]Worker {worker_id} error: {e}[/red]")
        
    finally:
        # Clean up browser at the end
        console.print(f"[dim]Worker {worker_id}: Dong browser sau {pairs_processed} pairs...[/dim]")
        if browser:
            await browser.close()
        if playwright:
            await playwright.stop()


async def run_batch(
    config: ScanConfig,
    cookie_file: str = "www_facebook_com_cookies.json",
    headless: bool = False
) -> list[dict]:
    """
    Run batch scanning with multiple concurrent browsers
    
    Args:
        config: ScanConfig object
        cookie_file: Path to cookie file
        headless: Run browsers in headless mode
        
    Returns:
        List of result dictionaries
    """
    # Validate cookie file
    if not validate_cookie_file(cookie_file):
        console.print(f"[red][X] Invalid cookie file: {cookie_file}[/red]")
        return []
    
    # Cặp sau khi gom nhóm keyword: (group_id, search_term, keyword_list)
    grouped_pairs = config.get_grouped_pairs()
    total_pairs = len(grouped_pairs)
    
    console.print(f"\n[bold blue]========================================[/bold blue]")
    console.print(f"[bold blue]   Facebook Group Batch Scanner[/bold blue]")
    console.print(f"[bold blue]========================================[/bold blue]")
    console.print(f"\n[cyan]Configuration:[/cyan]")
    console.print(f"  Concurrent browsers: {config.number_of_browser}")
    console.print(f"  Max scrolls per search: {config.scrolls}")
    console.print(f"  Extract links by click: {config.extract_links}")
    console.print(f"  Groups: {len(config.groups)}")
    console.print(f"  Keywords (gom nhom): {config.get_keyword_groups()}")
    console.print(f"  Total searches (group x search_term): {total_pairs}")
    console.print(f"\n[cyan]Searches to run:[/cyan]")
    
    for i, (group, search_term, keyword_list) in enumerate(grouped_pairs, 1):
        console.print(f"  {i}. {group} + '{search_term}' -> {keyword_list}")
    
    console.print(f"\n[yellow]Starting {config.number_of_browser} browser(s)...[/yellow]\n")
    
    queue = asyncio.Queue()
    for i, (group, search_term, keyword_list) in enumerate(grouped_pairs, 1):
        await queue.put((i, group, search_term, keyword_list))
    
    # Results storage
    results = []
    
    # Create workers
    num_workers = min(config.number_of_browser, total_pairs)
    workers = []
    
    for worker_id in range(1, num_workers + 1):
        worker_task = asyncio.create_task(
            worker(
                worker_id=worker_id,
                queue=queue,
                cookie_file=cookie_file,
                max_scrolls=config.scrolls,
                headless=headless,
                results=results,
                extract_links=config.extract_links
            )
        )
        workers.append(worker_task)
    
    # Wait for all pairs to be processed
    await queue.join()
    
    # Cancel workers
    for w in workers:
        w.cancel()
    
    # Wait for workers to finish
    await asyncio.gather(*workers, return_exceptions=True)
    
    # Display summary
    display_batch_summary(results)
    
    # Save consolidated results
    if results:
        save_consolidated_results(results)
    
    # Show MongoDB stats
    from .database import get_stats
    stats = get_stats()
    if stats:
        console.print(f"\n[cyan]MongoDB Stats:[/cyan]")
        console.print(f"  Total posts in DB: {stats.get('total_posts', 0)}")
        console.print(f"  Unique groups: {stats.get('unique_groups', 0)}")
        console.print(f"  Unique keywords: {stats.get('unique_keywords', 0)}")
    
    # Close MongoDB connection
    close_db()
    
    return results


def display_batch_summary(results: list[dict]):
    """Display summary: flatten theo (group_id, keyword) từ keyword_posts."""
    console.print(f"\n[bold green]========================================[/bold green]")
    console.print(f"[bold green]   BATCH SCAN COMPLETE[/bold green]")
    console.print(f"[bold green]========================================[/bold green]\n")
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=4)
    table.add_column("Group", width=20)
    table.add_column("Keyword", width=18)
    table.add_column("Posts", width=8)
    table.add_column("Status", width=10)
    
    total_posts = 0
    successful = 0
    row_num = 0
    
    for result in sorted(results, key=lambda x: x["pair_id"]):
        group_id = result.get("group_id", "")
        status = "[green]OK[/green]" if result.get("success") else "[red]FAIL[/red]"
        if result.get("success"):
            successful += 1
        
        keyword_posts = result.get("keyword_posts", {})
        if keyword_posts:
            for keyword, posts in keyword_posts.items():
                row_num += 1
                total_posts += len(posts)
                table.add_row(
                    str(row_num),
                    group_id[:20] if len(group_id) > 20 else group_id,
                    keyword[:18] if len(keyword) > 18 else keyword,
                    str(len(posts)),
                    status
                )
        else:
            row_num += 1
            table.add_row(
                str(row_num),
                group_id[:20] if len(group_id) > 20 else group_id,
                result.get("search_term", "-")[:18],
                "0",
                status
            )
    
    console.print(table)
    console.print(f"\n[cyan]Summary:[/cyan]")
    console.print(f"  Total searches: {len(results)}")
    console.print(f"  Successful: {successful}")
    console.print(f"  Failed: {len(results) - successful}")
    console.print(f"  Total posts found: {total_posts}")
