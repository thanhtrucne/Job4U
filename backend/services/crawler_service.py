"""
crawler_service.py
==================
Crawler orchestration service called by the admin API and APScheduler.

Key features:
  - Runs crawler modules as subprocesses (non-blocking via asyncio executor).
  - Real-time log streaming: subprocess stdout is captured line-by-line
    and appended to `_crawler_status["logs"]` for the admin dashboard poller.
  - Separate tasks for URL crawl and job detail crawl.
  - Combined task for the APScheduler.
"""
import logging
import asyncio
import subprocess
import sys
import os
import threading
from backend.database import AsyncSessionLocal
from backend.services.job_classifier_service import classifier_service

logger = logging.getLogger(__name__)

# ── Status dict ────────────────────────────────────────────────────────────────

_crawler_status: dict = {
    "phase":        "idle",   # idle | crawling_urls | crawling_jobs | completed | error
    "started_at":   None,
    "completed_at": None,
    "count":        0,
    "message":      "",
    "logs":         [],       # list[str] – last N lines from subprocess stdout
}

_crawler_running = False
_MAX_LOG_LINES   = 200       # keep at most this many lines in memory


def get_crawler_status() -> dict:
    """Return a safe copy of the current crawler status."""
    s = dict(_crawler_status)
    s["logs"] = list(_crawler_status["logs"])   # copy the list too
    return s


def _append_log(line: str):
    """Append a line to the in-memory log buffer (thread-safe enough for GIL)."""
    ts  = datetime.utcnow().strftime("%H:%M:%S")
    entry = f"[{ts}] {line.rstrip()}"
    _crawler_status["logs"].append(entry)
    # Trim to max size
    if len(_crawler_status["logs"]) > _MAX_LOG_LINES:
        _crawler_status["logs"] = _crawler_status["logs"][-_MAX_LOG_LINES:]


# ── Project root ───────────────────────────────────────────────────────────────

def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Subprocess runner with live stdout streaming ───────────────────────────────

def _run_subprocess(module: str, extra_args: list[str]) -> tuple[bool, str]:
    """
    Run a Python module as a subprocess, streaming its stdout/stderr
    line-by-line into the shared `_crawler_status["logs"]` buffer.

    Returns (success: bool, last_lines: str).
    """
    cmd = [sys.executable, "-m", module] + extra_args
    _append_log(f"Starting: {' '.join(cmd)}")

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=_project_root(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,   # merge stderr into stdout
            text=True,
            bufsize=1,                  # line-buffered
            encoding="utf-8",
            errors="replace",
        )

        last_lines: list[str] = []

        # Read line-by-line as they arrive
        for line in proc.stdout:          # type: ignore[union-attr]
            line = line.rstrip()
            if line:
                _append_log(line)
                last_lines.append(line)
                # Update live message with the latest meaningful line
                if "[OK]" in line or "[FAIL]" in line or "done" in line.lower() or "error" in line.lower():
                    _crawler_status["message"] = line[-200:]

        proc.wait(timeout=1800)          # 30-min hard cap

        tail = "\n".join(last_lines[-30:])
        if proc.returncode == 0:
            _append_log(f"Process finished OK (rc={proc.returncode})")
            return True, tail
        else:
            _append_log(f"Process exited with error rc={proc.returncode}")
            logger.error(f"{module} exited rc={proc.returncode}")
            return False, tail

    except subprocess.TimeoutExpired:
        _append_log(f"TIMEOUT: {module} exceeded 30 minutes")
        logger.error(f"{module} timed out")
        return False, "Timeout"
    except Exception as e:
        _append_log(f"Exception: {e}")
        logger.error(f"{module} error: {e}")
        return False, str(e)


# ── URL Crawl task ─────────────────────────────────────────────────────────────

async def run_url_crawl_task(pages: int = 50, category: str = "it"):
    """
    Trigger URL crawling in a thread-pool executor (non-blocking).
    Updates _crawler_status in real time.

    Args:
        pages:    Max listing pages to crawl.
        category: Job category slug (key in CATEGORY_PATHS).
    """
    global _crawler_running, _crawler_status

    if _crawler_running:
        logger.info("Crawler already running – skipping URL crawl request")
        return

    _crawler_running = True
    _crawler_status.update({
        "phase":        "crawling_urls",
        "started_at":   datetime.utcnow().isoformat(),
        "completed_at": None,
        "count":        0,
        "message":      f"Crawling URLs – category={category}, max {pages} pages…",
        "logs":         [],
    })
    await manager.send_crawl_status("crawling_urls")

    try:
        loop = asyncio.get_event_loop()
        success, msg = await loop.run_in_executor(
            None,
            lambda: _run_subprocess(
                "crawler.crawl_urls",
                ["--pages", str(pages), "--category", category],
            )
        )

        phase = "completed" if success else "error"
        _crawler_status.update({
            "phase":        phase,
            "completed_at": datetime.utcnow().isoformat(),
            "message":      f"URL crawl completed [OK] (category={category})" if success else f"URL crawl error: {msg[:200]}",
        })
        await manager.send_crawl_status(phase)
        logger.info(f"URL crawl finished. success={success} category={category}")

    except Exception as e:
        logger.error(f"run_url_crawl_task error: {e}")
        _crawler_status.update({
            "phase":        "error",
            "completed_at": datetime.utcnow().isoformat(),
            "message":      str(e),
        })
        await manager.send_crawl_status("error")
    finally:
        _crawler_running = False


# ── Job Detail Crawl task ──────────────────────────────────────────────────────

async def run_job_crawl_task(limit: int = 200):
    """
    Trigger job-detail crawling in a thread-pool executor (non-blocking).
    Updates _crawler_status in real time.
    """
    global _crawler_running, _crawler_status

    if _crawler_running:
        logger.info("Crawler already running – skipping job crawl request")
        return

    _crawler_running = True
    _crawler_status.update({
        "phase":        "crawling_jobs",
        "started_at":   datetime.utcnow().isoformat(),
        "completed_at": None,
        "count":        0,
        "message":      f"Crawling job details (limit {limit})…",
        "logs":         [],
    })
    await manager.send_crawl_status("crawling_jobs")

    try:
        loop = asyncio.get_event_loop()
        success, msg = await loop.run_in_executor(
            None,
            lambda: _run_subprocess("crawler.crawl_jobs", ["--limit", str(limit)])
        )

        phase = "completed" if success else "error"
        
        if success:
            _append_log("Starting AI Classification...")
            async with AsyncSessionLocal() as db:
                count = await classifier_service.classify_all_unlabeled(db)
                _append_log(f"AI Classification done: {count} jobs tagged.")
                from backend.services.structured_matching import normalize_job_skills
                normalized = await normalize_job_skills(db)
                await db.commit()
                _append_log(f"JD skill normalization done: {normalized} skill records.")

        _crawler_status.update({
            "phase":        phase,
            "completed_at": datetime.utcnow().isoformat(),
            "message":      "Job detail crawl completed [OK]" if success else f"Job crawl error: {msg[:200]}",
        })
        await manager.send_crawl_status(phase)
        logger.info(f"Job detail crawl finished. success={success}")

    except Exception as e:
        logger.error(f"run_job_crawl_task error: {e}")
        _crawler_status.update({
            "phase":        "error",
            "completed_at": datetime.utcnow().isoformat(),
            "message":      str(e),
        })
        await manager.send_crawl_status("error")
    finally:
        _crawler_running = False


# ── Full pipeline (used by APScheduler) ───────────────────────────────────────

async def run_crawler_task():
    """
    Full crawl pipeline: crawl URLs -> crawl job details.
    Triggered by the APScheduler on a cron interval.
    """
    global _crawler_running, _crawler_status

    if _crawler_running:
        logger.info("Crawler already running – skipping scheduled crawl")
        return

    _crawler_running = True
    _crawler_status.update({
        "phase":        "crawling_urls",
        "started_at":   datetime.utcnow().isoformat(),
        "completed_at": None,
        "count":        0,
        "message":      "Scheduled full crawl starting…",
        "logs":         [],
    })
    await manager.send_crawl_status("started")

    try:
        loop = asyncio.get_event_loop()

        # Step 1 – URLs
        _crawler_status["message"] = "Crawling URLs (scheduled)…"
        ok1, _ = await loop.run_in_executor(
            None, lambda: _run_subprocess("crawler.crawl_urls", ["--pages", "50"])
        )

        # Step 2 – Jobs
        _crawler_status.update({
            "phase":   "crawling_jobs",
            "message": "Crawling job details (scheduled)…",
        })
        ok2, _ = await loop.run_in_executor(
            None, lambda: _run_subprocess("crawler.crawl_jobs", ["--limit", "200"])
        )

        if ok2:
            _append_log("Scheduled AI Classification...")
            async with AsyncSessionLocal() as db:
                await classifier_service.classify_all_unlabeled(db)
                from backend.services.structured_matching import normalize_job_skills
                await normalize_job_skills(db)
                await db.commit()

        phase = "completed" if (ok1 and ok2) else "error"
        _crawler_status.update({
            "phase":        phase,
            "completed_at": datetime.utcnow().isoformat(),
            "message":      "Scheduled crawl completed [OK]" if phase == "completed" else "Scheduled crawl had errors [FAIL]",
        })
        await manager.send_crawl_status(phase)
        logger.info(f"Scheduled crawl done. ok1={ok1} ok2={ok2}")

    except Exception as e:
        logger.error(f"run_crawler_task error: {e}")
        _crawler_status.update({
            "phase":        "error",
            "completed_at": datetime.utcnow().isoformat(),
            "message":      str(e),
        })
        await manager.send_crawl_status("error")
    finally:
        _crawler_running = False
