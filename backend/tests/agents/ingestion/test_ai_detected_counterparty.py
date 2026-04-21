"""AIDetectedParser populates first-class counterparty fields (Story 11.10 AC #14)."""
from __future__ import annotations

from app.agents.ingestion.parsers.ai_detected import AIDetectedParser
from app.agents.ingestion.parsers.monobank import MonobankParser


_PE_HEADER = "Дата;Сума;Призначення;Контрагент;ІПН;Рахунок\n"
_PE_ROWS = (
    "2026-04-10;5000.00;Оплата за послуги;ТОВ Приклад;12345678;UA00POPDUM111\n"
    "2026-04-11;-200.00;Переказ з власного рахунку;Іванов Іван;1234567890;UA00MONO999\n"
    "2026-04-12;-50.00;Тестовий рядок без контрагента;;;\n"
)

_MAPPING = {
    "delimiter": ";",
    "date_column": "Дата",
    "date_format": "%Y-%m-%d",
    "amount_column": "Сума",
    "amount_sign_convention": "negative_is_outflow",
    "description_column": "Призначення",
    "counterparty_name_column": "Контрагент",
    "counterparty_tax_id_column": "ІПН",
    "counterparty_account_column": "Рахунок",
}


def test_populates_first_class_counterparty_fields():
    parser = AIDetectedParser(_MAPPING)
    csv_bytes = (_PE_HEADER + _PE_ROWS).encode("utf-8")
    result = parser.parse(csv_bytes, encoding="utf-8", delimiter=";")

    assert result.parsed_count == 3
    t0, t1, t2 = result.transactions

    assert t0.counterparty_name == "ТОВ Приклад"
    assert t0.counterparty_tax_id == "12345678"
    assert t0.counterparty_account == "UA00POPDUM111"

    assert t1.counterparty_name == "Іванов Іван"
    assert t1.counterparty_tax_id == "1234567890"
    assert t1.counterparty_account == "UA00MONO999"

    # Empty cells → None on the first-class fields.
    assert t2.counterparty_name is None
    assert t2.counterparty_tax_id is None
    assert t2.counterparty_account is None


def test_raw_data_stash_path_removed():
    """Story 11.7's raw_data['counterparty_*'] keys must no longer appear."""
    parser = AIDetectedParser(_MAPPING)
    csv_bytes = (_PE_HEADER + _PE_ROWS).encode("utf-8")
    result = parser.parse(csv_bytes, encoding="utf-8", delimiter=";")

    for t in result.transactions:
        for key in list(t.raw_data.keys()):
            assert not key.startswith("counterparty_") or key in {
                "Контрагент",
                "ІПН",
                "Рахунок",
            }  # original header-keyed entries allowed; stash keys not
        assert "counterparty_name" not in t.raw_data
        assert "counterparty_tax_id" not in t.raw_data
        assert "counterparty_account" not in t.raw_data


def test_monobank_parser_leaves_counterparty_none():
    """Backward-compat: card parsers never set counterparty fields."""
    sample = (
        "Дата i час операції,Деталі операції,MCC,Сума в iнвалютi,Валюта,"
        "Сума в гривнях,Курс,Сума комiсiй (у валюті рахунку),Сума кешбеку "
        "(у валюті рахунку),Залишок пiсля операцiї\n"
        "01.04.2026 10:00:00,Coffee,5814,,,—,,,,0.00\n"
    )
    parser = MonobankParser()
    result = parser.parse(sample.encode("utf-8"), encoding="utf-8", delimiter=",")
    # Monobank parser may flag the row for other reasons; focus on the DTO defaults.
    for t in result.transactions:
        assert t.counterparty_name is None
        assert t.counterparty_tax_id is None
        assert t.counterparty_account is None
