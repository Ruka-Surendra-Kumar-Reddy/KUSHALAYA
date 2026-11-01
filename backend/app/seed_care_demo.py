"""Seed SafeHomeOps demo (alias for seed_safehome).

Usage:
  python -m app.db_migrate && python -m app.seed_care_demo
"""

from app.seed_safehome import seed_safehome


def seed_care_demo() -> None:
    seed_safehome()


if __name__ == "__main__":
    seed_care_demo()
