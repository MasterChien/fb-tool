"""
Batch runner module - runs multiple scans concurrently
"""

import asyncio
from datetime import datetime
from rich.console import Console
from rich.table import Table

from .config_parser import ScanConfig
from .cookies import validate_cookie_file
from .browser import create_browser, create_context_with_cookies, create_page, navigate_to_group_search
from .scanner import scroll_and_collect_posts
from .output import save_results, save_consolidated_results

console = Console(force_terminal=True)


async def scan_single_pair(
    pair_id: int,
    group_id: str,
    keyword: str,
    cookie_file: str,
    max_scrolls: int,
    headless: bool = False,
    browser_index: int = 0
) -> dict:
    """
    Scan a single (group, keyword) pair
    
    Args:
        pair_id: ID for this pair (for logging)
        group_id: Facebook group ID
        keyword: Search keyword
        cookie_file: Path to cookie file
        max_scrolls: Maximum scrolls
        headless: Run headless
        browser_index: Index for window positioning (0-based)
        
    Returns:
        Result dictionary with posts and metadata
    """
    result = {
        "pair_id": pair_id,
        "group_id": group_id,
        "keyword": keyword,
        "posts": [],
        "success": False,
        "error": None
    }
    
    browser = None
    playwright = None
    
    try:
        console.print(f"\n[bold cyan]===== Browser {pair_id}: {group_id} + '{keyword}' =====[/bold cyan]")
        
        # Create browser with specific window position
        browser, playwright = await create_browser(headless=headless, browser_index=browser_index)
        
        # Create context with cookies
        context = await create_context_with_cookies(browser, cookie_file)
        
        # Create page
        page = await create_page(context)
        
        # Navigate to group search
        if not await navigate_to_group_search(page, group_id, keyword):
            result["error"] = "Navigation failed"
            return result
        
        # Scroll and collect posts
        posts = await scroll_and_collect_posts(page, keyword, max_scrolls)
        
        result["posts"] = posts
        result["success"] = True
        
        # Save results
        if posts:
            save_results(posts, group_id, keyword)
        
        return result
        
    except Exception as e:
        result["error"] = str(e)
        console.print(f"[red][X] Browser {pair_id} error: {e}[/red]")
        return result
    
    finally:
        if browser:
            await browser.close()
        if playwright:
            await playwright.stop()


async def worker(
    worker_id: int,
    queue: asyncio.Queue,
    cookie_file: str,
    max_scrolls: int,
    headless: bool,
    results: list
):
    """
    Worker that processes pairs from queue
    
    Args:
        worker_id: ID for this worker (1-based)
        queue: Queue of (pair_id, group_id, keyword) tuples
        cookie_file: Path to cookie file
        max_scrolls: Maximum scrolls
        headless: Run headless
        results: List to store results
    """
    while True:
        try:
            # Get next pair from queue (with timeout to check if done)
            pair_data = await asyncio.wait_for(queue.get(), timeout=1.0)
        except asyncio.TimeoutError:
            # Check if queue is empty and no more items coming
            if queue.empty():
                break
            continue
        
        pair_id, group_id, keyword = pair_data
        
        console.print(f"\n[yellow]Worker {worker_id} starting pair {pair_id}: {group_id} + '{keyword}'[/yellow]")
        
        result = await scan_single_pair(
            pair_id=pair_id,
            group_id=group_id,
            keyword=keyword,
            cookie_file=cookie_file,
            max_scrolls=max_scrolls,
            headless=headless,
            browser_index=worker_id - 1  # Convert to 0-based for window positioning
        )
        
        results.append(result)
        queue.task_done()
        
        console.print(f"[green]Worker {worker_id} finished pair {pair_id}: {len(result['posts'])} posts found[/green]")


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
    
    # Get all pairs
    pairs = config.get_all_pairs()
    total_pairs = len(pairs)
    
    console.print(f"\n[bold blue]========================================[/bold blue]")
    console.print(f"[bold blue]   Facebook Group Batch Scanner[/bold blue]")
    console.print(f"[bold blue]========================================[/bold blue]")
    console.print(f"\n[cyan]Configuration:[/cyan]")
    console.print(f"  Concurrent browsers: {config.number_of_browser}")
    console.print(f"  Max scrolls per search: {config.scrolls}")
    console.print(f"  Groups: {', '.join(config.groups)}")
    console.print(f"  Keywords: {', '.join(config.keywords)}")
    console.print(f"  Total pairs to scan: {total_pairs}")
    console.print(f"\n[cyan]Pairs to scan:[/cyan]")
    
    for i, (group, keyword) in enumerate(pairs, 1):
        console.print(f"  {i}. {group} + '{keyword}'")
    
    console.print(f"\n[yellow]Starting {config.number_of_browser} browser(s)...[/yellow]\n")
    
    # Create queue and add all pairs
    queue = asyncio.Queue()
    for i, (group, keyword) in enumerate(pairs, 1):
        await queue.put((i, group, keyword))
    
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
                results=results
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
    
    return results


def display_batch_summary(results: list[dict]):
    """Display summary of batch results"""
    console.print(f"\n[bold green]========================================[/bold green]")
    console.print(f"[bold green]   BATCH SCAN COMPLETE[/bold green]")
    console.print(f"[bold green]========================================[/bold green]\n")
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=4)
    table.add_column("Group", width=20)
    table.add_column("Keyword", width=15)
    table.add_column("Posts", width=8)
    table.add_column("Status", width=10)
    
    total_posts = 0
    successful = 0
    
    for result in sorted(results, key=lambda x: x["pair_id"]):
        posts_count = len(result["posts"])
        total_posts += posts_count
        
        if result["success"]:
            status = "[green]OK[/green]"
            successful += 1
        else:
            status = f"[red]FAIL[/red]"
        
        table.add_row(
            str(result["pair_id"]),
            result["group_id"][:20],
            result["keyword"][:15],
            str(posts_count),
            status
        )
    
    console.print(table)
    console.print(f"\n[cyan]Summary:[/cyan]")
    console.print(f"  Total pairs: {len(results)}")
    console.print(f"  Successful: {successful}")
    console.print(f"  Failed: {len(results) - successful}")
    console.print(f"  Total posts found: {total_posts}")
