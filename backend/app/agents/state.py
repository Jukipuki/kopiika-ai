from typing import TypedDict


class FinancialPipelineState(TypedDict):
    job_id: str
    user_id: str
    upload_id: str
    transactions: list[dict]              # list of {id, date, description, mcc, amount}
    categorized_transactions: list[dict]  # list of {transaction_id, category, confidence_score, flagged, uncategorized_reason}
    errors: list[dict]                    # list of {step, error_code, message}
    step: str                             # current pipeline step name
    total_tokens_used: int                # LLM token tracking
    locale: str                           # 'en' or 'uk', from user.locale
    insight_cards: list[dict]             # output of education node
    literacy_level: str                   # 'beginner' or 'intermediate'
    completed_nodes: list[str]            # nodes that finished successfully
    failed_node: str | None               # node that failed (if any)
    pattern_findings: list[dict]          # output of pattern_detection_node; each dict mirrors a DB finding row
    detected_subscriptions: list[dict]    # output of pattern_detection_node recurring detector; each dict mirrors a DB row
    triage_category_severity_map: dict    # output of triage_node: {category: worst_severity} for education to override LLM cards
