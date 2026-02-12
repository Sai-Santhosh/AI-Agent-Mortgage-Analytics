"""SQL validation and safety guardrails for NLQ-to-SQL."""
import re
from typing import Optional

# Disallowed SQL keywords (DML/DDL)
BLOCKED_KEYWORDS = {
    "insert", "update", "delete", "drop", "alter", "create", "truncate",
    "grant", "revoke", "execute", "exec", "xp_", "sp_", ";--", "/*", "*/",
}

# Allowed table prefixes (schema.table)
ALLOWED_TABLES = {
    "cpfb_state_delinquency_30_89", "cpfb_state_delinquency_90_plus",
    "cpfb_metro_delinquency_30_89", "cpfb_metro_delinquency_90_plus",
    "fred_mortgage_rates", "fhfa_hpi_state",
}


def validate_sql(sql: str, allowed_tables: Optional[set[str]] = None) -> tuple[bool, str]:
    """
    Validate SQL for safety. Returns (is_valid, error_message).
    """
    if not sql or not sql.strip():
        return False, "Empty SQL"
    s = sql.strip().upper()
    for kw in BLOCKED_KEYWORDS:
        if kw.upper() in s or kw.lower() in sql.lower():
            return False, f"Blocked keyword: {kw}"
    tables = allowed_tables or ALLOWED_TABLES
    # Extract table names: schema.table or table
    from_match = re.findall(r"\bFROM\s+(?:[\w]+\.)?([a-zA-Z0-9_]+)", sql, re.IGNORECASE)
    join_match = re.findall(r"\bJOIN\s+(?:[\w]+\.)?([a-zA-Z0-9_]+)", sql, re.IGNORECASE)
    all_tables = set(from_match + join_match)
    for t in all_tables:
        if t.lower() not in {x.lower() for x in tables}:
            return False, f"Table not allowed: {t}"
    # Require LIMIT for large result sets (optional warning)
    if "LIMIT" not in s and "TOP " not in s:
        # Auto-add LIMIT 1000 if missing
        pass  # We'll add in executor
    return True, ""


def add_limit_if_missing(sql: str, default_limit: int = 1000) -> str:
    """Add LIMIT clause if not present."""
    s = sql.strip()
    if "LIMIT" in s.upper():
        return s
    if s.rstrip().endswith(";"):
        s = s.rstrip()[:-1]
    return f"{s} LIMIT {default_limit}"
