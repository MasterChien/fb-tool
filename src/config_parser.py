"""
Config file parser module
"""

from pathlib import Path
from dataclasses import dataclass


def group_keywords_by_prefix(keywords: list[str]) -> list[tuple[str, list[str]]]:
    """
    Gom nhóm keyword theo tiền tố chung.
    VD: ["lừa đảo", "lừa lọc", "lừa"] -> [("lừa", ["lừa đảo", "lừa lọc", "lừa"])]
    Chỉ cần search "lừa" trên FB, sau đó phân loại post theo từng keyword.

    Returns:
        List of (search_term, [keyword1, keyword2, ...])
    """
    if not keywords:
        return []

    # Sắp xếp theo độ dài (ngắn nhất trước) để từ ngắn có thể là tiền tố của từ dài
    sorted_kw = sorted(set(k.strip() for k in keywords if k.strip()), key=len)
    used = set()
    groups: list[tuple[str, list[str]]] = []

    for kw in sorted_kw:
        if kw in used:
            continue
        # Nhóm gồm kw và mọi keyword khác có kw là tiền tố (bắt đầu bằng kw + khoảng trắng hoặc bằng kw)
        group = [kw]
        used.add(kw)
        for other in sorted_kw:
            if other in used:
                continue
            # other bằng kw hoặc có kw là tiền tố (kw + khoảng trắng hoặc kw + ký tự)
            if other == kw or other.startswith(kw):
                group.append(other)
                used.add(other)
        groups.append((kw, group))

    return groups


@dataclass
class ScanConfig:
    """Configuration for scanning"""
    number_of_browser: int
    scrolls: int
    groups: list[str]
    keywords: list[str]
    headless: bool = True  # Default headless for large batches
    extract_links: bool = False  # Extract post links by clicking (slower)

    def get_keyword_groups(self) -> list[tuple[str, list[str]]]:
        """Gom nhóm keywords theo tiền tố. Returns [(search_term, [k1, k2, ...]), ...]"""
        return group_keywords_by_prefix(self.keywords)

    def get_all_pairs(self) -> list[tuple[str, str]]:
        """
        Generate all (group, keyword) pairs (dùng cho backward compat / display).
        """
        pairs = []
        for group in self.groups:
            for keyword in self.keywords:
                pairs.append((group, keyword))
        return pairs

    def get_grouped_pairs(self) -> list[tuple[str, str, list[str]]]:
        """
        Cặp sau khi gom nhóm: mỗi cặp (group_id, search_term, keyword_list).
        Số lượng ít hơn vì nhiều keyword dùng chung 1 search_term.
        """
        groups_kw = self.get_keyword_groups()
        pairs: list[tuple[str, str, list[str]]] = []
        for group in self.groups:
            for search_term, keyword_list in groups_kw:
                pairs.append((group, search_term, keyword_list))
        return pairs

    def __str__(self) -> str:
        grouped = self.get_keyword_groups()
        total_searches = len(self.groups) * len(grouped)
        return (
            f"ScanConfig(\n"
            f"  browsers: {self.number_of_browser}\n"
            f"  scrolls: {self.scrolls}\n"
            f"  headless: {self.headless}\n"
            f"  extract_links: {self.extract_links}\n"
            f"  groups: {len(self.groups)} groups\n"
            f"  keywords: {len(self.keywords)} (gom thanh {len(grouped)} search term)\n"
            f"  total searches: {total_searches} (thay vi {len(self.groups) * len(self.keywords)})\n"
            f")"
        )


def parse_config(config_file: str = "config.txt") -> ScanConfig:
    """
    Parse configuration from file
    
    Config format:
        number_of_browser=3
        scrolls=30
        groups=group1, group2, group3
        keywords=keyword1, keyword2
    
    Args:
        config_file: Path to config file
        
    Returns:
        ScanConfig object
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config format is invalid
    """
    config_path = Path(config_file)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_file}")
    
    config_data = {}
    
    with open(config_file, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue
            
            # Parse key=value
            if "=" not in line:
                raise ValueError(f"Invalid config format at line {line_num}: {line}")
            
            key, value = line.split("=", 1)
            key = key.strip().lower()
            value = value.strip()
            
            config_data[key] = value
    
    # Validate required fields (support both singular and plural form)
    # Normalize number_of_browsers to number_of_browser
    if "number_of_browsers" in config_data:
        config_data["number_of_browser"] = config_data["number_of_browsers"]
    
    required_fields = ["number_of_browser", "scrolls", "groups", "keywords"]
    for field in required_fields:
        if field not in config_data:
            raise ValueError(f"Missing required config field: {field}")
    
    # Parse values
    try:
        number_of_browser = int(config_data["number_of_browser"])
        if number_of_browser < 1:
            raise ValueError("number_of_browser must be at least 1")
    except ValueError as e:
        raise ValueError(f"Invalid number_of_browser: {e}")
    
    try:
        scrolls = int(config_data["scrolls"])
        if scrolls < 1:
            raise ValueError("scrolls must be at least 1")
    except ValueError as e:
        raise ValueError(f"Invalid scrolls: {e}")
    
    # Parse comma-separated lists with trimming
    groups = [g.strip() for g in config_data["groups"].split(",") if g.strip()]
    if not groups:
        raise ValueError("groups cannot be empty")
    
    keywords = [k.strip() for k in config_data["keywords"].split(",") if k.strip()]
    if not keywords:
        raise ValueError("keywords cannot be empty")
    
    # Parse headless option (default: true for efficiency)
    headless = True
    if "headless" in config_data:
        headless_val = config_data["headless"].lower()
        headless = headless_val in ("true", "1", "yes", "on")
    
    # Parse extract_links option (default: false as it's slower)
    extract_links = False
    if "extract_links" in config_data:
        extract_links_val = config_data["extract_links"].lower()
        extract_links = extract_links_val in ("true", "1", "yes", "on")
    
    return ScanConfig(
        number_of_browser=number_of_browser,
        scrolls=scrolls,
        groups=groups,
        keywords=keywords,
        headless=headless,
        extract_links=extract_links
    )
