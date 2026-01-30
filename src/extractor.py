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
                
                // Strategy to find post link:
                // 1. Find <a> containing time text (date/time patterns)
                // 2. Direct link: /groups/.../posts/...
                // 3. pcb. pattern in photo links: pcb.POST_ID
                let searchContainer = messageDiv;
                const postLinkPattern = /\/groups\/[^\/]+\/posts\/(\d+)/;
                const pcbPattern = /pcb\.(\d+)/;
                let postId = null;
                
                // Time text patterns for Vietnamese and English
                const timeTextPatterns = [
                    /^\d+\s*(giờ|phút|ngày|tuần|tháng|năm)/i,
                    /^Thứ\s*(Hai|Ba|Tư|Năm|Sáu|Bảy|Chủ nhật)/i,
                    /^\d+\s*Tháng\s*\d+/i,
                    /lúc\s+\d+:\d+/i,
                    /^\d+[hmd]$/i,
                    /^(Yesterday|Hôm qua|Today|Hôm nay)/i,
                    /^(January|February|March|April|May|June|July|August|September|October|November|December)/i,
                    /^\d+\s*(second|minute|hour|day|week|month|year)s?\s*(ago)?/i
                ];
                
                for (let level = 0; level < 25 && searchContainer && !link; level++) {
                    const allLinks = searchContainer.querySelectorAll('a[href]');
                    
                    for (const a of allLinks) {
                        const href = a.getAttribute('href') || '';
                        const linkText = (a.innerText || '').trim();
                        const ariaLabel = a.getAttribute('aria-label') || '';
                        
                        // Check if href contains post link pattern
                        const postMatch = href.match(postLinkPattern);
                        if (postMatch) {
                            // Verify this is likely a time link by checking text or aria-label
                            const textToCheck = linkText || ariaLabel;
                            const isTimeLink = timeTextPatterns.some(p => p.test(textToCheck));
                            
                            if (isTimeLink || href.includes('/posts/')) {
                                postId = postMatch[1];
                                link = href;
                                postContainer = searchContainer;
                                if (debug) {
                                    debugInfo.push(`Post ${index}: Found post link at level ${level}, text="${textToCheck.substring(0, 30)}"`);
                                }
                                break;
                            }
                        }
                        
                        // Secondary: Check aria-label for time pattern and href for /posts/
                        if (!link && ariaLabel && href.includes('/posts/')) {
                            const isTimeLabel = timeTextPatterns.some(p => p.test(ariaLabel));
                            if (isTimeLabel) {
                                const match = href.match(postLinkPattern);
                                if (match) {
                                    postId = match[1];
                                    link = href;
                                    postContainer = searchContainer;
                                    if (debug) {
                                        debugInfo.push(`Post ${index}: Found via aria-label="${ariaLabel}" at level ${level}`);
                                    }
                                    break;
                                }
                            }
                        }
                        
                        // Tertiary: Extract post ID from pcb. pattern (photo links)
                        if (!postId && !link) {
                            const pcbMatch = href.match(pcbPattern);
                            if (pcbMatch) {
                                postId = pcbMatch[1];
                                postContainer = searchContainer;
                                if (debug) {
                                    debugInfo.push(`Post ${index}: Found pcb post ID ${postId} at level ${level}`);
                                }
                            }
                        }
                    }
                    
                    // Move up to parent
                    searchContainer = searchContainer.parentElement;
                }
                
                // If we found postId but no direct link, construct it
                if (postId && !link) {
                    const urlMatch = window.location.href.match(/groups\/([^\/\?]+)/);
                    if (urlMatch) {
                        const groupId = urlMatch[1];
                        link = `https://www.facebook.com/groups/${groupId}/posts/${postId}/`;
                        if (debug) {
                            debugInfo.push(`Post ${index}: Constructed link from pcb ID: ${link}`);
                        }
                    }
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
                    // Handle relative URLs
                    if (link.startsWith('/')) {
                        link = 'https://www.facebook.com' + link;
                    } else if (!link.startsWith('http')) {
                        link = 'https://www.facebook.com/' + link;
                    }
                    // Remove query parameters (keep clean URL)
                    link = link.split('?')[0];
                    
                    if (debug) {
                        debugInfo.push(`Post ${index}: Final link = "${link}"`);
                    }
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


async def extract_post_links_by_click(page: Page, posts: list[dict]) -> list[dict]:
    """
    Extract post links by clicking on each post and capturing the URL.
    This is slower but more reliable for getting post URLs.
    
    Args:
        page: Playwright page object
        posts: List of post dictionaries (will be modified in place)
        
    Returns:
        Updated list of posts with links filled in
    """
    import asyncio
    
    # Get posts that don't have links yet
    posts_needing_links = [(i, p) for i, p in enumerate(posts) if not p.get('link')]
    
    if not posts_needing_links:
        return posts
    
    console.print(f"[dim]  Extracting links for {len(posts_needing_links)} posts by click...[/dim]")
    
    # Save current URL to go back later
    search_url = page.url
    
    for idx, (post_index, post) in enumerate(posts_needing_links):
        try:
            # Find the story_message div matching this post's content
            content_snippet = post.get('full_text', post.get('content', ''))[:80]
            
            # Get all story_message elements
            story_messages = await page.query_selector_all('div[data-ad-rendering-role="story_message"]')
            
            target_element = None
            for msg in story_messages:
                try:
                    text = await msg.inner_text()
                    if text and content_snippet[:40] in text[:100]:
                        target_element = msg
                        break
                except:
                    continue
            
            if not target_element:
                console.print(f"[dim]    [{idx+1}/{len(posts_needing_links)}] Could not find post element[/dim]")
                continue
            
            # Scroll to the element first
            await target_element.scroll_into_view_if_needed()
            await asyncio.sleep(0.5)
            
            # Strategy: Find and click "Bình luận" (Comment) button near the post
            # This will navigate to the post detail page
            got_link = False
            
            # Find the post container by going up from story_message
            js_find_comment = """
            (msgElement) => {
                // Go up to find the post container
                let container = msgElement;
                for (let i = 0; i < 15 && container; i++) {
                    container = container.parentElement;
                }
                
                if (!container) return { found: false, debug: 'no container' };
                
                // Find div[role="button"] with exact text "Bình luận" or "Comment"
                const commentTexts = ['Bình luận', 'Comment'];
                const buttons = container.querySelectorAll('div[role="button"]');
                
                for (const btn of buttons) {
                    const text = (btn.innerText || '').trim();
                    for (const ct of commentTexts) {
                        if (text === ct) {
                            const rect = btn.getBoundingClientRect();
                            return {
                                x: rect.x + rect.width / 2,
                                y: rect.y + rect.height / 2,
                                found: true,
                                debug: 'found button: ' + text
                            };
                        }
                    }
                }
                
                // Fallback: find span containing exact text
                const spans = container.querySelectorAll('span');
                for (const span of spans) {
                    const text = (span.innerText || '').trim();
                    if (text === 'Bình luận' || text === 'Comment') {
                        const rect = span.getBoundingClientRect();
                        return {
                            x: rect.x + rect.width / 2,
                            y: rect.y + rect.height / 2,
                            found: true,
                            debug: 'found span: ' + text
                        };
                    }
                }
                
                return { found: false, debug: 'button not found in ' + buttons.length + ' buttons' };
            }
            """
            
            try:
                result = await target_element.evaluate(js_find_comment)
                console.print(f"[dim]    Debug: {result.get('debug', 'no debug')}[/dim]")
                
                if result and result.get('found'):
                    # Click at the comment button coordinates
                    console.print(f"[dim]    Clicking at ({result['x']:.0f}, {result['y']:.0f})...[/dim]")
                    await page.mouse.click(result['x'], result['y'])
                    await asyncio.sleep(3)
                    
                    new_url = page.url
                    console.print(f"[dim]    New URL: {new_url[:80]}...[/dim]")
                    
                    if '/posts/' in new_url or '/permalink/' in new_url:
                        clean_url = new_url.split('?')[0]
                        posts[post_index]['link'] = clean_url
                        console.print(f"[green]    [{idx+1}/{len(posts_needing_links)}] Got link: ...{clean_url[-50:]}[/green]")
                        got_link = True
                        
                        # Go back
                        await page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
                        await asyncio.sleep(2)
                    else:
                        console.print(f"[dim]    URL doesn't contain /posts/[/dim]")
                else:
                    console.print(f"[dim]    Button not found[/dim]")
            except Exception as e:
                console.print(f"[dim]    Comment click error: {str(e)[:50]}[/dim]")
            
            if not got_link:
                console.print(f"[dim]    [{idx+1}/{len(posts_needing_links)}] Could not get link via Comment button[/dim]")
                
        except Exception as e:
            console.print(f"[dim]    [{idx+1}/{len(posts_needing_links)}] Error: {str(e)[:50]}[/dim]")
            # Try to go back to search page
            try:
                if page.url != search_url:
                    await page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
                    await asyncio.sleep(2)
            except:
                pass
    
    return posts


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
