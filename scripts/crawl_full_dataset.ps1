# crawl_full_dataset.ps1
# Script to crawl ~5,000 IT jobs from TopCV and VietnamWorks

Write-Host "Starting Full Data Collection Pipeline (~5,000 Jobs)" -ForegroundColor Cyan

# 1. Crawl TopCV (~2,500 jobs)
Write-Host "`n[1/4] Crawling TopCV..." -ForegroundColor Yellow
python -m crawler.topcv_crawler --mode all --max-jobs 1000 --workers 3 --no-test

# 2. Crawl VietnamWorks (~2,500 jobs)
Write-Host "`n[2/4] Crawling VietnamWorks..." -ForegroundColor Yellow
python -m crawler.vietnamworks_crawler --mode all --max-jobs 100 --workers 3

# 3. Merge Datasets
Write-Host "`n[3/4] Merging datasets into TOTAL_IT_JOBS_DATASET.csv..." -ForegroundColor Yellow
python -c "import pandas as pd; df1=pd.read_csv('data/vnworks_it_full.csv'); df2=pd.read_csv('data/topcv_it_full_1.csv'); total=pd.concat([df1, df2], ignore_index=True).drop_duplicates(subset=['job_url']); total.to_csv('data/TOTAL_IT_JOBS_DATASET.csv', index=False); print(f'Successfully merged {len(total)} unique jobs.')"

# 4. Final Report
Write-Host "`n[4/4] Pipeline Complete!" -ForegroundColor Green
Write-Host "File saved at: data/TOTAL_IT_JOBS_DATASET.csv"
Write-Host "You can now run: python scripts/import_dataset.py --csv data/TOTAL_IT_JOBS_DATASET.csv" -ForegroundColor Gray
