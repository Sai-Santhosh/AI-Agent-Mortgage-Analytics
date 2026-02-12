#!/usr/bin/env python3
"""
Initialize database schema and load metadata registry.
Run: python scripts/init_db.py
"""
import sqlite3
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def init_schema(conn: sqlite3.Connection) -> None:
    """Create all database tables."""
    conn.executescript("""
        -- Dataset registry (like nlq_dataset_registry)
        CREATE TABLE IF NOT EXISTS nlq_dataset_registry (
            dataset_id TEXT PRIMARY KEY,
            dataset_name TEXT NOT NULL,
            domain TEXT NOT NULL,
            description TEXT NOT NULL,
            grain TEXT,
            freshness_sla TEXT,
            owner_team TEXT,
            pii_level TEXT DEFAULT 'none',
            allowed_schemas TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        -- Table registry
        CREATE TABLE IF NOT EXISTS nlq_table_registry (
            dataset_id TEXT NOT NULL,
            schema_name TEXT NOT NULL,
            table_name TEXT NOT NULL,
            table_desc TEXT NOT NULL,
            primary_keys TEXT,
            partition_cols TEXT,
            join_hints TEXT,
            important_cols TEXT,
            example_filters TEXT,
            updated_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (dataset_id, schema_name, table_name)
        );

        -- Domain definitions (metrics, formulas)
        CREATE TABLE IF NOT EXISTS nlq_domain_definitions (
            dataset_id TEXT NOT NULL,
            term TEXT NOT NULL,
            definition TEXT NOT NULL,
            formula_sql TEXT,
            notes TEXT,
            PRIMARY KEY (dataset_id, term)
        );

        -- CFPB State Delinquency (30-89 days)
        CREATE TABLE IF NOT EXISTS cpfb_state_delinquency_30_89 (
            date TEXT NOT NULL,
            state_fips TEXT NOT NULL,
            state_name TEXT NOT NULL,
            pct_30_89_days_late REAL NOT NULL,
            PRIMARY KEY (date, state_fips)
        );

        -- CFPB State Delinquency (90+ days)
        CREATE TABLE IF NOT EXISTS cpfb_state_delinquency_90_plus (
            date TEXT NOT NULL,
            state_fips TEXT NOT NULL,
            state_name TEXT NOT NULL,
            pct_90_plus_days_late REAL NOT NULL,
            PRIMARY KEY (date, state_fips)
        );

        -- CFPB Metro Delinquency (30-89 days)
        CREATE TABLE IF NOT EXISTS cpfb_metro_delinquency_30_89 (
            date TEXT NOT NULL,
            metro_area TEXT NOT NULL,
            pct_30_89_days_late REAL NOT NULL,
            PRIMARY KEY (date, metro_area)
        );

        -- CFPB Metro Delinquency (90+ days)
        CREATE TABLE IF NOT EXISTS cpfb_metro_delinquency_90_plus (
            date TEXT NOT NULL,
            metro_area TEXT NOT NULL,
            pct_90_plus_days_late REAL NOT NULL,
            PRIMARY KEY (date, metro_area)
        );

        -- FRED Mortgage Rates (30-year fixed)
        CREATE TABLE IF NOT EXISTS fred_mortgage_rates (
            date TEXT PRIMARY KEY,
            mort_30yr REAL,
            mort_15yr REAL,
            mort_5yr_arm REAL
        );

        -- FHFA House Price Index (simplified - state level)
        CREATE TABLE IF NOT EXISTS fhfa_hpi_state (
            period TEXT NOT NULL,
            state_fips TEXT NOT NULL,
            state_name TEXT,
            hpi_value REAL,
            hpi_yoy_change REAL,
            PRIMARY KEY (period, state_fips)
        );

        CREATE INDEX IF NOT EXISTS idx_cpfb_state_date ON cpfb_state_delinquency_30_89(date);
        CREATE INDEX IF NOT EXISTS idx_cpfb_state_state ON cpfb_state_delinquency_30_89(state_fips);
        CREATE INDEX IF NOT EXISTS idx_fred_date ON fred_mortgage_rates(date);
    """)


def load_metadata(conn: sqlite3.Connection) -> None:
    """Load metadata registry with dataset/table definitions."""
    datasets = [
        ("cpfb_delinquency", "CPFB Mortgage Delinquency", "delinquency",
         "Consumer Financial Protection Bureau mortgage performance data. Percent of mortgages 30-89 days delinquent and 90+ days delinquent. Available by state, metro area, and county. Data from Jan 2008 to present.",
         "state_month", "Monthly", "CFPB", "none", "main"),
        ("fred_rates", "FRED Mortgage Rates", "rates",
         "Federal Reserve Economic Data - 30-year and 15-year fixed mortgage rates from Freddie Mac Primary Mortgage Market Survey. Weekly data from 1971.",
         "weekly", "Weekly", "FRED", "none", "main"),
        ("fhfa_hpi", "FHFA House Price Index", "housing",
         "FHFA House Price Index - measures single-family home price changes from Fannie Mae and Freddie Mac repeat-sales. Available by state and metro.",
         "state_quarter", "Quarterly", "FHFA", "none", "main"),
    ]
    conn.executemany(
        """INSERT OR REPLACE INTO nlq_dataset_registry 
           (dataset_id, dataset_name, domain, description, grain, freshness_sla, owner_team, pii_level, allowed_schemas)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        datasets,
    )

    tables = [
        ("cpfb_delinquency", "main", "cpfb_state_delinquency_30_89",
         "State-level % of mortgages 30-89 days delinquent. Columns: date, state_fips, state_name, pct_30_89_days_late",
         "date, state_fips", "date", None,
         "date, state_fips, state_name, pct_30_89_days_late",
         "date BETWEEN '2020-01-01' AND '2025-12-31'"),
        ("cpfb_delinquency", "main", "cpfb_state_delinquency_90_plus",
         "State-level % of mortgages 90+ days delinquent. Columns: date, state_fips, state_name, pct_90_plus_days_late",
         "date, state_fips", "date", None,
         "date, state_fips, state_name, pct_90_plus_days_late",
         "date BETWEEN '2020-01-01' AND '2025-12-31'"),
        ("cpfb_delinquency", "main", "cpfb_metro_delinquency_30_89",
         "Metro area % mortgages 30-89 days delinquent. Columns: date, metro_area, pct_30_89_days_late",
         "date, metro_area", "date", None,
         "date, metro_area, pct_30_89_days_late",
         "date >= '2020-01-01'"),
        ("cpfb_delinquency", "main", "cpfb_metro_delinquency_90_plus",
         "Metro area % mortgages 90+ days delinquent. Columns: date, metro_area, pct_90_plus_days_late",
         "date, metro_area", "date", None,
         "date, metro_area, pct_90_plus_days_late",
         "date >= '2020-01-01'"),
        ("fred_rates", "main", "fred_mortgage_rates",
         "30-year and 15-year fixed mortgage rates. Columns: date, mort_30yr, mort_15yr, mort_5yr_arm",
         "date", None, None,
         "date, mort_30yr, mort_15yr, mort_5yr_arm",
         "date >= '2020-01-01'"),
        ("fhfa_hpi", "main", "fhfa_hpi_state",
         "FHFA House Price Index by state. Columns: period, state_fips, state_name, hpi_value, hpi_yoy_change",
         "period, state_fips", "period", None,
         "period, state_fips, state_name, hpi_value, hpi_yoy_change",
         "period >= '2020Q1'"),
    ]
    conn.executemany(
        """INSERT OR REPLACE INTO nlq_table_registry 
           (dataset_id, schema_name, table_name, table_desc, primary_keys, partition_cols, join_hints, important_cols, example_filters)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        tables,
    )

    definitions = [
        ("cpfb_delinquency", "delinquency_rate_30_89",
         "Percentage of mortgages 30-89 days past due. Use pct_30_89_days_late column.",
         None, "Early delinquency indicator"),
        ("cpfb_delinquency", "delinquency_rate_90_plus",
         "Percentage of mortgages 90+ days past due (serious delinquency). Use pct_90_plus_days_late.",
         None, "Serious delinquency; foreclosure risk"),
        ("cpfb_delinquency", "delinquency",
         "Mortgage delinquency - either 30-89 or 90+ days late depending on context.",
         None, None),
        ("fred_rates", "mortgage_rate",
         "30-year fixed mortgage rate from Freddie Mac PMMS. Column mort_30yr.",
         None, "Primary market rate"),
        ("fred_rates", "mort_30yr",
         "30-year fixed rate. mort_15yr for 15-year.",
         None, None),
        ("fhfa_hpi", "house_price_index",
         "FHFA House Price Index - repeat sales index. hpi_value. hpi_yoy_change = year-over-year % change.",
         None, "Based on GSE mortgages"),
    ]
    conn.executemany(
        """INSERT OR REPLACE INTO nlq_domain_definitions 
           (dataset_id, term, definition, formula_sql, notes)
           VALUES (?, ?, ?, ?, ?)""",
        definitions,
    )


def main() -> None:
    """Run initialization."""
    base = Path(__file__).parent.parent
    data_dir = base / "data"
    data_dir.mkdir(exist_ok=True)
    db_path = data_dir / "analytics.db"

    conn = sqlite3.connect(str(db_path))
    init_schema(conn)
    load_metadata(conn)
    conn.commit()
    conn.close()
    print(f"Database initialized at {db_path}")


if __name__ == "__main__":
    main()
