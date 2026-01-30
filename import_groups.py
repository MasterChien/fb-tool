#!/usr/bin/env python
"""
Import group IDs from Excel file and update config.txt

Usage:
    python import_groups.py <excel_file> [--column <name_or_index>]
    
Examples:
    python import_groups.py groups.xlsx
    python import_groups.py groups.xlsx --column 4
    python import_groups.py groups.xlsx --column "Link"
"""

import sys
import os
import re
import argparse

# Fix encoding for Windows
if sys.platform == "win32":
    os.system("chcp 65001 >nul 2>&1")
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

try:
    import pandas as pd
except ImportError:
    print("Error: pandas not installed. Run: pip install pandas openpyxl")
    sys.exit(1)


def extract_group_id(url: str) -> str | None:
    """Extract group ID from Facebook URL"""
    if not url or pd.isna(url):
        return None
    
    match = re.search(r'facebook\.com/groups/([^/?]+)', str(url))
    if match:
        return match.group(1)
    return None


def find_link_column(df: pd.DataFrame) -> int:
    """Find column containing Facebook links"""
    for i, col in enumerate(df.columns):
        # Check first few values in this column
        sample = df.iloc[:5, i].astype(str)
        if any('facebook.com/groups/' in str(v) for v in sample):
            return i
    return -1


def import_groups(excel_file: str, column=None) -> list[str]:
    """
    Import group IDs from Excel file
    
    Args:
        excel_file: Path to Excel file
        column: Column name or index (auto-detect if None)
        
    Returns:
        List of group IDs
    """
    print(f"Reading: {excel_file}")
    df = pd.read_excel(excel_file)
    
    print(f"Columns: {list(df.columns)}")
    print(f"Rows: {len(df)}")
    
    # Determine which column to use
    if column is not None:
        if isinstance(column, int) or column.isdigit():
            col_idx = int(column)
        else:
            # Try to find by name
            col_idx = -1
            for i, c in enumerate(df.columns):
                if column.lower() in str(c).lower():
                    col_idx = i
                    break
            if col_idx == -1:
                print(f"Error: Column '{column}' not found")
                return []
    else:
        # Auto-detect column with Facebook links
        col_idx = find_link_column(df)
        if col_idx == -1:
            print("Error: Could not find column with Facebook links")
            print("Try specifying column with --column option")
            return []
    
    print(f"Using column {col_idx}: {df.columns[col_idx]}")
    
    # Extract group IDs
    links = df.iloc[:, col_idx].tolist()
    group_ids = []
    
    for link in links:
        gid = extract_group_id(link)
        if gid:
            group_ids.append(gid)
    
    return group_ids


def update_config(group_ids: list[str], config_file: str = "config.txt"):
    """Update config.txt with new group IDs"""
    if not os.path.exists(config_file):
        print(f"Error: {config_file} not found")
        return False
    
    with open(config_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Find and update groups line
    new_lines = []
    groups_updated = False
    
    for line in lines:
        if line.strip().startswith('groups='):
            new_lines.append(f"groups={','.join(group_ids)}\n")
            groups_updated = True
        else:
            new_lines.append(line)
    
    if not groups_updated:
        new_lines.append(f"\ngroups={','.join(group_ids)}\n")
    
    with open(config_file, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Import Facebook group IDs from Excel file"
    )
    parser.add_argument("excel_file", help="Path to Excel file")
    parser.add_argument("--column", "-c", help="Column name or index containing links")
    parser.add_argument("--output", "-o", default="config.txt", help="Output config file")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Don't update config, just show groups")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.excel_file):
        print(f"Error: File not found: {args.excel_file}")
        sys.exit(1)
    
    # Import groups
    group_ids = import_groups(args.excel_file, args.column)
    
    if not group_ids:
        print("No groups found!")
        sys.exit(1)
    
    print(f"\nFound {len(group_ids)} groups:")
    for i, gid in enumerate(group_ids[:10], 1):
        print(f"  {i}. {gid}")
    if len(group_ids) > 10:
        print(f"  ... and {len(group_ids) - 10} more")
    
    if args.dry_run:
        print(f"\nDry run - config not updated")
        print(f"Groups: {','.join(group_ids)}")
    else:
        if update_config(group_ids, args.output):
            print(f"\nUpdated {args.output} with {len(group_ids)} groups")
        else:
            print(f"\nFailed to update {args.output}")
            sys.exit(1)


if __name__ == "__main__":
    main()
