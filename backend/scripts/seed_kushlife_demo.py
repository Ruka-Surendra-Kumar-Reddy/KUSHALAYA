"""Demo data: give the Lakshmi Reddy demo elder a KushLife trend to show.

Writes eight fortnightly KushLife scores (about four months) into
``elder.custom_attributes.safe_home.stability_score_history`` so the family
portal's KushLife trend has something to draw. Only the demo elder in the
tenant of the demo family login is touched, and every row is tagged
``"demo": True`` with a ``demo-kl-*`` visit id.

Idempotent: previous demo rows are replaced, real rows are kept.

Usage (from backend/, with the venv active):
    python -m scripts.seed_kushlife_demo           # dry run
    python -m scripts.seed_kushlife_demo --apply   # write
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SessionLocal
from app.models.elder import Elder
from app.models.user import User

DEMO_LOGIN = "lakshmi.family@sunrise-care.example"
DEMO_FIRST_NAME = "Lakshmi"
# Oldest first. 50 is her personal normal; a dip after a fall, then recovery
# with physiotherapy — the story the trend is meant to tell.
SCORES = [50, 47, 44, 49, 53, 55, 57, 58]


def build_rows(now: datetime) -> list[dict]:
    rows = []
    n = len(SCORES)
    for i, score in enumerate(SCORES):
        visited = now - timedelta(days=14 * (n - 1 - i))
        rows.append(
            {
                "visit_id": f"demo-kl-{i + 1}",
                "visited_at": visited.replace(microsecond=0).isoformat(),
                "score": score,
                "delta_from_baseline": score - 50,
                "band": "baseline" if i == 0 else ("better" if score > 50 else "watch" if score < 50 else "steady"),
                "demo": True,
            }
        )
    rows.reverse()  # history is stored newest first
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        login = db.query(User).filter(User.email == DEMO_LOGIN).first()
        if not login:
            print(f"Demo login {DEMO_LOGIN} not found - nothing to do.")
            return
        elder = (
            db.query(Elder)
            .filter(Elder.tenant_id == login.tenant_id, Elder.first_name == DEMO_FIRST_NAME)
            .first()
        )
        if not elder:
            print("Demo elder not found - nothing to do.")
            return

        attrs = dict(elder.custom_attributes or {})
        block = dict(attrs.get("safe_home") or {})
        existing = block.get("stability_score_history")
        real = [r for r in (existing if isinstance(existing, list) else []) if not (isinstance(r, dict) and r.get("demo"))]
        demo = build_rows(datetime.now(timezone.utc))
        merged = sorted(real + demo, key=lambda r: str(r.get("visited_at") or ""), reverse=True)[:60]

        print(f"Elder #{elder.id} {elder.first_name} {elder.last_name}: {len(real)} real rows kept, {len(demo)} demo rows")
        print("Scores oldest to newest:", SCORES)
        if not args.apply:
            print("Dry run — pass --apply to write.")
            return

        block["stability_score_history"] = merged
        attrs["safe_home"] = block
        elder.custom_attributes = attrs
        flag_modified(elder, "custom_attributes")
        db.commit()
        print("Written.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
