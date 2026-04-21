#!/usr/bin/env python
"""Re-encrypt user_iban_registry rows against the current KMS CMK (Story 11.10 / AC #18).

Operator-initiated one-shot. Not scheduled — run during a maintenance window
after `settings.KMS_IBAN_KEY_ARN` has been rotated or when migrating from the
local-Fernet fallback to KMS in a staging environment.

Usage:
    # From backend/
    python ../scripts/rotate_iban_encryption.py [--dry-run]

Behaviour:
    * Reads all rows in batches of 500.
    * Decrypts with the current `app.core.crypto.decrypt_iban` (historical KMS
      key versions resolve transparently via KMS).
    * Re-encrypts with `encrypt_iban` (new ciphertext + fresh DEK).
    * Commits per batch so a crash leaves at most 500 rows in-flight.
    * Prints row count and elapsed time.

Safety:
    * `--dry-run` reports counts without writing.
    * Script takes an implicit row-level lock via UPDATE; coordinate with
      traffic that writes registry rows.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Make `backend` importable when the script is invoked from repo root.
_BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from sqlmodel import Session, select  # noqa: E402

from app.core.crypto import decrypt_iban, encrypt_iban  # noqa: E402
from app.core.database import get_sync_session  # noqa: E402
from app.models.user_iban_registry import UserIbanRegistry  # noqa: E402

BATCH = 500


def rotate(dry_run: bool) -> None:
    session_cm = get_sync_session()
    session: Session = next(session_cm)
    try:
        total = 0
        start = time.monotonic()
        # Keyset pagination on id — stable under concurrent inserts/updates,
        # unlike OFFSET which shifts when rows are added mid-run.
        last_id = None
        while True:
            stmt = select(UserIbanRegistry).order_by(UserIbanRegistry.id).limit(BATCH)
            if last_id is not None:
                stmt = stmt.where(UserIbanRegistry.id > last_id)
            rows = session.execute(stmt).scalars().all()
            if not rows:
                break
            for row in rows:
                plain = decrypt_iban(row.iban_encrypted)
                new_ct = encrypt_iban(plain)
                if not dry_run:
                    row.iban_encrypted = new_ct
                    session.add(row)
            if not dry_run:
                session.commit()
            total += len(rows)
            last_id = rows[-1].id
            print(f"  processed {total} rows…")
        elapsed = time.monotonic() - start
        suffix = " (dry-run)" if dry_run else ""
        print(f"Done{suffix}: {total} rows re-encrypted in {elapsed:.1f}s")
    finally:
        session.close()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    rotate(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
