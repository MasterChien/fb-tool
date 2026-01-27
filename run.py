#!/usr/bin/env python
"""
Facebook Group Keyword Scanner

Reads configuration from config.txt and scans Facebook groups for keywords.

Config format (config.txt):
    number_of_browsers=3
    scrolls=30
    groups=group1, group2
    keywords=keyword1, keyword2
"""

import sys
import os
import asyncio

# Fix encoding for Windows
if sys.platform == "win32":
    os.system("chcp 65001 >nul 2>&1")
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rich.console import Console

console = Console(force_terminal=True)


def main():
    """Main entry point - reads from config.txt"""
    from src.config_parser import parse_config
    from src.batch_runner import run_batch
    
    try:
        # Parse config
        config = parse_config("config.txt")
        console.print(f"[green]Config loaded successfully[/green]")
        console.print(str(config))
        
        # Run batch
        asyncio.run(run_batch(
            config=config,
            cookie_file="www_facebook_com_cookies.json",
            headless=False
        ))
        
    except FileNotFoundError as e:
        console.print(f"[red][X] {e}[/red]")
        console.print("[yellow]Create config.txt with format:[/yellow]")
        console.print("  number_of_browsers=3")
        console.print("  scrolls=30")
        console.print("  groups=group1, group2")
        console.print("  keywords=keyword1, keyword2")
        sys.exit(1)
        
    except ValueError as e:
        console.print(f"[red][X] Config error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
