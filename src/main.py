"""
Main entry point for Facebook Group Scanner
"""

import asyncio
import sys
import os

# Fix encoding for Windows
if sys.platform == "win32":
    os.system("chcp 65001 >nul 2>&1")
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from rich.console import Console

from .cookies import validate_cookie_file
from .browser import create_browser, create_context_with_cookies, create_page, navigate_to_group_search
from .scanner import scroll_and_collect_posts
from .output import display_results, save_results

console = Console(force_terminal=True)


async def scan_facebook_group(
    group_id: str,
    keyword: str,
    cookie_file: str = "www_facebook_com_cookies.json",
    max_scrolls: int = 100,
    headless: bool = False,
    output_file: str = None
) -> list[dict]:
    """
    Main function to scan a Facebook group for posts containing keyword
    
    Args:
        group_id: Facebook group ID or vanity URL
        keyword: Keyword to search for
        cookie_file: Path to cookie file
        max_scrolls: Maximum scrolls (safety limit)
        headless: Run browser in headless mode
        output_file: Custom output file path
        
    Returns:
        List of found posts
    """
    console.print(f"\n[bold blue]Facebook Group Keyword Scanner[/bold blue]")
    console.print(f"[dim]Group: {group_id}[/dim]")
    console.print(f"[dim]Keyword: {keyword}[/dim]\n")
    
    # Validate cookie file
    if not validate_cookie_file(cookie_file):
        console.print(f"[red][X] Khong tim thay hoac file cookie khong hop le: {cookie_file}[/red]")
        return []
    
    browser = None
    playwright = None
    
    try:
        # Create browser
        browser, playwright = await create_browser(headless=headless)
        
        # Create context with cookies
        context = await create_context_with_cookies(browser, cookie_file)
        console.print(f"[green][OK][/green] Da inject cookies vao browser")
        
        # Create page
        page = await create_page(context)
        
        # Navigate to group search
        if not await navigate_to_group_search(page, group_id, keyword):
            return []
        
        # Scroll and collect posts
        posts = await scroll_and_collect_posts(page, keyword, max_scrolls)
        
        # Display results
        display_results(posts, keyword)
        
        # Save results
        if posts:
            save_results(posts, group_id, keyword, output_file)
        
        return posts
        
    except Exception as e:
        console.print(f"[red][X] Loi: {str(e)}[/red]")
        import traceback
        traceback.print_exc()
        return []
    
    finally:
        if browser:
            await browser.close()
        if playwright:
            await playwright.stop()


def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Facebook Group Keyword Scanner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Vi du su dung:
  python -m src.main 123456789 "tu khoa"
  python -m src.main groupname "keyword" --scrolls 30
  python -m src.main 123456789 "sale" --headless --output results.json
        """
    )
    
    parser.add_argument("group_id", help="ID hoac ten cua Facebook group")
    parser.add_argument("keyword", help="Tu khoa can tim kiem")
    parser.add_argument(
        "--cookies", "-c",
        default="www_facebook_com_cookies.json",
        help="Duong dan den file cookies (default: www_facebook_com_cookies.json)"
    )
    parser.add_argument(
        "--scrolls", "-s",
        type=int,
        default=100,
        help="So lan scroll toi da (default: 100)"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Chay browser o che do an"
    )
    parser.add_argument(
        "--output", "-o",
        help="File output de luu ket qua (JSON)"
    )
    
    args = parser.parse_args()
    
    # Run async function
    asyncio.run(scan_facebook_group(
        group_id=args.group_id,
        keyword=args.keyword,
        cookie_file=args.cookies,
        max_scrolls=args.scrolls,
        headless=args.headless,
        output_file=args.output
    ))


if __name__ == "__main__":
    main()
