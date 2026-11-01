"""Full SafeHomeOps / LiveWell360 bootstrap seed (super admin + tenant + clients + family).

Usage:
  python -m app.db_migrate && python -m app.seed_livewell
  # or: python -m app.seed_safehome
"""

from app.seed_safehome_demo import ensure_safehome_demo_data
from app.seed_super_admin import seed_super_admin


def seed_safehome() -> None:
    seed_super_admin()
    ensure_safehome_demo_data()


def main() -> int:
    seed_safehome()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
