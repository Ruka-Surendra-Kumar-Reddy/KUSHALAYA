"""LiveWell360 seed entrypoint (purge/reseed friendly).

Delegates to the existing SafeHome-named seed modules until those files are renamed.

Usage:
  python -m app.seed_livewell
"""

from app.seed_safehome import seed_safehome


def main() -> int:
    seed_safehome()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
