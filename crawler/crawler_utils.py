"""
crawler_utils.py
Shared utilities: logging, Chrome driver, retry, CSV helpers.
"""
import logging
import time
import random
import os
import csv
import re
from typing import Optional

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

try:
    from webdriver_manager.chrome import ChromeDriverManager
    _USE_WDM = True
except ImportError:
    _USE_WDM = False


# ── Logging ────────────────────────────────────────────────────────────────────

os.makedirs("logs", exist_ok=True)

logger = logging.getLogger("crawler")
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    # File handler – full DEBUG log
    fh = logging.FileHandler("logs/crawler.log", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # Console handler – INFO only
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)


# ── Chrome driver ──────────────────────────────────────────────────────────────

# Realistic user-agent to avoid bot detection
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/145.0.0.0 Safari/537.36"
)


def create_driver(headless: bool = True) -> webdriver.Chrome:
    """Create and return a stealth Chrome WebDriver instance."""
    options = Options()

    if headless:
        options.add_argument("--headless=new")

    # Core flags
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-popup-blocking")
    options.add_argument(f"--user-agent={_USER_AGENT}")

    # Anti-bot stealth
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # Memory optimization
    prefs = {
        "profile.managed_default_content_settings.images": 2
    }
    options.add_experimental_option("prefs", prefs)

    if _USE_WDM:
        service = Service(ChromeDriverManager().install())
    else:
        service = Service()

    driver = webdriver.Chrome(service=service, options=options)

    # Patch navigator.webdriver = undefined
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"}
    )

    driver.set_page_load_timeout(30)
    driver.implicitly_wait(5)

    return driver


# ── Retry decorator ────────────────────────────────────────────────────────────

def with_retry(max_attempts: int = 3):
    """Tenacity retry decorator for network/parse operations."""
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )


def scroll_to_bottom(driver, scroll_pause_time=1.5, max_scrolls=10):
    """
    Scroll down the page to trigger lazy loading of content.
    """
    last_height = driver.execute_script("return document.body.scrollHeight")
    scroll_count = 0
    
    while scroll_count < max_scrolls:
        # Scroll down to bottom
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        
        # Wait to load page
        time.sleep(scroll_pause_time)
        
        # Calculate new scroll height and compare with last scroll height
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height
        scroll_count += 1
    
    # Return to top for further processing if needed
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(0.5)

def normalize_text(text: Optional[str]) -> str:
    """
    Deep cleaning of text for ML readiness.
    - Standardizes whitespace
    - Removes non-printable characters
    - Ensures UTF-8 consistency
    """
    if not text:
        return ""
    
    # Remove non-breaking spaces and other weird whitespace
    text = text.replace("\xa0", " ").replace("\t", " ")
    
    # Normalize multiple spaces to one
    text = re.sub(r"\s+", " ", text)
    
    # Strip leading/trailing whitespace
    return text.strip()

# ── Timing helpers ─────────────────────────────────────────────────────────────

def random_delay(min_sec: float = 1.5, max_sec: float = 4.0):
    """Sleep for a random duration to mimic human browsing."""
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)


# ── CSV helpers ────────────────────────────────────────────────────────────────

def load_csv_set(filepath: str, column: str) -> set:
    """
    Return a set of values from a single CSV column.
    Used to track which URLs have already been crawled (resume support).
    """
    values: set = set()
    if not os.path.exists(filepath):
        return values
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                val = row.get(column, "").strip()
                if val:
                    values.add(val)
    except Exception as e:
        logger.warning(f"Could not load CSV {filepath}: {e}")
    return values


def append_to_csv(filepath: str, data: dict, fieldnames: list):
    """
    Append one row to a CSV file.
    Writes the header automatically if the file does not yet exist.
    """
    file_exists = os.path.exists(filepath) and os.path.getsize(filepath) > 0
    with open(filepath, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if not file_exists:
            writer.writeheader()
        writer.writerow({k: data.get(k, "") for k in fieldnames})


def load_csv_list(filepath: str, column: str) -> list:
    """Return an ordered list of values from a CSV column (preserves order)."""
    items = []
    if not os.path.exists(filepath):
        return items
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                val = row.get(column, "").strip()
                if val and val not in items:
                    items.append(val)
    except Exception as e:
        logger.warning(f"Could not load CSV list {filepath}: {e}")
    return items
