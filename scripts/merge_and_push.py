#!/usr/bin/env python3
import os
import re
import logging
import pandas as pd
import numpy as np
import sys
import unicodedata
import argparse
from datetime import datetime
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

# ─── Environment Setup ────────────────────────────────────────────────────────
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

# Import models from the main app
try:
    from backend.models import Job, Skill, JobSkill, Company, Category, Base
    from backend.config import settings
    DATABASE_URL = settings.DATABASE_URL_SYNC
except ImportError as e:
    print(f"Error importing backend modules: {e}")
    sys.exit(1)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("DataPipeline")

# ─── Configuration ────────────────────────────────────────────────────────────
TOPCV_CSV = os.path.join(project_root, 'data', 'topcv_it_full_1.csv')
VNW_CSV = os.path.join(project_root, 'data', 'vnworks_it_full.csv')
MERGED_CSV = os.path.join(project_root, 'data', 'merged_jobs.csv')

SKILL_LIST = [
    "python", "java", "c#", "c++", "golang", "ruby", "php", "scala",
    "nodejs", "node.js", "express", "fastapi", "django", "flask", "spring", "spring boot",
    "laravel", "asp.net", "html", "css", "javascript", "typescript", "react", "reactjs",
    "vue", "angular", "svelte", "nextjs", "mysql", "postgresql", "mongodb", "redis",
    "docker", "kubernetes", "aws", "azure", "gcp", "ci/cd", "jenkins", "linux",
    "machine learning", "deep learning", "tensorflow", "pytorch", "nlp", "phobert",
    "git", "github", "rest api", "graphql", "microservices", "agile", "scrum", "jira"
]

# ─── Helper Functions ──────────────────────────────────────────────────────────
def remove_html(text: str) -> str:
    if not text: return ""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', str(text))

def clean_standardize_text(text: str) -> str:
    if not text: return ""
    text = str(text)
    text = unicodedata.normalize('NFKC', text)
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def extract_skills(text: str) -> list:
    if not text: return []
    text_lower = text.lower()
    found = set()
    for skill in SKILL_LIST:
        pattern = r"(?<![a-z0-9])" + re.escape(skill) + r"(?![a-z0-9])"
        if re.search(pattern, text_lower):
            found.add(skill)
    return list(found)

# ─── Pipeline Class ───────────────────────────────────────────────────────────
class DataImportPipeline:
    def __init__(self, db_url: str, batch_size: int = 200):
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)
        self.batch_size = batch_size

    def setup_db(self):
        Base.metadata.create_all(self.engine)
        logger.info("Database schema verified.")

    def get_or_create_company(self, session, company_name: str):
        """Finds or creates a company by name (standardized)."""
        name_clean = company_name.strip()
        # Case-insensitive match
        company = session.query(Company).filter(func.lower(Company.name) == name_clean.lower()).first()
        if not company:
            company = Company(name=name_clean)
            session.add(company)
            session.flush()
        return company

    def get_or_create_skill(self, session, skill_name: str):
        skill = session.query(Skill).filter_by(name=skill_name).first()
        if not skill:
            skill = Skill(name=skill_name)
            session.add(skill)
            session.flush()
        return skill

    def get_or_create_category(self, session, cat_name: str):
        category = session.query(Category).filter_by(name=cat_name).first()
        if not category:
            category = Category(name=cat_name)
            session.add(category)
            session.flush()
        return category

    def run_import(self, csv_path: str, limit: int = None):
        logger.info(f"Starting import from {csv_path}...")
        try:
            df = pd.read_csv(csv_path, on_bad_lines='skip', nrows=limit)
        except Exception as e:
            logger.error(f"Failed to read CSV: {e}")
            return

        column_mapping = {
            'job_url': 'job_url', 'job_title': 'title', 'Tên công việc': 'title',
            'Tên công ty': 'company_name', 'Vị trí làm việc': 'location',
            'Lương': 'salary', 'Mô tả công việc': 'description',
            'Yêu cầu công việc': 'requirements', 'Năm kinh nghiệm': 'experience',
            'Hạn nộp hồ sơ': 'deadline', 'Category': 'category', 'Từ khóa': 'keyword'
        }
        for vi_col, en_col in column_mapping.items():
            if vi_col in df.columns:
                df = df.rename(columns={vi_col: en_col})

        df = df.dropna(subset=['title', 'company_name', 'job_url'])
        session = self.Session()
        processed_count = 0
        total_rows = len(df)

        for i in range(0, total_rows, self.batch_size):
            batch_df = df.iloc[i : i + self.batch_size]
            
            for _, row in batch_df.iterrows():
                try:
                    # Clean fields
                    title = str(row['title']).strip()
                    comp_name = str(row['company_name']).strip()
                    job_url = str(row['job_url']).strip()
                    location = str(row.get('location', 'N/A')).strip()
                    salary = str(row.get('salary', 'Thỏa thuận')).strip()
                    experience = str(row.get('experience', 'Không yêu cầu')).strip()
                    deadline = str(row.get('deadline', '—'))
                    
                    # Deduplicate Job in DB
                    job = session.query(Job).filter_by(job_url=job_url).first()
                    
                    clean_desc = remove_html(row.get('description', ''))
                    clean_req = remove_html(row.get('requirements', ''))
                    
                    # Skill extraction
                    combined_text = f"{title} {clean_desc} {clean_req}"
                    extracted_skills = extract_skills(combined_text)
                    
                    # Clean text bonus
                    standardized_title = clean_standardize_text(title)
                    bonus_clean_text = f"{standardized_title} {clean_standardize_text(clean_desc)} {clean_standardize_text(clean_req)}"

                    # Get Company (Normalized)
                    company = self.get_or_create_company(session, comp_name)

                    # Get Category
                    category_id = None
                    if 'category' in row and pd.notna(row['category']):
                        cat_obj = self.get_or_create_category(session, str(row['category']).strip())
                        category_id = cat_obj.id

                    if job:
                        # Update existing
                        job.title = title
                        job.company_id = company.id
                        job.category_id = category_id
                        job.location = location
                        job.salary = salary
                        job.experience = experience
                        job.description = clean_desc
                        job.requirements = clean_req
                        job.deadline = deadline
                        job.skills = extracted_skills
                        job.clean_text = bonus_clean_text
                    else:
                        # Create new
                        job = Job(
                            title=title,
                            company_id=company.id,
                            category_id=category_id,
                            location=location,
                            salary=salary,
                            experience=experience,
                            description=clean_desc,
                            requirements=clean_req,
                            job_url=job_url,
                            deadline=deadline,
                            skills=extracted_skills,
                            clean_text=bonus_clean_text,
                            is_active=True
                        )
                        session.add(job)
                        session.flush() # Populate job.id

                    # Skills relationships
                    existing_skill_ids = {js.skill_id for js in job.job_skills}
                    for s_name in extracted_skills:
                        skill_obj = self.get_or_create_skill(session, s_name)
                        if skill_obj.id not in existing_skill_ids:
                            js = JobSkill(job_id=job.id, skill_id=skill_obj.id)
                            session.add(js)
                            existing_skill_ids.add(skill_obj.id)
                    
                    # Commit every row to ensure we don't lose progress on error
                    session.commit()
                    processed_count += 1
                except Exception as ex:
                    session.rollback()
                    logger.error(f"Error processing row [{row.get('job_url', 'N/A')}]: {ex}")
                    continue

            logger.info(f"Progress: {processed_count}/{total_rows}")
            
        session.close()
        logger.info(f"Task complete. Imported: {processed_count}")

# ─── Orchestration ─────────────────────────────────────────────────────────────
def merge_datasets():
    logger.info("Merging sources...")
    if not os.path.exists(TOPCV_CSV) or not os.path.exists(VNW_CSV):
        logger.error("Missing input CSV files.")
        return False
    try:
        df1 = pd.read_csv(TOPCV_CSV, on_bad_lines='skip')
        df2 = pd.read_csv(VNW_CSV, on_bad_lines='skip')
        merged = pd.concat([df1, df2], ignore_index=True)
        merged = merged.drop_duplicates(subset=['job_url'])
        merged.to_csv(MERGED_CSV, index=False)
        logger.info(f"Consolidated data: {len(merged)} rows.")
        return True
    except Exception as e:
        logger.error(f"Merge error: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean, Merge, and Push Job Data.")
    parser.add_argument("--skip-merge", action="store_true", help="Use existing merged_jobs.csv.")
    args = parser.parse_args()

    if not args.skip_merge:
        if not merge_datasets():
            sys.exit(1)

    pipeline = DataImportPipeline(DATABASE_URL)
    pipeline.setup_db()
    pipeline.run_import(MERGED_CSV)
