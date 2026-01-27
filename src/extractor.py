"""
Post extraction module - handles extracting posts from Facebook DOM
"""

from playwright.async_api import Page
from rich.console import Console
from .config import EXPAND_BUTTON_TEXTS

console = Console(force_terminal=True)


async def expand_all_posts(page: Page) -> int:
    """
    Click all "Xem thêm" / "See more" buttons to expand posts
    
    Args:
        page: Playwright page object
        
    Returns:
        Number of buttons clicked
    """
    js_code = """
    async () => {
        const expandTexts = ['Xem thêm', 'See more', 'View more'];
        let clicked = 0;
        
        // Find all potential expand buttons/links
        const allElements = document.querySelectorAll('div[role="button"], span[role="button"], a');
        
        for (const el of allElements) {
            const text = el.innerText || '';
            const trimmedText = text.trim();
            
            // Check if this is an expand button
            for (const expandText of expandTexts) {
                if (trimmedText === expandText || trimmedText.startsWith(expandText)) {
                    try {
                        el.click();
                        clicked++;
                        // Small delay between clicks
                        await new Promise(r => setTimeout(r, 100));
                    } catch (e) {}
                    break;
                }
            }
        }
        
        return clicked;
    }
    """
    
    try:
        clicked = await page.evaluate(js_code)
        return clicked
    except Exception as e:
        console.print(f"[dim]Warning: Error expanding posts: {e}[/dim]")
        return 0


async def extract_posts(page: Page, keyword: str, debug: bool = False) -> list[dict]:
    """
    Extract posts from page that contain the keyword
    
    Args:
        page: Playwright page object
        keyword: Keyword to search for
        debug: Enable debug output
        
    Returns:
        List of post dictionaries
    """
    # Using raw string to avoid escape issues
    js_code = r"""
    (args) => {
        const keyword = args.keyword;
        const debug = args.debug;
        const posts = [];
        const seen = new Set();
        const debugInfo = [];
        
        // Create case-insensitive regex for keyword matching (handles Unicode properly)
        // Escape special regex characters in keyword
        const escapedKeyword = keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const keywordRegex = new RegExp(escapedKeyword, 'i');
        
        // Find all story message divs
        const storyMessages = document.querySelectorAll('div[data-ad-rendering-role="story_message"]');
        
        if (debug) {
            debugInfo.push(`Found ${storyMessages.length} story_message elements`);
            debugInfo.push(`Keyword regex: ${keywordRegex}`);
        }
        
        storyMessages.forEach((messageDiv, index) => {
            try {
                const content = messageDiv.innerText || '';
                if (content.length < 10) return;
                
                // Check if content contains keyword (case-insensitive with Unicode support)
                if (!keywordRegex.test(content)) {
                    if (debug && index < 3) {
                        debugInfo.push(`Post ${index}: No keyword found in "${content.substring(0, 50)}..."`);
                    }
                    return;
                }
                
                if (debug && index < 5) {
                    debugInfo.push(`Post ${index}: MATCH - "${content.substring(0, 80)}..."`);
                }
                
                // Normalize content for duplicate check (remove whitespace and punctuation)
                const normalizedContent = content.replace(/[\s\.,\?\!\:\;\-\(\)\[\]\"\']+/g, '').toLowerCase().substring(0, 200);
                if (seen.has(normalizedContent)) return;
                seen.add(normalizedContent);
                
                // Find post link by traversing up from story_message
                let link = '';
                let authorLink = '';
                let postContainer = messageDiv.closest('[role="article"]') || messageDiv.parentElement;
                let debugLinks = [];
                
                // Time patterns for aria-label
                const timePatterns = [
                    /^\d+\s*(giờ|phút|ngày|tuần|tháng|năm)/i,  // Vietnamese: "2 ngày", "3 giờ"
                    /^\d+[smhdwy]$/i,                           // English short: "2h", "3d"
                    /^\d+\s*(second|minute|hour|day|week|month|year)/i,  // English: "2 days"
                    /^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|Thg)/i,  // Month names
                    /^(Yesterday|Hôm qua|Today|Hôm nay)/i       // Yesterday/Today
                ];
                
                // Strategy: Go up the tree to find link matching pattern:
                // https://www.facebook.com/groups/[group_name]/posts/[post_id]
                let searchContainer = messageDiv;
                const postLinkPattern = /facebook\.com\/groups\/[^\/]+\/posts\/\d+/;
                
                for (let level = 0; level < 20 && searchContainer && !link; level++) {
                    // Look for ALL links and check if href matches post URL pattern
                    const allLinks = searchContainer.querySelectorAll('a');
                    for (const a of allLinks) {
                        const href = a.href || '';
                        
                        // Check if href matches full Facebook group post URL
                        if (href.match(postLinkPattern)) {
                            link = href;
                            postContainer = searchContainer;
                            if (debug) {
                                const ariaLabel = a.getAttribute('aria-label') || 'no-label';
                                debugInfo.push(`Post ${index}: Found post link at level ${level}, aria-label="${ariaLabel}"`);
                            }
                            break;
                        }
                    }
                    
                    // Move up to parent
                    searchContainer = searchContainer.parentElement;
                }
                
                // Get author and author_link from the found container
                // First get author_link
                if (postContainer) {
                    const userLinks = postContainer.querySelectorAll('a[href*="/user/"]');
                    for (const a of userLinks) {
                        const href = a.href || a.getAttribute('href') || '';
                        if (href.includes('/groups/')) {
                            authorLink = href;
                            break;
                        }
                    }
                }
                
                
                // Clean up links
                if (link) {
                    if (!link.startsWith('http')) {
                        link = 'https://www.facebook.com' + link;
                    }
                    link = link.split('?')[0];
                }
                
                if (authorLink) {
                    if (!authorLink.startsWith('http')) {
                        authorLink = 'https://www.facebook.com' + authorLink;
                    }
                    authorLink = authorLink.split('?')[0];
                }
                
                // Get author
                let author = 'Unknown';
                const authorSelectors = ['h2 a', 'h3 a', 'strong a', 'a[role="link"] strong', 'span[dir="auto"] a strong'];
                for (const sel of authorSelectors) {
                    const authorEl = postContainer.querySelector(sel);
                    if (authorEl && authorEl.innerText && authorEl.innerText.length > 1) {
                        author = authorEl.innerText.trim();
                        break;
                    }
                }
                
                posts.push({
                    author: author.substring(0, 100),
                    content: content,
                    link: link,
                    author_link: authorLink
                });
            } catch (e) {
                if (debug) {
                    debugInfo.push(`Error processing post ${index}: ${e.message}`);
                }
            }
        });
        
        return { posts: posts, debug: debugInfo, totalElements: storyMessages.length };
    }
    """
    
    try:
        result = await page.evaluate(js_code, {"keyword": keyword, "debug": debug})
        
        if debug:
            console.print(f"[dim]  Total story_message elements: {result.get('totalElements', 0)}[/dim]")
            for msg in result.get("debug", []):
                console.print(f"[dim]  {msg}[/dim]")
        
        return result.get("posts", [])
    except Exception as e:
        console.print(f"[red]JS extraction error: {e}[/red]")
        return []


async def check_end_of_results(page: Page) -> bool:
    """
    Check if Facebook shows "End of results" message
    
    Args:
        page: Playwright page object
        
    Returns:
        True if end of results reached
    """
    js_code = """
    () => {
        const endTexts = ['Đã hết kết quả', 'No more results', 'End of results'];
        const allSpans = document.querySelectorAll('span');
        for (const span of allSpans) {
            const text = span.innerText || '';
            for (const endText of endTexts) {
                if (text.includes(endText)) {
                    return true;
                }
            }
        }
        return false;
    }
    """
    
    try:
        return await page.evaluate(js_code)
    except:
        return False
