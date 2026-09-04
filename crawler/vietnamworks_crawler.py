"""
vietnamworks_crawler.py – Senior-grade VietnamWorks Job Crawler
===============================================================
STRATEGY: Hybrid Extraction
  Phase 1: Listing Page – Collect unique Job URLs.
  Phase 2: Detail Page  – Extract all fields with precise selectors.

FEATURES:
  ✅ Precise selectors for Company (.company-name) and Description (.description).
  ✅ Automated 'Expand' click for full descriptions.
  ✅ Batch crawling via IT_CATEGORIES dictionary.
  ✅ Parallel workers for detail pages.
"""

import argparse
import csv
import logging
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

try:
    from webdriver_manager.chrome import ChromeDriverManager
    _USE_WDM = True
except ImportError:
    _USE_WDM = False

# ──────────────────────────────────────────────────────────────────────────────
# CONFIG & CATEGORIES
# ──────────────────────────────────────────────────────────────────────────────

BASE_URL = "https://www.vietnamworks.com"
# Updated Search URL with specific job function IDs:
# j=36 (Phần mềm), 34 (Dữ liệu/AI), 35 (Bảo mật), 33 (QA/QC), 31 (IT Support)
# g=5 is IT/Telecommunications
# j=36: Software, 34: Data/AI, 35: Security, 33: QA/QC, 31: IT Support
SEARCH_URL = "https://www.vietnamworks.com/viec-lam?q={keyword}&g=5&j=36,34,35,33,31&page={page}"
# General IT listing — uses g=5 with keyword but WITHOUT the restrictive j= filter
# This casts a wider net than SEARCH_URL
GENERAL_IT_URL = "https://www.vietnamworks.com/viec-lam?g=5&q={keyword}&page={page}"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# Standardized fields as per user request
CSV_COLUMNS = [
    "job_url", "job_title", "company_name", "location", "salary", 
    "deadline", "description", "requirements", "category", "keyword"
]

# Standardized IT Categories (10 groups)
IT_CATEGORIES = {
    "BACKEND": ["Backend", "Java", "Spring", "API", "Microservices", "NodeJS", "Golang", "PHP", "Laravel", "Python", "C#", ".NET", "Ruby"],
    "FRONTEND": ["Frontend", "React", "Angular", "Vue", "HTML", "CSS", "JavaScript", "TypeScript"],
    "FULLSTACK": ["Fullstack"],
    "DATA": ["Data Scientist", "Data Engineer", "Machine Learning", "AI", "TensorFlow", "PyTorch", "Deep Learning", "NLP", "Computer Vision"],
    "MOBILE": ["Android", "iOS", "Flutter", "React Native", "Swift", "Kotlin"],
    "DEVOPS": ["DevOps", "Cloud", "AWS", "Docker", "Kubernetes"],
    "SECURITY": ["Security", "Cyber Security", "Pentest", "Information Security"],
    "QA": ["Tester", "QA", "Automation Test", "Software Tester"],
    "EMBEDDED": ["Embedded", "IoT", "Firmware"],
    "GAME": ["Game Developer", "Unity", "Unreal"]
}

# Positive IT keywords for general detection
IT_POSITIVE_KEYWORDS = [
    "software engineer", "software developer", "web developer", "mobile developer",
    "android developer", "ios developer", "cloud engineer", "system engineer",
    "network engineer", "security engineer", "nlp engineer", "embedded engineer",
    "iot engineer", "qa engineer", "database administrator", "dba", "blockchain developer",
    "python", "java", "c++", "c#", "javascript", "typescript", "go", "rust", "php", "ruby", "kotlin", "swift",
    "react", "angular", "vue", "nodejs", "spring boot", "django", "flask", ".net", "laravel", "tensorflow", "pytorch"
]

# Negative non-IT groups
NON_IT_GROUPS = [
    "marketing", "sales", "business development", "content", "hr", 
    "accounting", "finance", "customer service", "design", "logistics",
    "xây dựng", "cơ khí", "sản xuất", "may mặc", "môi trường", "thực phẩm",
    "y học", "y tế", "điều dưỡng", "thời trang", "biện pháp thi công",
    "giám sát hiện trường", "xưởng sơn", "trắc đạc", "kiến trúc sư thiết kế", "nội thất"
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(DATA_DIR / "vietnamworks_crawler.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("vnworks")

def safe_log(msg: str, level: str = "info"):
    """Log safely, stripping non-ASCII chars for Windows compatibility."""
    msg = (msg
        .replace("[OK]", "[OK]")
        .replace("[FAIL]", "[FAIL]")
        .replace(">>", ">>")
        .replace("[SAVE]", "[SAVE]")
        .replace("[START]", "[START]")
    )
    getattr(log, level)(msg)

# ──────────────────────────────────────────────────────────────────────────────
# DRIVER & HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def create_driver(headless: bool = True, fast_mode: bool = True) -> webdriver.Chrome:
    opts = Options()
    if headless: 
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--window-size=1440,900")
    opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    
    if fast_mode:
        opts.page_load_strategy = "eager"
        prefs = {"profile.managed_default_content_settings.images": 2}
        opts.add_experimental_option("prefs", prefs)
    
    # 1. Try standard selenium first
    try:
        driver = webdriver.Chrome(options=opts)
        return driver
    except Exception:
        pass

    # 2. Try WDM as fallback
    if _USE_WDM:
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=opts)
            return driver
        except Exception:
            pass
            
    # 3. Last resort
    service = Service()
    return webdriver.Chrome(service=service, options=opts)

def _clean(text: str | None) -> str:
    if not text: return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r"[\r\n\t]+", "\n", text)
    text = re.sub(r" +", " ", text)
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    return "\n".join(lines).strip()

def _text(soup: BeautifulSoup, selectors: str | list[str], default: str = "N/A") -> str:
    if isinstance(selectors, str):
        selectors = [selectors]
    for selector in selectors:
        try:
            el = soup.select_one(selector)
            if el: return _clean(el.get_text(" ", strip=True))
        except Exception: pass
    return default

def _is_it_job(job_data: dict | str) -> bool:
    """Heuristic check to ignore obvious non-IT jobs that search might return."""
    if isinstance(job_data, str):
        title = job_data
        description = ""
    else:
        title = job_data.get("title") or job_data.get("job_title") or ""
        description = job_data.get("description", "")
    
    non_it_keywords = [
        "sales", "logistics", "trắc đạc", "kế toán", "phiên dịch", 
        "marketing", "nhân sự", "hr", "tư vấn", "bảo hiểm", "giáo viên",
        "xây dựng", "cơ khí", "cơ điện", "điện lạnh", "sản xuất", "may mặc", 
        "môi trường", "thực phẩm", "y học", "y tế", "điều dưỡng", "thời trang",
        "thi công", "giám sát hiện trường", "xưởng sơn", "biện pháp thi công",
        "kiến trúc sư thiết kế", "nội thất", "kinh doanh", "accountant",
        "banker", "receptionist", "lễ tân", "tạp vụ"
    ]
    title_lower = title.lower()
    desc_lower = description.lower()
    
    # Check for obvious non-IT keywords in title
    if any(k in title_lower for k in non_it_keywords):
        # Safeguards: if it also contains very specific IT keywords in TITLE, keep it
        it_safeguards = [
            "it", "developer", "software", "tech", "lập trình", 
            "hệ thống", "dữ liệu", "mạng", "security", "bảo mật",
            "db", "cloud", "devops", "frontend", "backend", "fullstack", 
            "coder", "web", "mobile", "qa", "qc", "tester"
        ]
        if not any(k in title_lower for k in it_safeguards):
            # One more chance: if description has VERY specific tech stack keywords
            strong_tech = ["react", "nodejs", "python", "java", "golang", "c#", "asp.net", "php", "aws", "docker", "kubernetes", "sql", "javascript", "typescript"]
            if not any(k in desc_lower for k in strong_tech):
                return False
            
    return True

def _map_to_it_category(title: str, description: str) -> str:
    """Map a job to one of the 10 standardized IT categories."""
    title_lower = title.lower()
    desc_lower = description.lower()
    
    for main_cat, keywords in IT_CATEGORIES.items():
        if any(k.lower() in title_lower or k.lower() in desc_lower for k in keywords):
            return main_cat
    return "OTHER_IT" # Should not reach here due to _is_it_job filter

# ──────────────────────────────────────────────────────────────────────────────
# PHASE 1: LISTING
# ──────────────────────────────────────────────────────────────────────────────

def parse_listing_page(driver: webdriver.Chrome, url: str) -> list[dict]:
    """Collect unique job URLs from the listing page."""
    try:
        driver.get(url)
        WebDriverWait(driver, 30).until(
            EC.any_of(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a.img_job_card")),
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='-jv']"))
            )
        )
        driver.execute_script("window.scrollTo(0, 1000);")
        time.sleep(3) 
        
        soup = BeautifulSoup(driver.page_source, "lxml")
        jobs = []

        all_links = soup.select('a[href*="-jv"]')
        seen_urls = set()
        for link in all_links:
            href = link["href"].split("?")[0]
            if not href.startswith("http"): href = BASE_URL + href
            if href in seen_urls: continue
            seen_urls.add(href)
            
            # Simple metadata extraction if available on card
            title = _clean(link.get_text())
            if not title or len(title) < 5:
                card = link.find_parent("div", class_=lambda x: x and ("sc-" in x or "Job" in x))
                if card:
                    title_el = card.select_one('a[href*="-jv"]:not(.img_job_card)')
                    if title_el: title = _clean(title_el.get_text())

            jobs.append({
                "job_url": href,
                "job_title": title or "N/A",
                "company_name": "N/A",
                "location": "N/A",
                "salary": "N/A"
            })
            
        # Filter out obvious non-IT jobs before detail fetching
        filtered_jobs = [j for j in jobs if _is_it_job({"title": j["job_title"], "description": "", "category": ""})]
            
        return filtered_jobs
    except Exception as e:
        log.warning(f"Listing error {url}: {e}")
        return []

# ──────────────────────────────────────────────────────────────────────────────
# PHASE 2: DETAIL
# ──────────────────────────────────────────────────────────────────────────────

def parse_job_detail_full(driver: webdriver.Chrome, job: dict) -> dict:
    """Extract all necessary fields from the job detail page."""
    url = job["job_url"]
    try:
        driver.get(url)
        WebDriverWait(driver, 30).until(
            EC.any_of(
                EC.presence_of_element_located((By.CSS_SELECTOR, "h1")),
                EC.presence_of_element_located((By.CSS_SELECTOR, ".company-name")),
                EC.presence_of_element_located((By.CSS_SELECTOR, ".description"))
            )
        )
        
        # Ensure dynamic summary/location box is rendered
        driver.execute_script("window.scrollTo(0, 300);")
        time.sleep(5)
            
        soup = BeautifulSoup(driver.page_source, "lxml")
        
        # Click "Xem đầy đủ mô tả công việc" if it exists
        try:
            expand_btn = driver.find_elements(By.CSS_SELECTOR, 'button[aria-label="Xem đầy đủ mô tả công việc"]')
            if expand_btn:
                driver.execute_script("arguments[0].click();", expand_btn[0])
                time.sleep(1)
        except: pass
            
        soup = BeautifulSoup(driver.page_source, "lxml")
        
        # 1. Title
        job["job_title"] = _text(soup, "h1", default=job.get("job_title", "N/A"))
        
        # 2. Company Name
        company = "N/A"
        comp_el = (soup.select_one('.company-name a') or 
                   soup.select_one('h3.company-name a') or 
                   soup.select_one('.company-info h2 a') or
                   soup.select_one('a[name="label"][href*="/nha-tuyen-dung/"]'))
        if comp_el:
            txt = _clean(comp_el.get_text())
            if txt and txt.lower() not in ["trang chủ", "việc làm"]:
                company = txt
        job["company_name"] = company
            
        # 3. Location, Salary, Deadline
        # The header sticky bar on VNW has structure: [Salary | Deadline | Location]  
        # Location is in a short <span> or <div> containing ONLY the city name
        CITY_NAMES = [
            "Hà Nội", "Hồ Chí Minh", "Đà Nẵng", "Cần Thơ", "Bắc Ninh",
            "Bình Dương", "Hải Phòng", "Đồng Nai", "Long An", "Vũng Tàu",
            "Quảng Nam", "Khánh Hòa", "Thừa Thiên Huế", "An Giang", "Cà Mau"
        ]
        location = "N/A"
        salary = "Thỏa thuận"
        deadline = "N/A"
        
        # Strategy 1: Find <span> or <div> where the ENTIRE text is a city name (most reliable)
        for tag in soup.find_all(["span", "div"]):
            txt = tag.get_text(" ", strip=True)
            if txt in CITY_NAMES:
                # Prefer elements that are NOT inside footer/nav/recommendation sections
                parents_classes = " ".join(c for p in tag.parents for c in (p.get("class") or []))
                if not any(bad in parents_classes for bad in ["footer", "recommend", "sc-23c7111f"]):
                    location = txt
                    break
        
        # Strategy 2: If not found, look for the company address (more detailed but messier)
        if location == "N/A":
            for tag in soup.find_all(["p", "div"]):
                txt = tag.get_text(" ", strip=True)
                if any(city in txt for city in CITY_NAMES) and 5 < len(txt) < 100:
                    # Skip elements with too much noise
                    if not any(bad in txt for bad in ["Trang chủ", "Việc làm theo", "top_recommend"]):
                        location = re.sub(r"\(Xem bản đồ\)", "", txt, flags=re.IGNORECASE).strip()
                        location = re.sub(r"(Lượt xem|Hạn nộp|Nộp đơn).*$", "", location, flags=re.IGNORECASE).strip()
                        if location: break
        
        # Salary & Deadline: scan the header info block (short elements)
        # The structure is: [salary_div | deadline_div | city_div], all siblings
        header_items = soup.select("[class*='sc-335c0d9a'] span, [class*='sc-335c0d9a'] div")
        for el in header_items:
            txt = el.get_text(" ", strip=True)
            if not txt or len(txt) > 200: continue
            t_lower = txt.lower()
            if any(k in t_lower for k in ["hết hạn", "ngày"]) and deadline == "N/A":
                deadline = txt
            if any(k in t_lower for k in ["lương", "thỏa thuận", "thương lượng", "$", "vnđ", "triệu"]):
                if len(txt) < 50:  # Avoid picking up large description blocks
                    salary = txt
        
        job["location"] = location
        job["deadline"] = deadline
        job["salary"] = salary if salary != "Thỏa thuận" else job.get("salary", "Thỏa thuận")
        
        # DEBUG (remove after validation)
        print(f"\n[DEBUG] URL: {url}")
        print(f"[DEBUG] Location: {location}")
        print(f"[DEBUG] Salary: {salary}")
        print(f"[DEBUG] Deadline: {deadline}")
        
        # 4. Description & Requirements (Merged)
        description_text = "N/A"
        requirements_text = "N/A"
        
        # Strategy: Find sections by H2/H3 headers
        headers = soup.find_all(['h2', 'h3'])
        for h in headers:
            txt = h.get_text().lower().strip()
            content = ""
            parent_box = h.find_parent('div', class_=re.compile(r'gDSEwb|sc-1671001a-4'))
            if parent_box:
                content_el = parent_box.find('div', class_=re.compile(r'dVvinc|sc-1671001a-6'))
                if content_el:
                    content = content_el.get_text("\n", strip=True)
            
            if not content:
                nxt = h.find_next_sibling()
                if nxt:
                    content = nxt.get_text("\n", strip=True)

            if "mô tả công việc" in txt or "job description" in txt:
                description_text = _clean(content) if content else description_text
            elif any(k in txt for k in ["yêu cầu công việc", "requirements", "yêu cầu ứng viên"]):
                requirements_text = _clean(content) if content else requirements_text

        # Global Fallback
        if description_text == "N/A":
            content_el = (soup.select_one(".description") or 
                          soup.select_one("[class*='JobDescription']") or 
                          soup.select_one(".job-detail-content"))
            if content_el:
                description_text = _clean(content_el.get_text("\n", strip=True))
        
        # Merge fields as requested (Kept separate as per user feedback)
        job["description"] = description_text if description_text != "N/A" else "N/A"
        job["requirements"] = requirements_text if requirements_text != "N/A" else "N/A"
        job["deadline"] = deadline
        return job
    except Exception as e:
        log.error(f"Detail error {url}: {e}")
        return job

# ──────────────────────────────────────────────────────────────────────────────
# CORE
# ──────────────────────────────────────────────────────────────────────────────

def _detail_worker(job: dict) -> dict:
    driver = create_driver(headless=True, fast_mode=True)
    try:
        return parse_job_detail_full(driver, job)
    finally:
        driver.quit()

def crawl_vietnamworks(keyword: str, max_jobs: int = 10, workers: int = 3, category_name: str = "IT"):
    safe_log(f">> Phase 1: Collecting jobs for '{keyword}' ({category_name})")
    
    out_path = DATA_DIR / "vnworks_it_full.csv"
    existing_urls = set()
    if out_path.exists():
        try:
            old_df = pd.read_csv(out_path)
            existing_urls = set(old_df["job_url"].tolist())
        except Exception: pass

    listing_driver = create_driver(headless=True, fast_mode=False)
    collected_jobs = []
    page = 1
    
    try:
        while len(collected_jobs) < max_jobs and page <= 10:
            url = SEARCH_URL.format(keyword=keyword, page=page)
            jobs_on_page = parse_listing_page(listing_driver, url)
            if not jobs_on_page: break
            
            new_found = 0
            for j in jobs_on_page:
                if j["job_url"] not in existing_urls and not any(x["job_url"] == j["job_url"] for x in collected_jobs):
                    collected_jobs.append(j)
                    new_found += 1
            
            log.info(f"  Page {page}: found {len(jobs_on_page)} jobs. New items: {new_found}")
            if len(collected_jobs) >= max_jobs: break
            page += 1
    finally:
        listing_driver.quit()
        
    target_jobs = collected_jobs[:max_jobs]
    if not target_jobs:
        return pd.DataFrame()

    # Phase 2: Detail Extraction (Parallel)
    final_jobs = []
    processed_count = 0
    
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_detail_worker, j): j for j in target_jobs}
        for future in as_completed(futures):
            processed_count += 1
            try:
                job_full = future.result()
                
                # RE-VERIFY IT relevance with full description
                if not _is_it_job({
                    "title": job_full["job_title"], 
                    "description": job_full["description"], 
                    "category": ""
                }):
                    log.info(f"    [SKIP] Final Filter (Non-IT): {job_full['job_title']}")
                    continue
                
                # Standardize category
                final_cat = _map_to_it_category(job_full["job_title"], job_full["description"])
                
                # Build final object as per user request
                # Build final standardized object as per user request (10 columns)
                final_job = {
                    "job_url":      job_full["job_url"],
                    "job_title":    job_full["job_title"],
                    "company_name": job_full["company_name"],
                    "location":     job_full["location"],
                    "salary":       job_full["salary"],
                    "deadline":     job_full.get("deadline", "N/A"),
                    "description":  job_full["description"],
                    "requirements": job_full.get("requirements", "N/A"),
                    "category":     final_cat,
                    "keyword":      keyword
                }
                final_jobs.append(final_job)
                safe_log(f"  [{processed_count}/{len(target_jobs)}] [OK] {final_job['job_title']}")
            except Exception as e:
                log.error(f"Worker failed: {e}")

    if not final_jobs:
        return pd.DataFrame()

    new_df = pd.DataFrame(final_jobs)
    # Ensure columns match CSV_COLUMNS exactly
    new_df = new_df[CSV_COLUMNS]
    
    # Append to CSV; only write header if file is new or empty
    write_header = not out_path.exists() or out_path.stat().st_size == 0
    new_df.to_csv(
        out_path, 
        mode='a', 
        index=False, 
        header=write_header, 
        encoding="utf-8-sig",
        quoting=csv.QUOTE_ALL
    )
    
    safe_log(f"[SAVE] Added {len(final_jobs)} new IT jobs to {out_path}")
    return new_df

def crawl_all_categories(max_jobs_per_cat: int = 50, workers: int = 3):
    """Iterate through all IT categories and crawl jobs."""
    total_new = 0
    # Use the standardized categories for searching
    for cat_name, keywords in IT_CATEGORIES.items():
        # Search for the main category name first
        safe_log(f"\n[START] Category: {cat_name} (Searching for keywords)")
        
        # To avoid being too slow or repetitive, we'll search the first 3 major keywords if available
        search_keywords = keywords[:3] if len(keywords) >= 3 else keywords
        
        # If the category name itself is not in the keywords, add it
        if cat_name.lower() not in [k.lower() for k in search_keywords]:
             search_keywords = [cat_name] + search_keywords

        cat_new_count = 0
        for kw in search_keywords:
            log.info(f"--- Searching for keyword: {kw} ---")
            df = crawl_vietnamworks(kw, max_jobs=max_jobs_per_cat // len(search_keywords), workers=workers, category_name=cat_name)
            cat_new_count += len(df)
            total_new += len(df)
            
        safe_log(f"[CAT DONE] {cat_name}: total {cat_new_count} new jobs added.")
        
    safe_log(f"\n[DONE] Finished crawling all categories. Total new jobs added this session: {total_new}")


def crawl_general_it(max_jobs_per_kw: int = 100, workers: int = 3):
    """Crawl IT jobs from g=5 with each IT keyword, but WITHOUT the j= sub-category filter.
    This casts a wider net than crawl_all_categories / SEARCH_URL.
    The 'keyword' column in the CSV will reflect the actual keyword used.
    """
    safe_log(f"[START] General g=5 + keyword crawl (target ~{max_jobs_per_kw} jobs/keyword)")

    total_new = 0
    for cat_name, keywords in IT_CATEGORIES.items():
        # Search with first 3 keywords of each category
        search_keywords = keywords[:3] if len(keywords) >= 3 else keywords

        safe_log(f"\n[CAT] {cat_name}: searching {search_keywords}")
        for kw in search_keywords:
            out_path = DATA_DIR / "vnworks_it_full.csv"
            existing_urls: set[str] = set()
            if out_path.exists():
                try:
                    old_df = pd.read_csv(out_path)
                    existing_urls = set(old_df["job_url"].tolist())
                except Exception:
                    pass

            listing_driver = create_driver(headless=True, fast_mode=False)
            collected_jobs: list[dict] = []
            page = 1

            try:
                while len(collected_jobs) < max_jobs_per_kw and page <= 10:
                    url = GENERAL_IT_URL.format(keyword=kw, page=page)
                    log.info(f"  [{cat_name}][{kw}] Page {page}: {url}")
                    jobs_on_page = parse_listing_page(listing_driver, url)
                    if not jobs_on_page:
                        break

                    new_found = 0
                    for j in jobs_on_page:
                        if j["job_url"] not in existing_urls and not any(
                            x["job_url"] == j["job_url"] for x in collected_jobs
                        ):
                            collected_jobs.append(j)
                            new_found += 1

                    log.info(f"    {len(jobs_on_page)} scraped, {new_found} new (total collected: {len(collected_jobs)})")
                    if len(collected_jobs) >= max_jobs_per_kw:
                        break
                    page += 1
            finally:
                listing_driver.quit()

            target_jobs = collected_jobs[:max_jobs_per_kw]
            if not target_jobs:
                log.info(f"  No new jobs for keyword '{kw}'.")
                continue

            log.info(f"  Collected {len(target_jobs)} URLs for '{kw}'. Starting detail extraction...")

            final_jobs: list[dict] = []
            processed_count = 0
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {executor.submit(_detail_worker, j): j for j in target_jobs}
                for future in as_completed(futures):
                    processed_count += 1
                    try:
                        job_full = future.result()
                        if not _is_it_job({"title": job_full["job_title"], "description": job_full["description"], "category": ""}):
                            log.info(f"    [SKIP] Non-IT: {job_full['job_title']}")
                            continue

                        final_cat = _map_to_it_category(job_full["job_title"], job_full["description"])
                        final_job = {
                            "job_url":      job_full["job_url"],
                            "job_title":    job_full["job_title"],
                            "company_name": job_full["company_name"],
                            "location":     job_full["location"],
                            "salary":       job_full["salary"],
                            "deadline":     job_full.get("deadline", "N/A"),
                            "description":  job_full["description"],
                            "requirements": job_full.get("requirements", "N/A"),
                            "category":     final_cat,
                            "keyword":      kw,   # ← actual keyword used
                        }
                        final_jobs.append(final_job)
                        safe_log(f"  [{processed_count}/{len(target_jobs)}] [OK] {final_job['job_title']} | {final_cat}")
                    except Exception as e:
                        log.error(f"Worker failed: {e}")

            if final_jobs:
                new_df = pd.DataFrame(final_jobs)[CSV_COLUMNS]
                write_header = not out_path.exists() or out_path.stat().st_size == 0
                new_df.to_csv(out_path, mode="a", index=False, header=write_header,
                              encoding="utf-8-sig", quoting=csv.QUOTE_ALL)
                safe_log(f"[SAVE] +{len(final_jobs)} jobs for keyword '{kw}' → {out_path}")
                total_new += len(final_jobs)

    safe_log(f"\n[DONE] General crawl finished. Total new jobs added: {total_new}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VietnamWorks IT Crawler")
    parser.add_argument("--mode", choices=["all", "single", "general"], default="all")
    parser.add_argument("--keyword", type=str, default="Python")
    parser.add_argument("--max-jobs", type=int, default=10)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--start-page", type=int, default=1,
                        help="Starting page for general mode (default: 1)")

    args = parser.parse_args()

    if args.mode == "all":
        crawl_all_categories(max_jobs_per_cat=args.max_jobs, workers=args.workers)
    elif args.mode == "general":
        crawl_general_it(max_jobs_per_kw=args.max_jobs, workers=args.workers)
    else:
        crawl_vietnamworks(args.keyword, max_jobs=args.max_jobs, workers=args.workers)
