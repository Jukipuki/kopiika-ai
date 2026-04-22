"""Rebuild the financial profile and recompute the health score for a single user.

Useful for dev/ops when transactions have been edited (re-categorized, kind
corrections, etc.) without a fresh upload to trigger the Celery pipeline.
The full pipeline runs `build_or_update_profile` then `calculate_health_score`;
this script does the same two steps synchronously.

Usage:
    cd backend
    .venv/bin/python -m scripts.recompute_health_score <user_id>
    .venv/bin/python -m scripts.recompute_health_score <cognito_sub> --by-sub
"""
import argparse
import sys
import uuid

from sqlmodel import select

from app.core.database import get_sync_session
from app.models.user import User
from app.services.health_score_service import calculate_health_score
from app.services.profile_service import build_or_update_profile


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("identifier", help="User UUID, or cognito_sub with --by-sub")
    parser.add_argument(
        "--by-sub",
        action="store_true",
        help="Treat identifier as cognito_sub instead of UUID",
    )
    args = parser.parse_args()

    with get_sync_session() as session:
        if args.by_sub:
            user = session.exec(
                select(User).where(User.cognito_sub == args.identifier)
            ).first()
            if user is None:
                print(f"No user with cognito_sub={args.identifier!r}", file=sys.stderr)
                return 1
            user_id = user.id
        else:
            try:
                user_id = uuid.UUID(args.identifier)
            except ValueError:
                print(
                    f"Invalid UUID {args.identifier!r} — pass --by-sub for cognito_sub lookup",
                    file=sys.stderr,
                )
                return 1

        profile = build_or_update_profile(session, user_id)
        print(
            f"Profile refreshed: period={profile.period_start}..{profile.period_end} "
            f"income={profile.total_income} expenses={profile.total_expenses}"
        )

        score = calculate_health_score(session, user_id)
        print(f"Score: {score.score}")
        print(f"Breakdown: {score.breakdown}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
