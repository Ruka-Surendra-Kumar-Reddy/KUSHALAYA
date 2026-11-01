"""Background job worker — run on VM via systemd or cron.

  python -m app.worker           # poll until interrupted
  python -m app.worker --once    # process one job and exit (systemd timer friendly)
"""

from __future__ import annotations

import argparse
import logging
import time

from app.core.database import SessionLocal
import app.jobs.handlers  # noqa: F401 — register handlers + configure jobs
from app.services.background_job_service import BackgroundJobService

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="WorkforceOS background job worker")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process at most one job and exit",
    )
    parser.add_argument(
        "--drain",
        action="store_true",
        help="Process pending jobs until none are left (max 100), then exit — for the systemd timer",
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=5.0,
        help="Sleep between polls in daemon mode",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.drain:
        for _ in range(100):
            db = SessionLocal()
            try:
                job = BackgroundJobService.run_once(db)
            except Exception:
                # One broken job must not stop SOS escalation behind it.
                logger.exception("job run failed; continuing")
                db.rollback()
                continue
            finally:
                db.close()
            if not job:
                break
            logger.info("job %s %s -> %s", job.id, job.job_type, job.status)
        return
    if args.once:
        db = SessionLocal()
        try:
            job = BackgroundJobService.run_once(db)
            if job:
                logger.info("job %s %s -> %s", job.id, job.job_type, job.status)
            else:
                logger.info("no pending jobs")
        finally:
            db.close()
        return

    logger.info("worker started (poll=%ss)", args.poll_seconds)
    while True:
        db = SessionLocal()
        try:
            job = BackgroundJobService.run_once(db)
            if job:
                logger.info("job %s %s -> %s", job.id, job.job_type, job.status)
            else:
                time.sleep(args.poll_seconds)
        finally:
            db.close()


if __name__ == "__main__":
    main()
