"""
topcv_vnw_style_crawler.py – VNW-Architected TopCV Job Crawler
==============================================================
STRATEGY: Hybrid Extraction (Phased)
  Phase 1: Listing Page – Collect unique Job URLs based on IT keywords.
  Phase 2: Detail Page  – Extract all fields with layout-aware selectors.

FEATURES:
  ✅ Precise selectors for Standard and Diamond/Brand layouts.
  ✅ IT-specific heuristics and categorization (Backend, Frontend, etc.).
  ✅ High-resiliency against Cloudflare using undetected-chromedriver.
  ✅ Parallel workers for detail pages (optimized for stealth).
"""

import argparse
import csv
import logging
import os
import re
import sys
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Dict, Set, Optional

import pandas as pd
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# Attempt to import undetected-chromedriver
try:
    import undetected_chromedriver as uc
except ImportError:
    uc = None

# ──────────────────────────────────────────────────────────────────────────────
# CONFIG & CATEGORIES
# ──────────────────────────────────────────────────────────────────────────────
BASE_URL = "https://www.topcv.vn"

CATEGORY_SEEDS = [
    {
        "name": "Software Engineering",
        "url": "https://www.topcv.vn/tim-viec-lam-software-engineering-cr257cb258?type_keyword=1&sba=1&category_family=r257~b258"
    },
    {
        "name": "IT Generic",
        "url": "https://www.topcv.vn/tim-viec-lam-cong-nghe-thong-tin-cr257?category_family=r257"
    },
    {
        "name": "Backend Developer",
        "url": "https://www.topcv.vn/tim-viec-lam-backend-developer"
    },
    {
        "name": "Java Developer",
        "url": "https://www.topcv.vn/tim-viec-lam-java-developer"
    },
    {
        "name": ".NET Developer",
        "url": "https://www.topcv.vn/tim-viec-lam-net-developer"
    },
    {
        "name": "PHP Developer",
        "url": "https://www.topcv.vn/tim-viec-lam-php-developer"
    },
    {
        "name": "Python Developer",
        "url": "https://www.topcv.vn/tim-viec-lam-python-developer"
    },
    {
        "name": "Frontend Developer",
        "url": "https://www.topcv.vn/tim-viec-lam-frontend-developer"
    },
    {
        "name": "React Developer",
        "url": "https://www.topcv.vn/tim-viec-lam-reactjs"
    },
    {
        "name": "VueJS Developer",
        "url": "https://www.topcv.vn/tim-viec-lam-vuejs"
    },
    {
        "name": "Fullstack Developer",
        "url": "https://www.topcv.vn/tim-viec-lam-fullstack-developer"
    },
    {
        "name": "Mobile Developer",
        "url": "https://www.topcv.vn/tim-viec-lam-mobile-developer"
    },
    {
        "name": "Android Developer",
        "url": "https://www.topcv.vn/tim-viec-lam-android"
    },
    {
        "name": "iOS Developer",
        "url": "https://www.topcv.vn/tim-viec-lam-ios"
    },
    {
        "name": "Flutter Developer",
        "url": "https://www.topcv.vn/tim-viec-lam-flutter"
    },
    {
        "name": "Data Scientist",
        "url": "https://www.topcv.vn/tim-viec-lam-data-scientist"
    },
    {
        "name": "Data Analyst",
        "url": "https://www.topcv.vn/tim-viec-lam-data-analyst"
    },
    {
        "name": "Machine Learning",
        "url": "https://www.topcv.vn/tim-viec-lam-machine-learning"
    },
    {
        "name": "AI Engineer",
        "url": "https://www.topcv.vn/tim-viec-lam-ai-engineer"
    },
    {
        "name": "DevOps Engineer",
        "url": "https://www.topcv.vn/tim-viec-lam-devops"
    },
    {
        "name": "Cloud Engineer",
        "url": "https://www.topcv.vn/tim-viec-lam-cloud-engineer"
    },
    {
        "name": "AWS Engineer",
        "url": "https://www.topcv.vn/tim-viec-lam-aws"
    },
    {
        "name": "QA Tester",
        "url": "https://www.topcv.vn/tim-viec-lam-tester"
    },
    {
        "name": "Automation Test",
        "url": "https://www.topcv.vn/tim-viec-lam-automation-test"
    },
    {
        "name": "Cyber Security",
        "url": "https://www.topcv.vn/tim-viec-lam-an-ninh-mang"
    },
    {
        "name": "System Engineer",
        "url": "https://www.topcv.vn/tim-viec-lam-system-engineer"
    },
    {
        "name": "Network Engineer",
        "url": "https://www.topcv.vn/tim-viec-lam-network"
    },
    {
        "name": "Game Developer",
        "url": "https://www.topcv.vn/tim-viec-lam-game-developer"
    },
    {
        "name": "Blockchain Developer",
        "url": "https://www.topcv.vn/tim-viec-lam-blockchain"
    }
]

SEARCH_URL_TEMPLATE = "https://www.topcv.vn/tim-viec-lam-{keyword}?page={page}"
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

CSV_COLUMNS = [
    "job_url", "job_title", "company_name", "location", "salary", 
    "deadline", "description", "requirements", "category", "keyword"
]

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

CHROME_BINARY_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CHROMEDRIVER_PATH = r"C:\Users\admin\.wdm\drivers\chromedriver\win64\146.0.7680.165\chromedriver-win32/chromedriver.exe"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(DATA_DIR / "topcv_vnw_style.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("topcv_vnw")

# ──────────────────────────────────────────────────────────────────────────────
# DRIVER & HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def create_stealth_driver(headless: bool = False):
    if not uc:
        log.error("undetected-chromedriver not installed.")
        return None
        
    def get_options():
        options = uc.ChromeOptions()
        if headless:
            options.add_argument("--headless")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        return options

    # 1. Try pinned version 146 (known correct for this env)
    try:
        driver = uc.Chrome(
            options=get_options(),
            browser_executable_path=CHROME_BINARY_PATH,
            driver_executable_path=CHROMEDRIVER_PATH,
            version_main=146
        )
        return driver
    except Exception as e:
        log.debug(f"Pinned version 146 failed: {e}. Trying auto-detect...")
    
    # 2. Fallback to default (auto-detect)
    try:
        driver = uc.Chrome(
            options=get_options(),
            browser_executable_path=CHROME_BINARY_PATH
        )
        return driver
    except Exception as e:
        log.error(f"Failed to create UC driver: {e}")
        return None

def _clean(text: str | None) -> str:
    if not text: return ""
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
            if el:
                val = _clean(el.get_text(" ", strip=True))
                if val: return val
        except Exception: pass
    return default

def _is_it_job(title: str, description: str = "") -> bool:
    title_lower = title.lower()
    non_it = ["sales", "kế toán", "marketing", "logistics", "may mặc", "xây dựng", "nhân sự"]
    if any(k in title_lower for k in non_it):
        it_guards = ["it", "developer", "software", "lập trình", "web", "data", "devops"]
        if not any(k in title_lower for k in it_guards): return False
    return True

def _map_to_it_category(title: str, description: str) -> str:
    title_lower = title.lower()
    desc_lower = description.lower()
    for main_cat, keywords in IT_CATEGORIES.items():
        if any(k.lower() in title_lower or k.lower() in desc_lower for k in keywords):
            return main_cat
    return "OTHER_IT"

# ──────────────────────────────────────────────────────────────────────────────
# PHASE 1: LISTING
# ──────────────────────────────────────────────────────────────────────────────

def parse_listing_page(driver, url: str) -> List[dict]:
    if not driver:
        log.error(f"No driver provided for {url}")
        return []
        
    try:
        driver.get(url)
        time.sleep(random.uniform(5, 8))
        if "Cloudflare" in driver.title or "Just a moment" in driver.page_source:
            log.warning("Cloudflare detected! Waiting 30s...")
            time.sleep(30)
            driver.refresh()
            time.sleep(10)
            
        # Help trigger lazy loading/rendering
        driver.execute_script("window.scrollTo(0, 500);")
        time.sleep(2)
        driver.execute_script("window.scrollTo(0, 1000);")
        time.sleep(2)
        
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".job-item-search-result, [class*='job-item'], h3.title"))
            )
        except:
            log.warning(f"Timeout waiting for jobs on {url}")
            # Log a small snippet of page source for debugging
            log.info(f"Page Title: {driver.title}")
            return []
        
        soup = BeautifulSoup(driver.page_source, "lxml")
        jobs = []
        cards = soup.select(".job-item-search-result, .job-item-2114663, [class*='job-item']")
        
        if not cards:
            log.warning(f"No jobs found matching selectors on {url}. Page Title: {driver.title}")
            driver.save_screenshot(str(DATA_DIR / "topcv_listing_debug.png"))
            # Check for empty state
            if "không tìm thấy" in soup.get_text().lower():
                log.info("Page explicitly says 'No results found'.")
            else:
                log.info(f"Page content length: {len(driver.page_source)}")

        for card in cards:
            title_el = card.select_one(".title a, .job-title a, a[class*='title']")
            if not title_el: continue
            
            href = title_el["href"].split("?")[0]
            if not href.startswith("http"): href = BASE_URL + href
            
            title = _clean(title_el.get_text())
            company = _text(card, [".company a", ".company-name a", ".company-name", ".company"])
            location = _text(card, ".address, .location")
            salary = _text(card, ".salary")
            
            is_it = _is_it_job(title)
            print(f"[DEBUG] Title: {title} | Company: {company} | Is IT: {is_it}")
            
            if is_it:
                jobs.append({
                    "job_url": href,
                    "job_title": title,
                    "company_name": company,
                    "location": location,
                    "salary": salary
                })
        return jobs
    except Exception as e:
        log.error(f"Listing error at {url}: {e}")
        return []

# ──────────────────────────────────────────────────────────────────────────────
# PHASE 2: DETAIL
# ──────────────────────────────────────────────────────────────────────────────

def parse_job_detail(driver, job: dict) -> dict:
    url = job["job_url"]
    phase1_title = job.get("job_title", "N/A")
    phase1_company = job.get("company_name", "N/A")
    phase1_location = job.get("location", "N/A")
    phase1_salary = job.get("salary", "N/A")
    
    try:
        driver.get(url)
        time.sleep(random.uniform(8, 12))
        
        if "Just a moment" in driver.title or "Cloudflare" in driver.title:
            log.warning(f"Blocked by Cloudflare at {url}. Waiting 30s...")
            time.sleep(30)
            driver.refresh()
            time.sleep(10)

        # Expand "Xem thêm"
        expand_selectors = [".btn-show-more", "#btn-show-more", ".see-more", "#btn-show-more-jd"]
        for selector in expand_selectors:
            try:
                for btn in driver.find_elements(By.CSS_SELECTOR, selector):
                    if btn.is_displayed():
                        driver.execute_script("arguments[0].click();", btn)
                        time.sleep(1)
            except: pass

        soup = BeautifulSoup(driver.page_source, "lxml")
        is_brand = "/brand/" in url
        is_diamond = bool(soup.select_one(".job-description__header") or soup.select_one(".btn-diamond"))
        
        # 1. Title
        title_sel = [".job-detail__info--title", "h1.job-title", "h1", "h2.premium-job-basic-information__content--title", ".job-description__header-title"]
        job["job_title"] = _text(soup, title_sel, default=phase1_title)
        if "topcv" in job["job_title"].lower(): job["job_title"] = phase1_title
        
        # 2. Company Name
        company_sel = [
            "div.job-detail__company--name a", 
            ".company-name a", 
            ".job-header-info__company-name", 
            ".box-info-company .company-name",
            ".company-name",
            "h2",
            "h1.company-content__title--name",
            ".brand-name",
            "a[data-original-title]",
            ".name"
        ]
        company_text = _text(soup, company_sel, default="N/A")
        
        if company_text == "N/A":
            logo = soup.select_one(".brand-logo img, .company-logo img, .navbar-diamond-company-brand img")
            if logo and logo.get("alt"): company_text = _clean(logo["alt"])
            
        job["company_name"] = company_text if company_text != "N/A" else phase1_company

        # 3. Location, Salary
        location = "N/A"
        salary = "Thoả thuận"
        new_layout_found = False
        
        if is_brand:
            # Info items in Brand layout: [Salary, Location, Exp]
            # Pattern: .basic-information-item__data--value
            basic_info = soup.select(".basic-information-item__data--value")
            if len(basic_info) >= 2:
                salary = _clean(basic_info[0].get_text())
                location = _clean(basic_info[1].get_text())
                new_layout_found = True
        elif is_diamond:
            for item in soup.find_all(class_='job-detail-v2__info-item'):
                lbl = item.find(class_='job-detail-v2__info-item-label')
                val = item.find(class_='job-detail-v2__info-item-value')
                if lbl and val:
                    ltext = lbl.text.strip().lower()
                    if "mức lương" in ltext: salary = val.text.strip()
                    elif "địa điểm" in ltext:
                        loc_link = val.find('a', href=re.compile(r'/tim-viec-lam-.*-tai-.*-kl'))
                        location = loc_link.text.strip() if loc_link else val.text.strip()
        else:
            # ── LAYOUT 1: div.info > div.label-content > label.address (current TopCV 2025) ──
            if not new_layout_found:
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
                    city_spans = [s.text.strip() for s in label_content.find_all('span')
                                  if any(c in s.text for c in ["Hà Nội", "Hồ Chí Minh", "Đà Nẵng", "Hải Phòng", "Cần Thơ", "Bình Dương", "Đồng Nai"])]
                    if city_spans:
                        location = ", ".join(city_spans)
                        new_layout_found = True
                        break
            
            # ── LAYOUT 2: .job-info_content / .col-job-info (interim) ──
            if not new_layout_found:
                for el in soup.select(".job-info_content, .col-job-info")[:10]:
                    loc_links = el.find_all('a', href=re.compile(r'/tim-viec-lam-.*-kl\d'))
                    if loc_links:
                        location = ", ".join([a.text.strip() for a in loc_links if a.text.strip()])
                        new_layout_found = True
                        break
            
            # ── LAYOUT 3: Index-based (2nd content-value = location, per reference code) ──
            if not new_layout_found:
                all_vals = soup.select("div.job-detail__info--section div.job-detail__info--section-content-value")
                if len(all_vals) >= 2:
                    loc_text = all_vals[1].get_text(separator=", ").strip()
                    if loc_text and loc_text.lower() not in ["n/a", "địa điểm"]:
                        location = loc_text
                        new_layout_found = True
                if salary == "Thoả thuận" and all_vals:
                    sal_text = all_vals[0].get_text(separator=", ").strip()
                    if sal_text and sal_text.lower() not in ["n/a"]:
                        salary = sal_text
            
            # ── LAYOUT 4: .job-detail__info--section with label matching (old) ──
            info_sections = soup.find_all('div', class_='job-detail__info--section')
            for sec in info_sections:
                label_el = sec.find('div', class_='job-detail__info--section-label')
                value_el = sec.find('div', class_='job-detail__info--section-content-value')
                if label_el and value_el:
                    lbl = label_el.text.strip().lower()
                    if "mức lương" in lbl: salary = value_el.text.strip()
                    elif "địa điểm" in lbl and not new_layout_found:
                        loc_link = value_el.find('a', href=re.compile(r'/tim-viec-lam-.*-tai-.*-kl'))
                        location = loc_link.text.strip() if loc_link else value_el.text.strip()


        job["location"] = location if location != "N/A" else phase1_location
        job["salary"] = salary if salary != "Thoả thuận" else phase1_salary
        
        # 4. Deadline
        deadline = "N/A"
        if is_brand:
            deadline_el = soup.select_one(".job-detail__information-detail--actions-label")
            if deadline_el:
                dt = deadline_el.get_text().strip()
                deadline = dt.split(":", 1)[1].strip() if ":" in dt else dt
        
        if deadline == "N/A":
            deadline_sel = [".job-detail__info--deadline-date", ".job-detail__info--section-content-value"]
            deadline = _text(soup, deadline_sel, "N/A")
            
        job["deadline"] = deadline

        description = ""
        requirements = ""
        content_sel = [".job-description__item", ".job-detail__section", ".job-detail-section", ".premium-job-description__box", ".job-description__left", "#job-detail", ".col-md-9", ".job-data", ".box-item"]
        full_text = ""
        for sel in content_sel:
            for el in soup.select(sel):
                full_text += el.get_text(separator="\n") + "\n"
        
        if full_text.strip():
            parts = re.split(r'(Mô tả công việc|Yêu cầu ứng viên|Quyền lợi|Cách thức ứng tuyển|Yêu cầu công việc|Yêu cầu|Kỹ năng|Yêu cầu kinh nghiệm)', full_text, flags=re.IGNORECASE)
            for i in range(1, len(parts), 2):
                h, c = parts[i].lower(), parts[i+1].strip()
                if "mô tả" in h: description += c + " "
                elif "yêu cầu" in h or "kỹ năng" in h: requirements += c + " "
            
            if not description and not requirements:
                description, requirements = full_text[:1000], full_text[1000:2000]
        
        job["description"] = description.replace("\n", " ").strip() or "N/A"
        job["requirements"] = requirements.replace("\n", " ").strip() or "N/A"
        job["category"] = _map_to_it_category(job["job_title"], job["description"])
        
        return job
    except Exception as e:
        log.error(f"Detail error at {url}: {e}")
        return job

# ──────────────────────────────────────────────────────────────────────────────
# EXECUTION
# ──────────────────────────────────────────────────────────────────────────────

def _detail_worker(job: dict) -> dict:
    driver = create_stealth_driver(headless=True)
    try:
        if not driver: return job
        return parse_job_detail(driver, job)
    finally:
        if driver: driver.quit()

def crawl_topcv_vnw_style(keyword: Optional[str] = None, max_jobs: int = 20, workers: int = 1, pages_per_seed: int = 5):
    all_collected_jobs = []
    seen_urls = set()
    seeds = []
    if keyword:
        seeds.append({"name": f"Search: {keyword}", "url": SEARCH_URL_TEMPLATE.format(keyword=keyword, page="{page}")})
    else:
        for seed in CATEGORY_SEEDS:
            sep = "&" if "?" in seed["url"] else "?"
            seeds.append({"name": seed["name"], "url": seed["url"] + f"{sep}page={{page}}"})

    log.info(f">> Phase 1: Collecting jobs from {len(seeds)} sources (Headfull for stability)")
    listing_driver = create_stealth_driver(headless=False)
    
    try:
        for seed in seeds:
            log.info(f"  Source: {seed['name']}")
            for page in range(1, pages_per_seed + 1):
                if len(all_collected_jobs) >= max_jobs: break
                
                url = seed["url"].format(page=page)
                
                # RECOVERY: If driver died, recreate it
                try:
                    new_jobs = parse_listing_page(listing_driver, url)
                except Exception as e:
                    if "no such window" in str(e).lower() or "target window already closed" in str(e).lower():
                        log.warning("Listing driver crashed! Re-creating...")
                        if listing_driver:
                            try: listing_driver.quit()
                            except: pass
                        time.sleep(10)
                        listing_driver = create_stealth_driver(headless=False)
                        new_jobs = parse_listing_page(listing_driver, url)
                    else:
                        log.error(f"Unexpected listing error: {e}")
                        new_jobs = []
                
                print(f"[DEBUG] Phase 1 Success: Found {len(new_jobs)} jobs for {keyword or seed['name']}")
                
                for nj in new_jobs:
                    if nj["job_url"] not in seen_urls:
                        # Only collect if it looks like an IT job
                        if _is_it_job(nj["job_title"]):
                            nj["keyword"] = keyword or seed["name"]
                            all_collected_jobs.append(nj)
                            seen_urls.add(nj["job_url"])
                        else:
                            log.debug(f"Skipping non-IT job: {nj['job_title']}")
                
                log.info(f"    Page {page}: found {len(new_jobs)} jobs ({len(all_collected_jobs)} IT total)")
                if len(all_collected_jobs) >= max_jobs: break
                time.sleep(random.uniform(5, 10))
    finally:
        if listing_driver: listing_driver.quit()

    log.info(f">> Phase 2: Extracting details for {len(all_collected_jobs)} jobs using {workers} workers")
    final_jobs = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_detail_worker, job): job for job in all_collected_jobs}
        for future in as_completed(futures):
            res = future.result()
            final_jobs.append(res)
            log.info(f"  [{len(final_jobs)}/{len(all_collected_jobs)}] [OK] {res['job_title']} @ {res['company_name']}")

    if not final_jobs:
        log.warning(">> No jobs were successfully extracted.")
        return

    output_file = DATA_DIR / "topcv_it_full_1.csv.csv"
    df_new = pd.DataFrame(final_jobs)
    # Ensure all columns exist
    for col in CSV_COLUMNS:
        if col not in df_new.columns: df_new[col] = "N/A"
    
    df_new.to_csv(output_file, index=False, columns=CSV_COLUMNS, encoding="utf-8-sig", quoting=csv.QUOTE_ALL)
    log.info(f">> COMPLETED. Data saved to {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyword", type=str, help="Search keyword")
    parser.add_argument("--max-jobs", type=int, default=20)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--pages", type=int, default=5)
    args = parser.parse_args()
    
    crawl_topcv_vnw_style(keyword=args.keyword, max_jobs=args.max_jobs, workers=args.workers, pages_per_seed=args.pages)
