"""
Configuration and constants
"""

# Browser settings
BROWSER_ARGS = [
    '--disable-blink-features=AutomationControlled',
    '--disable-infobars',
    '--no-sandbox',
    '--disable-dev-shm-usage',
]

# Window settings for tiled layout
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
VIEWPORT = {'width': WINDOW_WIDTH, 'height': WINDOW_HEIGHT}

# Grid layout (2 columns)
GRID_COLS = 2
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
LOCALE = 'vi-VN'

# Scroll settings
DEFAULT_SCROLL_DELAY = 2.0
DEFAULT_MAX_SCROLLS = 100
MAX_NO_NEW_POSTS = 5

# Text patterns to skip (UI elements)
SKIP_PATTERNS = [
    'Thích', 'Bình luận', 'Chia sẻ', 'Like', 'Comment', 'Share',
    'Tất cả cảm xúc', 'All reactions', 'bình luận', 'comments',
    'lượt chia sẻ', 'shares', 'Trả lời', 'Reply', 'Phản hồi',
]

# End of results indicators
END_OF_RESULTS_TEXTS = ['Đã hết kết quả', 'No more results', 'End of results']

# Expand button texts
EXPAND_BUTTON_TEXTS = ['Xem thêm', 'See more', 'View more', '...more']
