"""Deterministic counterparty-ID classification (Story 11.10 / TD-049).

Ukrainian counterparty tax IDs come in three shapes relevant to PE statements:

* **EDRPOU (8 digits)** — legal entity identifier. Seed list of Ukrainian
  State Treasury and State Tax Service offices below; anything else 8-digit
  is a generic legal entity.
* **RNOKPP (10 digits)** — individual tax number. Appears on P2P transfers
  between registered persons.
* **Treasury / tax authority** — subset of EDRPOU matching the seed list.

The seed list is intentionally small: the central State Treasury EDRPOU plus
the primary State Tax Service office. Oblast-level offices add later as
production traffic surfaces them — the docstring records the source of truth
so future maintainers know what to audit.

Source: treasury.gov.ua and tax.gov.ua (public registries). Last verified
2026-04-21. If this list grows past ~50 entries, migrate to a YAML file
under `app/agents/categorization/data/` per the story's scope notes.

Rule precedence (applied left-to-right by categorization_node):

    Rule 5 (self-IBAN) > Rule 6 (treasury) > Rule 4 (description self-transfer)
        > Rule 7 (RNOKPP) / Rule 8 (EDRPOU)

Exported surface:
    edrpou_kind(tax_id)  -> Literal["treasury", "edrpou_8", "rnokpp_10", "unknown"]
    is_treasury_edrpou(tax_id) -> bool
"""
from __future__ import annotations

from typing import Literal

# Central State Treasury (Державна казначейська служба України) and the main
# State Tax Service (Державна податкова служба України). Keep concise —
# expand via a future story or config-data change.
_TREASURY_EDRPOU: frozenset[str] = frozenset(
    {
        "37567646",  # Державна казначейська служба України (central office)
        "43005000",  # Державна податкова служба України
    }
)

CounterpartyKind = Literal["treasury", "edrpou_8", "rnokpp_10", "unknown"]


def _clean(tax_id: str | None) -> str:
    if tax_id is None:
        return ""
    return "".join(c for c in tax_id if c.isdigit())


def is_treasury_edrpou(tax_id: str | None) -> bool:
    """True if the tax ID is a known Ukrainian Treasury / Tax Service EDRPOU."""
    return _clean(tax_id) in _TREASURY_EDRPOU


def edrpou_kind(tax_id: str | None) -> CounterpartyKind:
    """Classify a counterparty tax ID.

    Digit-length disambiguates EDRPOU (8) from RNOKPP (10). Treasury EDRPOUs
    win over the generic 8-digit bucket so the prompt can apply Rule 6.
    """
    digits = _clean(tax_id)
    if not digits:
        return "unknown"
    if digits in _TREASURY_EDRPOU:
        return "treasury"
    if len(digits) == 10:
        return "rnokpp_10"
    if len(digits) == 8:
        return "edrpou_8"
    return "unknown"
