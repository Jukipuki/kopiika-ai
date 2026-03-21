# Monobank CSV Export Format & Ukrainian Bank Statement Parsing

**Research Date:** 2026-03-15
**Research Agent:** Claude Opus 4.6

---

## 1. Monobank API Transaction Data Structure (Definitive)

The Monobank Open API (`/personal/statement/{account}/{from}/{to}`) returns transaction items with the following well-documented fields. This is the **authoritative data model** from which both the API JSON responses and the web cabinet CSV/XLS exports are derived.

### StatementItem Fields

| Field | JSON Key | Type | Unit | Description |
|-------|----------|------|------|-------------|
| Transaction ID | `id` | string | — | Unique identifier (e.g., `"ZuHWzqkKGVo="`) |
| Timestamp | `time` | int32 | Unix seconds | Transaction time (e.g., `1554466347`) |
| Description | `description` | string | — | Merchant/transaction description (e.g., `"Покупка щастя"`) |
| MCC | `mcc` | int32 | — | Merchant Category Code per ISO 18245 (e.g., `7997`) |
| Original MCC | `originalMcc` | int32 | — | Original MCC before any remapping |
| Hold Status | `hold` | bool | — | Whether the transaction is still pending/on hold |
| Amount | `amount` | int64 | kopiykas (cents) | Amount in account currency (negative = debit) (e.g., `-95000` = -950.00 UAH) |
| Operation Amount | `operationAmount` | int64 | kopiykas (cents) | Amount in transaction currency (for foreign currency ops) |
| Currency Code | `currencyCode` | int32 | ISO 4217 numeric | Currency code (e.g., `980` = UAH, `840` = USD, `978` = EUR) |
| Commission | `commissionRate` | int64 | kopiykas (cents) | Commission charged |
| Cashback | `cashbackAmount` | int64 | kopiykas (cents) | Cashback amount earned |
| Balance | `balance` | int64 | kopiykas (cents) | Account balance after this transaction |
| Comment | `comment` | string | — | User-added comment (optional) |
| Receipt ID | `receiptId` | string | — | Receipt identifier (for ATM withdrawals) |
| Invoice ID | `invoiceId` | string | — | Invoice ID (FOP/sole proprietorship accounts only) |
| Counter EDRPOU | `counterEdrpou` | string | — | Counterparty EDRPOU code (FOP accounts only) |
| Counter IBAN | `counterIban` | string | — | Counterparty IBAN (FOP accounts only) |
| Counter Name | `counterName` | string | — | Counterparty/merchant name |

**Total: 17 fields**

### Key Data Format Notes

- **All monetary amounts are in the smallest currency unit** (kopiykas for UAH, cents for USD/EUR). Divide by 100 for human-readable amounts.
- **Negative `amount` = expense/debit; positive = income/credit.**
- **`currencyCode` uses ISO 4217 numeric codes**, not alphabetic (980 not "UAH").
- **`time` is Unix timestamp in seconds**, not milliseconds.
- **API rate limit**: 1 request per 60 seconds, max 31 days + 1 hour per request, max 500 transactions per response.

### Example API JSON Response

```json
{
  "id": "ZuHWzqkKGVo=",
  "time": 1554466347,
  "description": "Покупка щастя",
  "mcc": 7997,
  "originalMcc": 7997,
  "hold": false,
  "amount": -95000,
  "operationAmount": -95000,
  "currencyCode": 980,
  "commissionRate": 0,
  "cashbackAmount": 1900,
  "balance": 1025000,
  "comment": "",
  "receiptId": "",
  "invoiceId": "",
  "counterEdrpou": "",
  "counterIban": "",
  "counterName": ""
}
```

**Sources:**
- [Monobank Open API Documentation](https://api.monobank.ua/docs/index.html)
- [Go Monobank Client - Transaction Struct](https://pkg.go.dev/github.com/vtopc/go-monobank)
- [Python Monobank Client](https://pypi.org/project/monobank/)
- [Monobank Ruby Gem](https://vergilet.github.io/monobank/)
- [Monobank MCP Server - get_statement tool](https://glama.ai/mcp/servers/@Aler1x/monobank-mcp/tools/get_statement)
- [Monobank API Statement Endpoint](https://monobank.ua/en/api-docs/providers/kliientski-personalni-dani/get--personal--statement--%7Baccount%7D--%7Bfrom%7D--%7Bto%7D)

---

## 2. Monobank CSV Export Format (Web Cabinet)

### How to Export

Monobank provides CSV/XLS export through:
1. **Monobank mobile app** - Export generates files named like `report_13-08-2024_19-36-25.csv`
2. **Web cabinet** (`web.monobank.ua`) - Navigate to statements, select date range, click "Export"

### CSV Format Specification

| Property | Value |
|----------|-------|
| **Encoding** | **Windows-1251** (for Universal Bank / Універсалбанк format) |
| **Separator** | Semicolon (`;`) — standard for European/Ukrainian locale CSV |
| **Decimal separator** | Comma (`,`) per Ukrainian locale |
| **Date format** | `dd.MM.yyyy HH:mm:ss` (Ukrainian standard) |
| **File extension** | `.csv` |
| **BOM** | Likely present for Windows-1251 compatibility |

### CSV Column Structure (Reconstructed from Multiple Sources)

Based on the API data model and third-party tool implementations, the Monobank web cabinet CSV export contains columns corresponding to the API fields. The **mono-cli** tool (which generates CSV from API data) produces these 11 columns in order:

| Column # | Header Name | Data Type | Example |
|----------|-------------|-----------|---------|
| 1 | ID | string | `ZuHWzqkKGVo=` |
| 2 | Time | Unix timestamp (int) | `1554466347` |
| 3 | Description | string (Cyrillic) | `Покупка щастя` |
| 4 | MCC | integer | `7997` |
| 5 | Hold | boolean | `false` |
| 6 | Amount | integer (kopiykas) | `-95000` |
| 7 | OperationAmount | integer (kopiykas) | `-95000` |
| 8 | CurrencyCode | integer (ISO 4217) | `980` |
| 9 | CommissionRate | integer (kopiykas) | `0` |
| 10 | CashbackAmount | integer (kopiykas) | `1900` |
| 11 | Balance | integer (kopiykas) | `1025000` |

**Important caveat:** The web cabinet's native CSV export (in "Universal Bank" format) likely uses **Ukrainian-language column headers** and may format amounts as human-readable decimals (e.g., `-950,00`) rather than kopiykas. The exact native column headers could not be confirmed through public documentation and may include Ukrainian names such as:
- "Дата і час" (Date and time)
- "Опис" (Description)
- "MCC"
- "Сума" (Amount)
- "Валюта" (Currency)
- "Комісія" (Commission)
- "Кешбек" (Cashback)
- "Залишок" (Balance)

**Sources:**
- [BookKeeper - Monobank Statement Import](https://bookkeeper.kiev.ua/zavantazhennya-vipisok-monobank-dlya-yurosib-v-bookkeeper/) — confirms Windows-1251 encoding and "Універсалбанк" format
- [Taxer.ua - How to get CSV from Monobank](https://taxer.ua/ru/kb/yak-otrymaty-csv-fail-vypysky-u-monobank)
- [mono-cli GitHub - CSV export tool](https://github.com/lungria/mono-cli) — source code confirms 11 columns
- [Monobudget - CSV import from Monobank](https://github.com/smaugfm/monobudget)

---

## 3. PrivatBank Statement Export Format

### Export Methods

PrivatBank (Приват24) provides statement export via:
1. **Приват24 web interface** - "Мої рахунки" (My Accounts) page, download in XLS format
2. **PrivatBank Merchant API** - Programmatic access requiring merchant registration and IP whitelisting

### CSV Structure (via privatbank2csv converter)

The `privatbank2csv` Ruby script converts PrivatBank XLS exports to CSV with these columns:

| Column # | Content | Description |
|----------|---------|-------------|
| 1 | Date/Time | Local timezone timestamp |
| 2 | Description | Basic transaction details |
| 3 | Currency info + Description | For foreign currency: original amount + exchange rate + description. For domestic: just description |
| 4 | Amount | Transaction sum in card currency |

### Additional Export Formats

- **Open Statement Service** ("Відкрита виписка") provides: date, amount, currency, counterparty name, period turnovers
- **DBF format** also supported as alternative to CSV
- **Business accounts** (Приват24 для Бізнесу) have separate statement formatting

**Sources:**
- [privatbank2csv GitHub](https://github.com/leonid-shevtsov/privatbank2csv) — Ruby converter for Приват24 XLS to CSV
- [Taxer.ua - How to get CSV from PrivatBank](https://taxer.ua/ru/kb/yak-otrimati-ssv-fajl-vipiski-v-privatbank)
- [PrivatBank Open Statement Service](https://privatbank.ua/business/openstatement)

---

## 4. Ukrainian Formatting Standards & Localization Details

### Date and Time

| Format | Pattern | Example |
|--------|---------|---------|
| Date | `dd.MM.yyyy` | `03.12.2024` |
| Time | `HH:mm` or `HH:mm:ss` | `21:05` or `21:05:33` |
| DateTime | `dd.MM.yyyy HH:mm:ss` | `03.12.2024 21:05:33` |
| Ordering | Little-endian (day first) | — |
| Clock | 24-hour | — |

### Numbers and Currency

| Property | Standard |
|----------|----------|
| Decimal separator | Comma (`,`) |
| Thousands separator | Space (` `) or non-breaking space |
| Currency symbol | `₴` (placed **after** the number) |
| Currency abbreviation | `грн` (Cyrillic) |
| Format | `999 999 999,99 ₴` |
| ISO 4217 alpha | `UAH` |
| ISO 4217 numeric | `980` |
| Locale code (Java/.NET) | `uk_UA` / `uk-UA` |

### Character Encoding

| Context | Encoding |
|---------|----------|
| Monobank web cabinet CSV | **Windows-1251** |
| Monobank API responses | **UTF-8** (JSON) |
| General modern Ukrainian web | UTF-8 |
| Legacy Ukrainian systems | Windows-1251 or KOI8-U |

### Cyrillic-Specific Parsing Concerns

- Ukrainian uses Cyrillic script with unique letters: `і`, `ї`, `є`, `ґ` (not present in Russian)
- Windows-1251 encoding covers both Ukrainian and Russian Cyrillic
- BOM (Byte Order Mark) may or may not be present in CSV files
- Some merchant descriptions mix Cyrillic and Latin characters
- Ukrainian `і` (U+0456) is visually identical to Latin `i` — watch out for mixed-script strings

**Sources:**
- [Freeformatter.com - Ukraine Standards](https://www.freeformatter.com/ukraine-standards-code-snippets.html)
- [Wikipedia - Date and time notation in Ukraine](https://en.wikipedia.org/wiki/Date_and_time_notation_in_Ukraine)
- [BookKeeper - Windows-1251 confirmation](https://bookkeeper.kiev.ua/zavantazhennya-vipisok-monobank-dlya-yurosib-v-bookkeeper/)

---

## 5. Existing Open-Source Parsers & Tools

### Monobank-Specific Tools

| Tool | Language | Purpose | URL |
|------|----------|---------|-----|
| **mono-cli** | Go | CLI tool that exports Monobank API statements to CSV, prints to stdout | [github.com/lungria/mono-cli](https://github.com/lungria/mono-cli) |
| **monobudget** | Kotlin | Auto-imports Monobank transactions to YNAB or Lunchmoney; supports CSV import mode | [github.com/smaugfm/monobudget](https://github.com/smaugfm/monobudget) |
| **python-monobank** | Python | Full API client for Monobank personal and corporate APIs | [github.com/vitalik/python-monobank](https://github.com/vitalik/python-monobank) |
| **go-monobank** | Go | Golang client for personal and corporate Monobank API | [github.com/vtopc/go-monobank](https://github.com/vtopc/go-monobank) |
| **monobank (Ruby)** | Ruby | Ruby gem for Monobank API | [github.com/vergilet/monobank](https://github.com/vergilet/monobank) |
| **monobank_api (Dart)** | Dart | Dart/Flutter SDK for Monobank API | [github.com/Sominemo/monobank_api](https://github.com/Sominemo/monobank_api) |
| **monobank-airtable** | JS | Exports Monobank data to various sources including Airtable | [github.com/andriyor/monobank-airtable](https://github.com/andriyor/monobank-airtable) |
| **monobank-api (.NET)** | C# | .NET wrapper for Monobank Open API | [github.com/maisak/monobank-api](https://github.com/maisak/monobank-api) |

### PrivatBank-Specific Tools

| Tool | Language | Purpose | URL |
|------|----------|---------|-----|
| **privatbank2csv** | Ruby | Converts Приват24 XLS statements to CSV | [github.com/leonid-shevtsov/privatbank2csv](https://github.com/leonid-shevtsov/privatbank2csv) |

### General Bank Statement Parsers (Potentially Adaptable)

| Tool | Language | Notes | URL |
|------|----------|-------|-----|
| **bank2ynab** | Python | Universal CSV-to-YNAB converter; config-driven, no Ukrainian banks pre-configured but easily extensible | [github.com/bank2ynab/bank2ynab](https://github.com/bank2ynab/bank2ynab) |
| **bankstatementparser** | Python | CAMT/ISO 20022 parser for financial transactions | [github.com/sebastienrousseau/bankstatementparser](https://github.com/sebastienrousseau/bankstatementparser) |
| **bank-statement-parser** | Python | PDF bank statement to hledger importer | [github.com/felgru/bank-statement-parser](https://github.com/felgru/bank-statement-parser) |

**Sources:**
- [GitHub Topics: monobank-api](https://github.com/topics/monobank-api)
- [GitHub Topics: monobank](https://github.com/topics/monobank)
- [bank2ynab Configuration](https://github.com/bank2ynab/bank2ynab/blob/develop/bank2ynab.conf)

---

## 6. MCC Codes & Merchant Category Patterns

### MCC Dataset for Ukrainian Banks

A dedicated open-source MCC codes dataset exists with Ukrainian, English, and Russian translations, categorized into 20 groups:

| Group Code | Category |
|------------|----------|
| AS | Agricultural services |
| AL | Airlines |
| HR | Hotels/Resorts |
| BS | Business services |
| ES | Entertainment services |
| FS | Food services |
| RS | Retail stores |
| TS | Transportation services |
| UT | Utilities |
| NC | Not categorized |
| ... | (20 groups total) |

**Source:** [Merchant-Category-Codes GitHub](https://github.com/Oleksios/Merchant-Category-Codes) — MIT licensed, JSON format, acknowledges Monobank for localization help.

### Common Ukrainian Merchant Description Patterns

Based on the API documentation and community implementations, the `description` field in Monobank transactions follows these patterns:

| Transaction Type | Description Pattern Example |
|------------------|-----------------------------|
| Card purchase (POS) | `"Сільпо"`, `"АТБ-Маркет"`, `"Rozetka"` |
| Online purchase | `"Uber"`, `"Netflix"`, `"Google"` |
| P2P transfer | Recipient name or `"Від: [Name]"` / `"Name"` |
| ATM withdrawal | ATM location or bank name |
| Account top-up | `"Поповнення"` or source description |
| Utility payment | Service provider name |

**Note:** The description field may contain:
- Pure Cyrillic text (Ukrainian merchant names)
- Pure Latin text (international merchants)
- Mixed Cyrillic + Latin text
- Newline characters (`\n`) within descriptions (the mono-cli tool explicitly strips these)

---

## 7. Known Parsing Pitfalls

### Encoding Issues
1. **Windows-1251 vs UTF-8 mismatch** — The web cabinet CSV is Windows-1251 encoded, but the API returns UTF-8 JSON. Parsers must detect or be configured for the correct encoding.
2. **BOM detection** — CSV files may or may not include a BOM; parsers should handle both cases.
3. **Mixed-script strings** — Ukrainian `і` (Cyrillic) and Latin `i` are visually identical but different code points. This can cause issues with string matching and deduplication.

### Amount Format Issues
4. **Kopiykas vs Hryvnias** — API returns amounts in kopiykas (smallest unit). The web CSV export may use either format. Always check whether to divide by 100.
5. **Comma as decimal separator** — Ukrainian locale uses comma for decimals (`-950,00` not `-950.00`). Standard CSV parsers expecting periods will fail.
6. **Semicolon delimiter** — Because comma is the decimal separator, Ukrainian CSVs often use semicolon (`;`) as the field delimiter, not comma.
7. **Negative amounts** — Expenses are negative, incomes positive. Some exports may use separate debit/credit columns instead.

### Date/Time Issues
8. **Unix timestamps vs formatted dates** — API uses Unix seconds; CSV export uses `dd.MM.yyyy HH:mm:ss`. Parsers must handle both.
9. **Timezone** — API timestamps are UTC. The web cabinet export may use Kyiv time (EET/EEST, UTC+2/+3).

### Description Field Issues
10. **Embedded newlines** — The `description` field can contain newline characters that break naive CSV parsing. The mono-cli tool explicitly handles this with regex replacement.
11. **Variable content** — Descriptions mix merchant names, transaction types, and sometimes include card masks or additional details with no fixed structure.

### API Limitations
12. **Rate limiting** — 1 request per 60 seconds for personal API; corporate API has no rate limit.
13. **Max period** — 31 days + 1 hour per single API request.
14. **Max transactions** — Up to 500 transactions per response.
15. **Hold transactions** — Transactions with `hold: true` are pending and may later change or be removed.

### Currency Handling
16. **Multi-currency** — For foreign currency transactions, `amount` is in account currency (after conversion) while `operationAmount` is in the original transaction currency. `currencyCode` corresponds to `operationAmount`.
17. **ISO 4217 numeric codes** — The API uses numeric codes (980, 840, 978), not alphabetic ("UAH", "USD", "EUR").

---

## 8. API Authentication & Access

### Personal API
1. Visit [https://api.monobank.ua/](https://api.monobank.ua/)
2. Authorize via QR code in the Monobank app
3. Obtain personal X-Token
4. Use as `X-Token` header in all API requests

### Corporate API
1. Generate ECDSA key pair using secp256k1 algorithm
2. Email public key to `api@monobank.ua`
3. Request user authorization via `access_request()` flow
4. No rate limitations (recommended for commercial use)

### Webhook Support
- Subscribe a URL via `POST /personal/webhook`
- Server receives `POST` with `{type: "StatementItem", data: {account: "...", statementItem: {...}}}`
- Server must respond with HTTP 200

**Sources:**
- [Monobank Open API Docs](https://api.monobank.ua/docs/index.html)
- [Python Monobank Client](https://pypi.org/project/monobank/)
- [Monobank API Topics on GitHub](https://github.com/topics/monobank-api)

---

## 9. Summary of Key ISO Codes

| Code | Standard | Meaning |
|------|----------|---------|
| `980` | ISO 4217 | Ukrainian Hryvnia (UAH) |
| `840` | ISO 4217 | US Dollar (USD) |
| `978` | ISO 4217 | Euro (EUR) |
| `985` | ISO 4217 | Polish Zloty (PLN) |
| `UA` | ISO 3166-1 alpha-2 | Ukraine |
| `UKR` | ISO 3166-1 alpha-3 | Ukraine |
| `804` | ISO 3166-1 numeric | Ukraine |
| `uk_UA` | POSIX locale | Ukrainian language, Ukraine |

---

## 10. Recommendations for Building a Parser

1. **For API-based import (recommended):** Use the Monobank Open API with the Python `monobank` library or equivalent. Data comes in UTF-8 JSON with well-defined numeric fields. Handle rate limiting with exponential backoff.

2. **For CSV file import:**
   - Detect encoding (try Windows-1251 first, fallback to UTF-8)
   - Use semicolon as delimiter
   - Parse amounts with comma as decimal separator
   - Strip embedded newlines from description fields
   - Convert `dd.MM.yyyy HH:mm:ss` dates to ISO 8601
   - Divide kopiykas amounts by 100 if the source uses smallest-unit format

3. **For multi-bank support:** Abstract the parser behind a common transaction interface with fields: `date`, `description`, `amount`, `currency`, `balance`, `category/mcc`, `counterparty`. Map each bank's specific format to this common model.
