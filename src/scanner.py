"""
Main scanning logic module
"""

import asyncio
from datetime import datetime
from playwright.async_api import Page
from rich.console import Console

from .config import DEFAULT_SCROLL_DELAY, EMPTY_SCROLL_LIMIT, DEFAULT_MAX_SCROLLS
from .extractor import extract_posts, expand_all_posts, check_end_of_results
from .utils import extract_snippet

console = Console(force_terminal=True)


def _match_keywords(content: str, keyword_list: list[str]) -> list[str]:
    """Trả về danh sách keyword trong keyword_list mà content chứa (case-insensitive)."""
    import re
    matched = []
    content_lower = content.lower()
    for kw in keyword_list:
        if not kw:
            continue
        escaped = re.escape(kw)
        if re.search(escaped, content_lower, re.IGNORECASE):
            matched.append(kw)
    return matched


async def scroll_and_collect_posts(
    page: Page,
    search_term: str,
    keyword_list: list[str] | None = None,
    max_scrolls: int | None = None,
    scroll_delay: float = DEFAULT_SCROLL_DELAY
) -> list[dict]:
    """
    Scroll page và thu thập post. Search trên FB bằng search_term; mỗi post
    được gán matched_keywords = [các keyword trong keyword_list mà post chứa].

    - keyword_list: None hoặc [keyword1, ...] (cùng tiền tố với search_term).
      Nếu None thì dùng [search_term] (1 keyword).
    """
    import re

    if keyword_list is None:
        keyword_list = [search_term]
    if max_scrolls is None:
        max_scrolls = DEFAULT_MAX_SCROLLS

    posts_found: list[dict] = []
    seen_content_hashes = set()
    scroll_num = 0
    empty_scroll_count = 0

    kw_preview = ", ".join(keyword_list[:5]) + ("..." if len(keyword_list) > 5 else "")
    console.print(f"\n[cyan]Tim kiem '{search_term}' (phan loai theo: {kw_preview})...[/cyan]")
    console.print(f"[dim]Dung khi lien tiep {EMPTY_SCROLL_LIMIT} lan scroll khong co post moi[/dim]\n")

    console.print(f"[dim]Cho trang load...[/dim]")
    await asyncio.sleep(3)

    while scroll_num < max_scrolls:
        scroll_num += 1
        posts_before = len(posts_found)

        expanded = await expand_all_posts(page)
        if expanded > 0 and scroll_num <= 3:
            console.print(f"[dim]  Da expand {expanded} posts[/dim]")
            await asyncio.sleep(1)

        raw_posts = await extract_posts(page, search_term, debug=(scroll_num == 1))
        if scroll_num == 1:
            console.print(f"[dim]Tim thay {len(raw_posts)} posts chua '{search_term}'[/dim]")

        for post_data in raw_posts:
            try:
                content = post_data.get("content", "")
                link = post_data.get("link", "")
                author = post_data.get("author", "Unknown")
                author_link = post_data.get("author_link", "")

                if len(content) < 10:
                    continue

                normalized = re.sub(r'[\s\.,\?\!\:\;\-\(\)\[\]\"\']+', '', content).lower()[:200]
                content_hash = hash(normalized)
                if content_hash in seen_content_hashes:
                    continue
                seen_content_hashes.add(content_hash)

                matched_kw = _match_keywords(content, keyword_list)
                if not matched_kw:
                    continue

                snippet = extract_snippet(content, search_term, 150)
                post = {
                    "author": author,
                    "author_link": author_link,
                    "snippet": snippet,
                    "link": link,
                    "full_text": content[:2000],
                    "found_at": datetime.now().isoformat(),
                    "matched_keywords": matched_kw,
                }
                posts_found.append(post)
                console.print(f"  [green][+][/green] #{len(posts_found)} - [bold]{author[:30]}[/bold] [dim]({', '.join(matched_kw)})[/dim]")
            except Exception:
                continue

        posts_after = len(posts_found)
        new_posts_this_scroll = posts_after - posts_before

        if new_posts_this_scroll == 0:
            empty_scroll_count += 1
        else:
            empty_scroll_count = 0

        console.print(f"[dim]  Scroll {scroll_num}: +{new_posts_this_scroll} posts moi (tong: {len(posts_found)}), empty_scroll={empty_scroll_count}[/dim]")

        if empty_scroll_count >= EMPTY_SCROLL_LIMIT:
            console.print(f"\n[yellow]Lien tiep {EMPTY_SCROLL_LIMIT} lan scroll khong co post moi. Chuyen cap tiep theo.[/yellow]")
            break

        if await check_end_of_results(page):
            console.print(f"\n[green]Da tim het ket qua! (Facebook bao 'Da het ket qua')[/green]")
            break

        if empty_scroll_count > 0:
            console.print(f"[dim]  Cho load ({scroll_delay + 2}s) truoc khi scroll tiep...[/dim]")
            await asyncio.sleep(scroll_delay + 2)

        current_height = await page.evaluate("document.body.scrollHeight")
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(scroll_delay + 1)

        new_height = await page.evaluate("document.body.scrollHeight")
        if new_height == current_height:
            console.print(f"[dim]  Dang cho Facebook load them...[/dim]")
            await asyncio.sleep(4)
            new_height = await page.evaluate("document.body.scrollHeight")
            if new_height == current_height:
                await page.evaluate("window.scrollBy(0, -500)")
                await asyncio.sleep(1)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(3)

    return posts_found
