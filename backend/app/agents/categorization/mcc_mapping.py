"""MCC (Merchant Category Code) to spending category mapping.

Categories: groceries, restaurants, transport, entertainment, utilities, healthcare,
shopping, travel, education, finance, subscriptions, fuel, atm_cash, government,
transfers, transfers_p2p, savings, charity, other.
"""

VALID_CATEGORIES: frozenset[str] = frozenset({
    "groceries", "restaurants", "transport", "entertainment", "utilities",
    "healthcare", "shopping", "travel", "education", "finance",
    "subscriptions", "fuel", "atm_cash", "government", "transfers",
    "transfers_p2p", "savings", "charity", "other",
    "uncategorized",
})


VALID_KINDS: frozenset[str] = frozenset({"spending", "income", "savings", "transfer"})

# Per tech spec §2.3 — which categories are valid for each transaction_kind.
# `spending` is a catch-all *except* `savings` (savings transfers are their own kind).
# `income` only ever lands in `other` or `uncategorized` (incoming flows aren't
# bucketed by merchant category). `savings` and `transfer` are 1:1 with their
# eponymous categories.
KIND_CATEGORY_RULES: dict[str, frozenset[str]] = {
    "spending": VALID_CATEGORIES - frozenset({"savings"}),
    "income": frozenset({"other", "uncategorized"}),
    "savings": frozenset({"savings"}),
    "transfer": frozenset({"transfers"}),
}


def kind_by_sign(amount: int) -> str:
    """Sign-based default for `transaction_kind` until the LLM emits one (Story 11.3)."""
    return "income" if amount > 0 else "spending"


def validate_kind_category(kind: str, category: str) -> bool:
    """Return True if (kind, category) is a valid combination per the matrix.

    Does not raise — callers decide whether to raise or fall back.
    """
    allowed = KIND_CATEGORY_RULES.get(kind)
    if allowed is None:
        return False
    return category in allowed

# DO NOT add MCCs 4816 (Computer Network Services) or 6012 (Financial
# Institutions - Merchandise). Both cover too many distinct real-world
# behaviors (ISP vs SaaS vs payment-processor passthrough for 4816;
# fintech catchall for 6012) to map deterministically. Description is
# authoritative — let the LLM pass resolve them. Rationale: tech-spec
# §2.2 "Explicitly NOT deterministically mapped".
MCC_TO_CATEGORY: dict[int, str] = {
    # Groceries
    5411: "groceries",   # Grocery Stores, Supermarkets
    5412: "groceries",   # Convenience Stores, except Discount Stores
    5422: "groceries",   # Freezer and Locker Meat Provisioners
    5441: "groceries",   # Candy, Nut, and Confectionery Stores
    5451: "groceries",   # Dairy Products Stores
    5462: "groceries",   # Bakeries
    5499: "groceries",   # Miscellaneous Food Stores

    # Restaurants / Food
    5812: "restaurants",  # Eating Places, Restaurants
    5814: "restaurants",  # Fast Food Restaurants
    5811: "restaurants",  # Caterers

    # Fuel
    5541: "fuel",   # Service Stations (with or without Ancillary Services)
    5542: "fuel",   # Automated Fuel Dispensers
    5983: "fuel",   # Fuel Dealers

    # Transport
    4111: "transport",   # Local and Suburban Commuter Passenger Transportation
    4112: "transport",   # Passenger Railways
    4121: "transport",   # Taxicabs and Limousines
    4131: "transport",   # Bus Lines
    4784: "transport",   # Toll and Bridge Fees
    4789: "transport",   # Transportation Services
    7523: "transport",   # Automobile Parking Lots and Garages

    # Utilities
    4899: "utilities",   # Cable, Satellite, and Other Pay Television/Radio
    4900: "utilities",   # Utilities: Electric, Gas, Water, Sanitary
    4814: "utilities",   # Telecommunication Services, including Local and Long Distance

    # Healthcare
    5912: "healthcare",  # Drug Stores and Pharmacies
    8011: "healthcare",  # Doctors and Physicians
    8049: "healthcare",  # Osteopathic Physicians
    8062: "healthcare",  # Hospitals
    8099: "healthcare",  # Medical Services and Health Practitioners
    8021: "healthcare",  # Dentists and Orthodontists
    8031: "healthcare",  # Optometrists and Ophthalmologists
    8041: "healthcare",  # Chiropractors
    8042: "healthcare",  # Optometrists, Ophthalmologist
    8043: "healthcare",  # Opticians, Optical Goods, and Eyeglasses
    8071: "healthcare",  # Medical and Dental Laboratories

    # Entertainment
    7832: "entertainment",  # Motion Picture Theaters
    7922: "entertainment",  # Theatrical Ticket Agencies
    7941: "entertainment",  # Professional Sports Clubs/Fields/Stadiums
    7996: "entertainment",  # Amusement Parks, Carnivals, Circuses
    7993: "entertainment",  # Video Game Arcades / Establishments
    7994: "entertainment",  # Video Game Arcades
    7995: "entertainment",  # Betting (including Lottery Tickets)
    7999: "entertainment",  # Recreation Services
    7801: "entertainment",  # Government Licensed Horse/Dog Racing
    5813: "entertainment",  # Bars, Cocktail Lounges, Discotheques
    7997: "entertainment",  # Country Clubs, Membership Sports Activities

    # Shopping
    5311: "shopping",   # Department Stores
    5331: "shopping",   # Variety Stores
    5600: "shopping",   # Apparel and Accessory Shops
    5611: "shopping",   # Men's and Boys' Clothing and Accessory Shops
    5621: "shopping",   # Women's Ready-to-Wear Stores
    5631: "shopping",   # Women's Accessory and Specialty Shops
    5641: "shopping",   # Children's and Infants' Wear Stores
    5651: "shopping",   # Family Clothing Stores
    5661: "shopping",   # Shoe Stores
    5699: "shopping",   # Miscellaneous Apparel and Accessory Shops
    5719: "shopping",   # Miscellaneous Home Furnishing Specialty Shops
    5722: "shopping",   # Household Appliance Stores
    5731: "shopping",   # Electronics Stores
    5734: "shopping",   # Computer and Computer Software Stores
    5945: "shopping",   # Hobby, Toy, and Game Shops
    5942: "shopping",   # Book Stores
    5943: "shopping",   # Stationery, Office, and School Supply Stores
    5944: "shopping",   # Jewelry Stores, Watches, Clocks, and Silverware
    5947: "shopping",   # Gift, Card, Novelty, and Souvenir Shops
    5999: "shopping",   # Miscellaneous and Specialty Retail Shops
    5200: "shopping",   # Home Supply Warehouse Stores (catches FOP-on-5200 merchants)

    # Courier / Delivery
    4215: "shopping",   # Courier Services (Nova Poshta, Meest, Justin, etc.)

    # Travel
    4511: "travel",   # Airlines, Air Carriers
    4722: "travel",   # Travel Agencies and Tour Operators
    7011: "travel",   # Hotels, Motels, and Resorts
    7012: "travel",   # Timeshares
    3000: "travel",   # Airlines
    4411: "travel",   # Cruise Lines
    7513: "travel",   # Truck and Utility Trailer Rentals
    7514: "travel",   # Passenger Car Rentals
    7519: "travel",   # Motor Home and Recreational Vehicle Rentals

    # Education
    8220: "education",  # Colleges, Universities
    8249: "education",  # Schools, Trade and Vocational
    8211: "education",  # Elementary and Secondary Schools
    8299: "education",  # Schools and Educational Services
    8241: "education",  # Correspondence Schools

    # ATM / Cash
    6010: "atm_cash",   # Manual Cash Disbursement — functionally same as ATM (6011)
    6011: "atm_cash",   # Automated Cash Disbursements (ATM)

    # Note: MCC 4829 (Wire Transfer / Money Order) is intentionally NOT mapped
    # here — it is semantically ambiguous (charity donations, P2P jar payments,
    # inter-account transfers all share this MCC). It falls through to the LLM
    # pass for description-aware classification per Story 11.2.

    # Charity / Social
    8398: "charity",    # Charitable and Social Service Organizations

    # Finance
    6099: "finance",   # Financial Institutions – Other
    6159: "finance",   # Federal Mortgage Loans
    6051: "finance",   # Non-Financial Institutions – Currency
    6211: "finance",   # Security Brokers/Dealers
    6300: "finance",   # Insurance
    6381: "finance",   # Insurance Premiums

    # Subscriptions (streaming services, SaaS)
    5968: "subscriptions",   # Direct Marketing – Continuity/Subscription Merchants

    # Government
    9311: "government",   # Tax Payments
    9399: "government",   # Government Services
    9411: "government",   # Government Loans
    9222: "government",   # Fines
}


def get_mcc_category(mcc: int | None) -> str | None:
    """Return the spending category for a given MCC code, or None if unmapped."""
    if mcc is None:
        return None
    return MCC_TO_CATEGORY.get(mcc)
