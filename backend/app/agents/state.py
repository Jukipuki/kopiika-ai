from typing import TypedDict


class FinancialPipelineState(TypedDict):
    job_id: str
    user_id: str
    upload_id: str
    transactions: list[dict]              # list of {id, date, description, mcc, amount}
    categorized_transactions: list[dict]  # list of {transaction_id, category, confidence_score, flagged}
    errors: list[dict]                    # list of {step, error_code, message}
    step: str                             # current pipeline step name
    total_tokens_used: int                # LLM token tracking
    locale: str                           # 'en' or 'uk', from user.locale
    insight_cards: list[dict]             # output of education node
    literacy_level: str                   # 'beginner' or 'intermediate'
