"""
Config file parser module
"""

from pathlib import Path
from dataclasses import dataclass


@dataclass
class ScanConfig:
    """Configuration for scanning"""
    number_of_browser: int
    scrolls: int
    groups: list[str]
    keywords: list[str]
    
    def get_all_pairs(self) -> list[tuple[str, str]]:
        """
        Generate all (group, keyword) pairs
        
        Returns:
            List of (group_id, keyword) tuples
        """
        pairs = []
        for group in self.groups:
            for keyword in self.keywords:
                pairs.append((group, keyword))
        return pairs
    
    def __str__(self) -> str:
        return (
            f"ScanConfig(\n"
            f"  browsers: {self.number_of_browser}\n"
            f"  scrolls: {self.scrolls}\n"
            f"  groups: {self.groups}\n"
            f"  keywords: {self.keywords}\n"
            f"  total pairs: {len(self.groups) * len(self.keywords)}\n"
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
    
    return ScanConfig(
        number_of_browser=number_of_browser,
        scrolls=scrolls,
        groups=groups,
        keywords=keywords
    )
