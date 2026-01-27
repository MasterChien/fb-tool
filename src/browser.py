"""
Browser management module
"""

import asyncio
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from rich.console import Console

from .config import BROWSER_ARGS, VIEWPORT, USER_AGENT, LOCALE, WINDOW_WIDTH, WINDOW_HEIGHT, GRID_COLS
from .cookies import load_cookies

console = Console(force_terminal=True)


def calculate_window_position(browser_index: int) -> tuple[int, int]:
    """
    Calculate window position for tiled layout
    
    Args:
        browser_index: 0-based browser index
        
    Returns:
        Tuple of (x, y) position
    """
    col = browser_index % GRID_COLS
    row = browser_index // GRID_COLS
    
    x = col * WINDOW_WIDTH
    y = row * WINDOW_HEIGHT
    
    return x, y


async def create_browser(headless: bool = False, browser_index: int = 0) -> tuple[Browser, any]:
    """
    Create and configure browser instance
    
    Args:
        headless: Run browser in headless mode
        browser_index: Index for window positioning (0-based)
        
    Returns:
        Tuple of (browser, playwright instance)
    """
    playwright = await async_playwright().start()
    
    # Calculate window position
    x, y = calculate_window_position(browser_index)
    
    # Add window position args
    args = BROWSER_ARGS + [
        f'--window-position={x},{y}',
        f'--window-size={WINDOW_WIDTH},{WINDOW_HEIGHT}'
    ]
    
    browser = await playwright.chromium.launch(
        headless=headless,
        args=args
    )
    
    return browser, playwright


async def create_context_with_cookies(browser: Browser, cookie_file: str) -> BrowserContext:
    """
    Create browser context and inject cookies
    
    Args:
        browser: Browser instance
        cookie_file: Path to cookie file
        
    Returns:
        Browser context with cookies
    """
    context = await browser.new_context(
        viewport=VIEWPORT,
        user_agent=USER_AGENT,
        locale=LOCALE,
    )
    
    # Load and add cookies
    cookies = load_cookies(cookie_file)
    await context.add_cookies(cookies)
    console.print(f"[green][OK][/green] Da load {len(cookies)} cookies")
    
    return context


async def create_page(context: BrowserContext) -> Page:
    """
    Create new page with anti-detection scripts
    
    Args:
        context: Browser context
        
    Returns:
        Page object
    """
    page = await context.new_page()
    
    # Hide webdriver flag
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
    """)
    
    return page


async def navigate_to_group_search(page: Page, group_id: str, keyword: str) -> bool:
    """
    Navigate to Facebook group and search for keyword
    
    Args:
        page: Page object
        group_id: Facebook group ID or vanity URL
        keyword: Search keyword
        
    Returns:
        True if navigation successful
    """
    from urllib.parse import quote
    
    # First navigate to group
    group_url = f"https://www.facebook.com/groups/{group_id}"
    console.print(f"[cyan]>[/cyan] Dang truy cap group...")
    
    try:
        await page.goto(group_url, wait_until='domcontentloaded', timeout=60000)
        await asyncio.sleep(5)
        
        # Check if login required
        current_url = page.url
        if "login" in current_url.lower() or "checkpoint" in current_url.lower():
            console.print("[red][X] Cookie khong hop le hoac da het han.[/red]")
            return False
        
        console.print(f"[green][OK][/green] Da truy cap group thanh cong")
        
        # Navigate to search
        search_url = f"https://www.facebook.com/groups/{group_id}/search/?q={quote(keyword)}"
        console.print(f"[cyan]>[/cyan] Dang tim kiem '{keyword}'...")
        await page.goto(search_url, wait_until='domcontentloaded', timeout=60000)
        await asyncio.sleep(5)
        
        # Save debug screenshot
        screenshot_path = f"debug_screenshot_{group_id}.png"
        await page.screenshot(path=screenshot_path)
        console.print(f"[dim]Debug: Da luu screenshot vao {screenshot_path}[/dim]")
        
        return True
        
    except Exception as e:
        console.print(f"[red][X] Loi navigation: {e}[/red]")
        return False
