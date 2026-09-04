import os
import time
import csv
import json
import random
import logging
import argparse
import re
from typing import List, Dict, Set
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pathlib import Path

try:
    import undetected_chromedriver as uc
except ImportError:
    uc = None

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler("logs/crawler.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("crawler")

# Constants
MAX_WORKERS = 1 # Slow crawl as requested
RETRY_LIMIT = 3
MAX_RETRY_PER_URL = 2
DELAY_RANGE = (10, 20)
STATUS_PENDING = "pending"
STATUS_DONE = "done"
STATUS_FAILED = "failed"

# Chrome configuration from USER
CHROME_BINARY_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CHROMEDRIVER_PATH = r"C:\Users\admin\.wdm\drivers\chromedriver\win64\146.0.7680.165\chromedriver-win32/chromedriver.exe"

class URLStateManager:
    def __init__(self, csv_path):
        self.csv_path = Path(csv_path)
        self.lock = Lock()
        self._ensure_csv()

    def _ensure_csv(self):
        if not self.csv_path.exists():
            self.csv_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.csv_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["job_url", "category", "keyword", "status", "retry_count"])
                writer.writeheader()

    def save_urls_batch(self, items: List[dict]):
        with self.lock:
            existing = self._load_all()
            new_urls = []
            for item in items:
                if item["job_url"] not in existing:
                    item.update({"status": STATUS_PENDING, "retry_count": 0})
                    new_urls.append(item)
            
            if new_urls:
                with open(self.csv_path, "a", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=["job_url", "category", "keyword", "status", "retry_count"])
                    writer.writerows(new_urls)
            return len(new_urls)

    def _load_all(self) -> Dict[str, dict]:
        data = {}
        if not self.csv_path.exists(): return data
        with open(self.csv_path, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                data[row["job_url"]] = row
        return data

    def get_crawlable(self, done_urls: Set[str]) -> List[dict]:
        with self.lock:
            all_urls = self._load_all()
            return [
                v for k, v in all_urls.items() 
                if k not in done_urls and v["status"] != STATUS_DONE and int(v.get("retry_count", 0)) < MAX_RETRY_PER_URL
            ]

    def mark_done(self, url: str):
        self._update_status(url, STATUS_DONE)

    def mark_failed(self, url: str):
        with self.lock:
            all_urls = self._load_all()
            if url in all_urls:
                count = int(all_urls[url].get("retry_count", 0)) + 1
                all_urls[url]["retry_count"] = count
                all_urls[url]["status"] = STATUS_FAILED
                self._save_all(all_urls)

    def _update_status(self, url: str, status: str):
        with self.lock:
            all_urls = self._load_all()
            if url in all_urls:
                all_urls[url]["status"] = status
                self._save_all(all_urls)

    def _save_all(self, data: Dict[str, dict]):
        with open(self.csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["job_url", "category", "keyword", "status", "retry_count"])
            writer.writeheader()
            writer.writerows(data.values())

class ProductionTopCVCrawler:
    def __init__(self, target=3200, output_file="data/it_dataset_jobs_v2.csv", state_file="data/it_dataset_urls.csv"):
        self.target = target
        self.output_file = Path(output_file)
        self.state_file = Path(state_file)
        self.state_mgr = URLStateManager(self.state_file)
        
        self.done_urls = self._load_done_urls()
        self.stats = {"scraped": len(self.done_urls), "failed": 0, "skipped": 0}
        
        if not self.output_file.exists():
            self.output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.output_file, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["job_url", "job_title", "company_name", "location", "salary", "deadline", "description", "requirements", "category", "keyword"])

    def _load_done_urls(self) -> Set[str]:
        if not self.output_file.exists(): return set()
        try:
            with open(self.output_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                return {row["job_url"] for row in reader if row.get("job_url")}
        except: return set()

    def create_stealth_driver(self, headless=True):
        """Create a highly stealth driver using undetected-chromedriver."""
        if not uc:
            logger.error("undetected-chromedriver not installed.")
            return None
            
        try:
            options = uc.ChromeOptions()
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-popup-blocking")
            
            # Use random modern user-agents
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ]
            options.add_argument(f"--user-agent={random.choice(user_agents)}")
            
            if headless: options.add_argument("--headless")
            options.binary_location = CHROME_BINARY_PATH
            
            # Use the correct local driver to match Chrome 146
            driver = uc.Chrome(
                driver_executable_path=CHROMEDRIVER_PATH,
                version_main=146,
                options=options
            )
            
            driver.set_page_load_timeout(45)
            # Standard stealth patch for navigator.webdriver
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            })
            
            return driver
        except Exception as e:
            logger.error(f"Failed to create stealth driver: {e}")
            return None

    def parse_job_detail(self, driver, url, category, keyword):
        """Parse job details with robust handling for multiple layouts (Standard and Diamond)."""
        try:
            time.sleep(random.uniform(5, 10))
            # Initial Load
            driver.get(url)
            time.sleep(random.uniform(8, 15)) # Give it more time initially
            
            # Detect Cloudflare
            if "Just a moment" in driver.title or "Cloudflare" in driver.title or "Access denied" in driver.title:
                logger.warning(f"Blocked by Cloudflare at {url}. Attempting to wait/refresh...")
                time.sleep(30) # Passive wait for challenge
                driver.refresh()
                time.sleep(10)
                if "Just a moment" in driver.title:
                    # Final aggressive attempt: get directly again
                    logger.info(f"Retrying direct get for {url}")
                    driver.get(url)
                    time.sleep(15)

            if "Just a moment" in driver.title:
                logger.error(f"Still blocked at {url}")
                return None

            try:
                expand_selectors = [
                    ".btn-show-more", "#btn-show-more", ".show-more-desc",
                    "a[data-target='#job-description-modal']", ".see-more"
                ]
                for selector in expand_selectors:
                    try:
                        buttons = driver.find_elements(By.CSS_SELECTOR, selector)
                        for btn in buttons:
                            if btn.is_displayed():
                                driver.execute_script("arguments[0].click();", btn)
                                time.sleep(1)
                    except: pass
            except: pass

            soup = BeautifulSoup(driver.page_source, 'lxml')
            
            is_diamond = bool(soup.find(class_='job-description__header') or soup.find(class_='btn-diamond'))
            
            if is_diamond:
                title_el = soup.find(class_='job-description__header-title') or soup.find('h1')
                title_text = title_el.text.strip() if title_el else "N/A"
                
                company_el = soup.find(class_='navbar-diamond-company-brand') or \
                             soup.find(class_='company-name') or \
                             soup.find(class_='company')
                company_text = company_el.get('title') or company_el.get_text().strip() if company_el else "N/A"
                
                salary = "Thoả thuận"
                location = "N/A"
                deadline = "N/A"
                
                summary = soup.find(class_='job-description__header-info')
                if summary:
                    deadline_el = summary.find(class_='job-description__header-status')
                    if deadline_el: deadline = deadline_el.text.strip()
                
                for item in soup.find_all(class_='job-detail-v2__info-item'):
                    lbl = item.find(class_='job-detail-v2__info-item-label')
                    val = item.find(class_='job-detail-v2__info-item-value')
                    if lbl and val:
                        ltext = lbl.text.strip().lower()
                        vtext = val.text.strip()
                        if "mức lương" in ltext: salary = vtext
                        elif "địa điểm" in ltext:
                            # Diamond layout location - often in val
                            loc_link = val.find('a', href=re.compile(r'/tim-viec-lam-.*-tai-.*-kl'))
                            location = loc_link.text.strip() if loc_link else vtext
                
                description = ""
                requirements = ""
                
                for section in soup.find_all(class_='job-description__item'):
                    header = section.find(['h3', 'h4', 'div'], class_='job-description__item-title') or section.find('h3')
                    content = section.find(class_='job-description__item-content')
                    if header and content:
                        htext = header.text.strip().lower()
                        ctext = content.get_text(separator=" ").strip()
                        if "địa điểm" in htext: location = ctext
                        elif "mô tả" in htext: description = ctext
                        elif "yêu cầu" in htext: requirements = ctext
            else:
                title = soup.find('h1', class_='job-detail__info--title') or soup.find('h1')
                title_text = title.text.strip() if title else "N/A"
                if "topcv" in title_text.lower() or "www." in title_text.lower():
                    title_text = "N/A"
                
                company = soup.find('a', class_='name', attrs={'data-original-title': True}) or \
                          soup.find('div', class_='job-detail__company--name') or \
                          soup.find('h2')
                company_text = company.get('data-original-title') or company.text.strip() if company else "N/A"
                
                location = "N/A"
                salary = "Thoả thuận"
                deadline = "N/A"
                
                deadline_el = soup.find('div', class_='job-detail__info--deadline-date')
                if deadline_el: deadline = deadline_el.text.strip()
                
                # ── LAYOUT 1: div.info > div.label-content > label.address (current TopCV 2025) ──
                new_layout_found = False
                for info_div in soup.find_all('div', class_='info'):
                    label_content = info_div.find('div', class_='label-content')
                    if not label_content: continue
                    addr_label = label_content.find('label', class_='address')
                    if addr_label:
                        loc_text = addr_label.get_text(separator=", ").strip()
                        if loc_text and loc_text.lower() not in ["n/a", "địa điểm"]:
                            location = loc_text
                            new_layout_found = True
                            break
                    # Also try any city-name spans in label-content
                    city_spans = [s.text.strip() for s in label_content.find_all('span')
                                  if any(c in s.text for c in ["Hà Nội", "Hồ Chí Minh", "Đà Nẵng", "Hải Phòng", "Cần Thơ", "Bình Dương", "Đồng Nai"])]
                    if city_spans:
                        location = ", ".join(city_spans)
                        new_layout_found = True
                        break
                
                # ── LAYOUT 2: .job-info_content / .col-job-info (interim layout) ──
                if not new_layout_found:
                    for el in soup.select(".job-info_content, .col-job-info")[:10]:
                        loc_links = el.find_all('a', href=re.compile(r'/tim-viec-lam-.*-kl\d'))
                        if loc_links:
                            location = ", ".join([a.text.strip() for a in loc_links if a.text.strip()])
                            new_layout_found = True
                            break
                
                # ── LAYOUT 3: Index-based (2nd content-value = location, per reference code) ──
                # Ref: driver.find_element(XPath, "(//div[contains(@class, 'job-detail__info--section')]/div[contains(@class,'job-detail__info--section-content-value')])[2]")
                if not new_layout_found:
                    all_vals = soup.select("div.job-detail__info--section div.job-detail__info--section-content-value")
                    if len(all_vals) >= 2:
                        loc_text = all_vals[1].get_text(separator=", ").strip()
                        if loc_text and loc_text.lower() not in ["n/a", "địa điểm"]:
                            location = loc_text
                            new_layout_found = True
                
                # ── LAYOUT 4: .job-detail__info--section with label matching (old) ──
                info_sections = soup.find_all('div', class_='job-detail__info--section')
                for sec in info_sections:
                    label_el = sec.find('div', class_='job-detail__info--section-label')
                    value_el = sec.find('div', class_='job-detail__info--section-content-value')
                    if label_el and value_el:
                        lbl = label_el.text.strip().lower()
                        val = value_el.text.strip()
                        if "mức lương" in lbl: salary = val
                        elif "địa điểm" in lbl and not new_layout_found:
                            loc_link = value_el.find('a', href=re.compile(r'/tim-viec-lam-.*-tai-.*-kl'))
                            if not loc_link:
                                loc_link = value_el.find('a')
                            if loc_link:
                                location = loc_link.text.strip()
                            else:
                                location = val
                                if not location or location == "N/A":
                                    tooltip = value_el.find(attrs={"data-original-title": True})
                                    if tooltip:
                                        tooltip_soup = BeautifulSoup(tooltip['data-original-title'], 'lxml')
                                        location = tooltip_soup.get_text(separator=" ").strip()
                
                # ── Salary fallback ──
                if salary == "Thoả thuận":
                    # Also try 1st content-value = salary
                    if all_vals:
                        sal_text = all_vals[0].get_text(separator=", ").strip()
                        if sal_text and sal_text.lower() not in ["n/a"]:
                            salary = sal_text
                    else:
                        sal_el = soup.select_one(".job-info__salary, [class*='salary']")
                        if sal_el: salary = sal_el.text.strip()
                
                if deadline == "N/A":
                    for item in soup.find_all('div', class_='job-detail__info--section-content-value'):
                        text = item.text.strip()
                        if any(x in text.lower() for x in ["tháng", "202", "/"]) and len(text) < 20: 
                            deadline = text

                description = ""
                requirements = ""
                content_sections = soup.find_all(['div', 'section'], class_=re.compile(r'job-description|job-detail__section'))
                full_text = ""
                for section in content_sections:
                    full_text += section.get_text(separator="\n") + "\n"
                
                if not full_text:
                    main_content = soup.find('div', id='job-detail') or soup.find('div', class_='col-md-9')
                    if main_content: full_text = main_content.get_text(separator="\n")

                parts = re.split(r'(Mô tả công việc|Yêu cầu ứng viên|Quyền lợi|Cách thức ứng tuyển|Yêu cầu công việc|Yêu cầu|Kỹ năng)', full_text, flags=re.IGNORECASE)
                for i in range(1, len(parts), 2):
                    header = parts[i].lower()
                    content = parts[i+1].strip()
                    if "mô tả" in header: description = content
                    elif "yêu cầu" in header or "kỹ năng" in header: requirements = content
                
                if not description and not requirements and full_text:
                    description = full_text[:1000]
                    requirements = full_text[1000:2000]

            return {
                "job_url": url,
                "job_title": title_text,
                "company_name": company_text,
                "location": location,
                "salary": salary,
                "deadline": deadline,
                "description": description.replace("\n", " ").strip(),
                "requirements": requirements.replace("\n", " ").strip(),
                "category": category,
                "keyword": keyword
            }
        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")
            return None

    def worker(self, url_item, driver_meta):
        url = url_item["job_url"]
        category = url_item.get("category", "N/A")
        keyword = url_item.get("keyword", "N/A")
        time.sleep(random.uniform(5, 10))
        
        for attempt in range(RETRY_LIMIT):
            driver = None
            try:
                idx = random.randint(0, MAX_WORKERS - 1)
                driver = driver_meta['drivers'][idx]
                if not driver:
                    logger.info(f"Connecting to Chrome (attempt {attempt+1}/{RETRY_LIMIT})...")
                    driver = self.create_stealth_driver()
                    driver_meta['drivers'][idx] = driver
                if not driver: continue

                data = self.parse_job_detail(driver, url, category, keyword)
                if data:
                    with open(self.output_file, "a", encoding="utf-8", newline="") as f:
                        writer = csv.DictWriter(f, fieldnames=data.keys())
                        writer.writerow(data)
                    self.state_mgr.mark_done(url)
                    num_done = len(self._load_done_urls())
                    logger.info(f"  [{num_done}/{self.target}] [OK] {data['job_title'][:40]}")
                    return
                else:
                    logger.warning(f"  [RETRY {attempt+1}] {url}")
                    try: driver.quit()
                    except: pass
                    driver_meta['drivers'][idx] = None
            except Exception as e:
                logger.error(f"Worker session error: {e}")
                driver_meta['drivers'][idx] = None
        self.state_mgr.mark_failed(url)

    def scrape_urls(self, url_items):
        if not url_items:
            logger.info("No URLs to scrape.")
            return
        logger.info(f"PHASE 2: Scraping {len(url_items)} URLs...")
        driver_meta = {'drivers': [None] * MAX_WORKERS}
        try:
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                for item in url_items:
                    executor.submit(self.worker, item, driver_meta)
                    time.sleep(random.uniform(*DELAY_RANGE))
                    if len(self._load_done_urls()) >= self.target:
                        break
        finally:
            for d in driver_meta['drivers']:
                try: 
                    if d: d.quit()
                except: pass
        
    def run(self, mode="all", url_file=None):
        if mode == "urls" and url_file:
            if os.path.exists(url_file):
                with open(url_file, "r", encoding="utf-8") as f:
                    new_items = list(csv.DictReader(f))
                    self.state_mgr.save_urls_batch(new_items)
        
        done_urls = self._load_done_urls()
        to_crawl = self.state_mgr.get_crawlable(done_urls)
        num_scraped_total = len(done_urls)
        remaining_to_target = self.target - num_scraped_total
        
        if remaining_to_target <= 0:
            logger.info(f"Target of {self.target} already reached ({num_scraped_total} in file).")
            return
        logger.info(f"Found {len(to_crawl)} crawlable URLs. Target: {self.target}. Remaining: {remaining_to_target}")
        self.scrape_urls(to_crawl[:remaining_to_target])

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["all", "urls"], default="all")
    parser.add_argument("--url-file", default=None)
    parser.add_argument("--target", type=int, default=3200)
    parser.add_argument("--output", default="data/it_dataset_jobs_v2.csv")
    parser.add_argument("--state", default="data/it_dataset_urls.csv")
    args = parser.parse_args()
    crawler = ProductionTopCVCrawler(target=args.target, output_file=args.output, state_file=args.state)
    crawler.run(mode=args.mode, url_file=args.url_file)
