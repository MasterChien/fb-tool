"""
Main scanning logic module
"""

import asyncio
from datetime import datetime
from playwright.async_api import Page
from rich.console import Console

from .config import DEFAULT_SCROLL_DELAY, MAX_NO_NEW_POSTS
from .extractor import extract_posts, expand_all_posts, check_end_of_results
from .utils import extract_snippet

console = Console(force_terminal=True)


async def scroll_and_collect_posts(
    page: Page, 
    keyword: str, 
    max_scrolls: int = 100,
    scroll_delay: float = DEFAULT_SCROLL_DELAY
) -> list[dict]:
    """
    Scroll page and collect posts containing keyword
    
    Args:
        page: Playwright page object
        keyword: Keyword to search for
        max_scrolls: Maximum number of scrolls (safety limit)
        scroll_delay: Delay between scrolls in seconds
        
    Returns:
        List of found posts
    """
    posts_found = []
    seen_content_hashes = set()
    
    scroll_num = 0
    no_new_posts_count = 0
    
    console.print(f"\n[cyan]Bat dau tim kiem posts chua '{keyword}'...[/cyan]")
    console.print(f"[dim]Se tu dong dung khi khong con post moi hoac het ket qua[/dim]\n")
    
    # Wait for initial page load
    console.print(f"[dim]Cho trang load...[/dim]")
    await asyncio.sleep(3)
    
    while scroll_num < max_scrolls:
        scroll_num += 1
        posts_before = len(posts_found)
        
        # First, expand all "Xem thêm" buttons to get full content
        expanded = await expand_all_posts(page)
        if expanded > 0 and scroll_num <= 3:
            console.print(f"[dim]  Da expand {expanded} posts[/dim]")
            await asyncio.sleep(1)  # Wait for content to load
        
        # Extract posts containing keyword
        raw_posts = await extract_posts(page, keyword, debug=(scroll_num == 1))
        
        if scroll_num == 1:
            console.print(f"[dim]Debug: Tim thay {len(raw_posts)} posts chua keyword '{keyword}'[/dim]")
        
        # Process found posts
        for post_data in raw_posts:
            try:
                content = post_data.get("content", "")
                link = post_data.get("link", "")
                author = post_data.get("author", "Unknown")
                author_link = post_data.get("author_link", "")
                
                if len(content) < 10:
                    continue
                
                # Normalize content for duplicate check
                # Remove all whitespace, punctuation variations, and convert to lowercase
                import re
                # Remove all whitespace and common punctuation
                normalized = re.sub(r'[\s\.,\?\!\:\;\-\(\)\[\]\"\']+', '', content).lower()[:200]
                content_hash = hash(normalized)
                if content_hash in seen_content_hashes:
                    continue
                seen_content_hashes.add(content_hash)
                
                # Create snippet
                snippet = extract_snippet(content, keyword, 150)
                
                posts_found.append({
                    "author": author,
                    "author_link": author_link,
                    "snippet": snippet,
                    "link": link,
                    "full_text": content[:2000],
                    "found_at": datetime.now().isoformat()
                })
                
                console.print(f"  [green][+][/green] #{len(posts_found)} - [bold]{author[:30]}[/bold]")
            
            except Exception as e:
                continue
        
        # Check progress
        posts_after = len(posts_found)
        new_posts_this_scroll = posts_after - posts_before
        
        if new_posts_this_scroll == 0:
            no_new_posts_count += 1
        else:
            no_new_posts_count = 0
        
        console.print(f"[dim]  Scroll {scroll_num}: +{new_posts_this_scroll} posts moi (tong: {len(posts_found)})[/dim]")
        
        # Get current height before scrolling
        current_height = await page.evaluate("document.body.scrollHeight")
        
        # Scroll to bottom
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        
        # Wait for content to load
        await asyncio.sleep(scroll_delay + 1)
        
        # Check if page loaded more content
        new_height = await page.evaluate("document.body.scrollHeight")
        
        if new_height == current_height:
            console.print(f"[dim]  Dang cho Facebook load them...[/dim]")
            await asyncio.sleep(4)
            
            new_height = await page.evaluate("document.body.scrollHeight")
            
            if new_height == current_height:
                # Try scroll up then down to trigger load
                await page.evaluate("window.scrollBy(0, -500)")
                await asyncio.sleep(1)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(3)
        
        # Check for end of results
        if await check_end_of_results(page):
            console.print(f"\n[green]Da tim het ket qua! (Facebook bao 'Da het ket qua')[/green]")
            break
        
        # Stop if no new posts for too long
        if no_new_posts_count >= MAX_NO_NEW_POSTS:
            console.print(f"\n[yellow]Da scroll {MAX_NO_NEW_POSTS} lan khong tim thay post moi. Dung tim kiem.[/yellow]")
            break
    
    if scroll_num >= max_scrolls:
        console.print(f"\n[yellow]Da dat gioi han {max_scrolls} lan scroll.[/yellow]")
    
    return posts_found
