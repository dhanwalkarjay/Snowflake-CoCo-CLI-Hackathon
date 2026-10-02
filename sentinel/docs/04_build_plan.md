# Sentinel — Build Plan

> Phased execution plan using Dynamic Tables, Cortex Search,
> a Semantic View, and a Cortex Agent.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                        CORTEX AGENT                              │
│              (SENTINEL_DB.APP.SENTINEL_AGENT)                    │
│                                                                  │
│  ┌─────────────────────┐    ┌──────────────────────────────┐     │
│  │   SEMANTIC VIEW     │    │      CORTEX SEARCH           │     │
│  │  (analytical SQL)   │    │  (regulation & policy RAG)   │     │
│  └────────┬────────────┘    └──────────────┬───────────────┘     │
│           │                                │                     │
│           ▼                                ▼                     │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │  CORE.*  (DIM/FACT dynamic tables)                      │     │
│  │  RISK.*  (Signal → Evidence → Finding dynamic tables)   │     │
│  │  DOCS.*  (Regulation & policy corpus)                   │     │
│  │  AUDIT.* (Audit log, model decisions)                   │     │
│  └─────────────────────────────────────────────────────────┘     │
│           ▲                                                      │
│           │                                                      │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │  RAW.*   (Source-of-record ingested tables)             │     │
│  └─────────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────┘
```

---

## Phase 0 — Foundation (DDL + Sample Data)

### P0.1 Create RAW Tables

Execute all `CREATE TABLE` statements from `01_data_model.md` § 1.

```sql
-- Run in order (FK dependencies):
-- 1. RAW.CUSTOMERS
-- 2. RAW.ACCOUNTS
-- 3. RAW.TRANSACTIONS
-- 4. RAW.LOANS
-- 5. RAW.LOAN_REPAYMENTS
-- 6. RAW.LIQUIDITY_POSITIONS
-- 7. RAW.WATCHLISTS
```

### P0.2 Create RISK Tables

```sql
-- Run in order:
-- 1. RISK.SIGNALS
-- 2. RISK.EVIDENCE
-- 3. RISK.FINDINGS
-- 4. RISK.ALERTS
-- 5. RISK.CASES
-- 6. RISK.CASE_EVIDENCE_LINK
-- 7. RISK.SAR_FILINGS
```

### P0.3 Create DOCS Tables

```sql
-- 1. DOCS.REGULATION_DOCS
-- 2. DOCS.POLICY_DOCS
```

### P0.4 Create AUDIT Tables

```sql
-- 1. AUDIT.AUDIT_LOG
-- 2. AUDIT.MODEL_DECISIONS
```

### P0.5 Load Sample Data

Use `COPY INTO` from a Snowflake stage or `INSERT` synthetic data for testing.
Minimum viable dataset:

| Table | Rows | Notes |
|-------|------|-------|
| CUSTOMERS | 1,000 | Mix of INDIVIDUAL/CORPORATE, varied risk ratings |
| ACCOUNTS | 2,500 | 2–3 accounts per customer |
| TRANSACTIONS | 50,000 | 30 days of history, include structuring/velocity patterns |
| LOANS | 500 | Include some SMA/NPA accounts |
| LOAN_REPAYMENTS | 3,000 | Include late payments |
| LIQUIDITY_POSITIONS | 90 | 30 days × 3 buckets minimum |
| WATCHLISTS | 200 | OFAC + internal entries |

---

## Phase 1 — Dynamic Tables (CORE Layer)

### P1.1 Create CORE Dynamic Tables

Execute from `01_data_model.md` § 2:

```sql
-- 1. CORE.DIM_CUSTOMERS       (target_lag: 10 min)
-- 2. CORE.DIM_ACCOUNTS        (target_lag: 10 min)
-- 3. CORE.FACT_TRANSACTIONS   (target_lag: 5 min)
-- 4. CORE.FACT_LOANS          (target_lag: 30 min)
-- 5. CORE.FACT_LIQUIDITY      (target_lag: 1 hr)
```

### P1.2 Validate CORE Layer

```sql
-- Check all DTs are refreshing
SELECT name, target_lag, refresh_mode, scheduling_state
FROM TABLE(INFORMATION_SCHEMA.DYNAMIC_TABLE_REFRESH_HISTORY())
WHERE name LIKE 'DIM_%' OR name LIKE 'FACT_%'
ORDER BY name;

-- Spot-check row counts
SELECT 'DIM_CUSTOMERS' AS dt, COUNT(*) FROM SENTINEL_DB.CORE.DIM_CUSTOMERS
UNION ALL
SELECT 'DIM_ACCOUNTS',      COUNT(*) FROM SENTINEL_DB.CORE.DIM_ACCOUNTS
UNION ALL
SELECT 'FACT_TRANSACTIONS',  COUNT(*) FROM SENTINEL_DB.CORE.FACT_TRANSACTIONS
UNION ALL
SELECT 'FACT_LOANS',         COUNT(*) FROM SENTINEL_DB.CORE.FACT_LOANS
UNION ALL
SELECT 'FACT_LIQUIDITY',     COUNT(*) FROM SENTINEL_DB.CORE.FACT_LIQUIDITY;
```

---

## Phase 2 — Signal → Evidence → Finding Pipeline

### P2.1 Create Signal Dynamic Tables

Execute signal detection DTs from `03_signal_evidence_finding.md` § 2.
Start with the structuring detector, then add:

```sql
-- Signal DTs (all target_lag: 5 min):
-- 1. RISK.SIG_STRUCTURING          (cash structuring)
-- 2. RISK.SIG_VELOCITY             (velocity spike)
-- 3. RISK.SIG_HIGH_VALUE           (high-value cash / CTR)
-- 4. RISK.SIG_DORMANT_ACTIVATION   (dormant account reactivation)
-- 5. RISK.SIG_GEO_ANOMALY          (geo/device anomalies)
-- 6. RISK.SIG_WATCHLIST            (watchlist screening)
-- 7. RISK.SIG_RAPID_FUND_THROUGH   (pass-through detection)
```

Each SIG_* DT writes to `RISK.SIGNALS` (or is itself a queryable DT that
downstream DTs reference).

### P2.2 Create Evidence Builder

```sql
-- RISK.EVIDENCE_BUILDER (target_lag: 10 min)
-- See 03_signal_evidence_finding.md § 3
```

### P2.3 Create Finding & Alert Builders

```sql
-- RISK.FINDING_BUILDER (target_lag: 10 min)
-- RISK.ALERT_BUILDER   (target_lag: 10 min)
-- See 03_signal_evidence_finding.md § 4
```

### P2.4 Validate RISK Pipeline

```sql
-- Insert test structuring pattern into RAW.TRANSACTIONS
-- Wait 40 min (worst-case end-to-end lag)
-- Verify signal → evidence → finding → alert propagation

SELECT 'SIGNALS'  AS layer, COUNT(*) FROM SENTINEL_DB.RISK.SIG_STRUCTURING
UNION ALL
SELECT 'EVIDENCE',          COUNT(*) FROM SENTINEL_DB.RISK.EVIDENCE_BUILDER
UNION ALL
SELECT 'FINDINGS',          COUNT(*) FROM SENTINEL_DB.RISK.FINDING_BUILDER
UNION ALL
SELECT 'ALERTS',            COUNT(*) FROM SENTINEL_DB.RISK.ALERT_BUILDER;
```

---

## Phase 3 — Cortex Search (Regulation & Policy RAG)

### P3.1 Load Document Corpus

Populate `DOCS.REGULATION_DOCS` and `DOCS.POLICY_DOCS` with chunked text.
Recommended chunk size: 512–1024 tokens with 10% overlap.

Key documents to include:

| Document | Source |
|----------|--------|
| RBI Master Direction on KYC | RBI circulars |
| PMLA Act 2002 (as amended) | Legislative text |
| RBI Guidelines on Fraud Classification | RBI/2024-25 |
| FATF 40 Recommendations | FATF |
| RBI ALM Guidelines | RBI circulars |
| Internal AML Policy | Bank policy |
| Internal Fraud Investigation SOP | Bank SOP |

### P3.2 Create Cortex Search Service

```sql
CREATE OR REPLACE CORTEX SEARCH SERVICE SENTINEL_DB.APP.SENTINEL_SEARCH
    ON CONTENT
    ATTRIBUTES TITLE, CATEGORY, REGULATORY_BODY
    WAREHOUSE = SENTINEL_WH
    TARGET_LAG = '1 hour'
    AS (
        SELECT
            DOC_ID || '-' || CONTENT_CHUNK_INDEX AS DOC_CHUNK_ID,
            TITLE,
            CATEGORY,
            REGULATORY_BODY,
            CONTENT
        FROM SENTINEL_DB.DOCS.REGULATION_DOCS
        UNION ALL
        SELECT
            DOC_ID || '-' || CONTENT_CHUNK_INDEX AS DOC_CHUNK_ID,
            TITLE,
            CATEGORY,
            DEPARTMENT AS REGULATORY_BODY,
            CONTENT
        FROM SENTINEL_DB.DOCS.POLICY_DOCS
    );
```

### P3.3 Test Cortex Search

```sql
-- Verify search works
SELECT *
FROM TABLE(
    SENTINEL_DB.APP.SENTINEL_SEARCH!SEARCH(
        query => 'What is the CTR reporting threshold for cash transactions in India?',
        columns => ['TITLE', 'CONTENT', 'CATEGORY'],
        limit => 5
    )
);
```

---

## Phase 4 — Semantic View

### P4.1 Create Semantic View

The semantic view exposes CORE + RISK tables for natural-language querying
via Cortex Analyst. It defines business-friendly names, metrics, and
relationships.

```sql
CREATE OR REPLACE SEMANTIC VIEW SENTINEL_DB.APP.SENTINEL_SV
    COMMENT = 'Sentinel: Banking fraud, AML & regulatory copilot'
AS
TABLES (
    -- CORE dimensions
    SENTINEL_DB.CORE.DIM_CUSTOMERS
        COMMENT = 'Customer master with KYC status and risk ratings'
        PRIMARY KEY (CUSTOMER_ID)
        WITH COLUMNS (
            CUSTOMER_ID     COMMENT = 'Unique customer identifier',
            CUSTOMER_TYPE   COMMENT = 'INDIVIDUAL or CORPORATE',
            FULL_NAME       COMMENT = 'Customer full name',
            NATIONALITY     COMMENT = 'ISO 3166-1 alpha-3 country code',
            CITY            COMMENT = 'City of residence',
            STATE           COMMENT = 'State/province',
            COUNTRY         COMMENT = 'Country of residence',
            KYC_STATUS      COMMENT = 'KYC verification status: PENDING, VERIFIED, EXPIRED, REJECTED',
            RISK_RATING     COMMENT = 'Customer risk rating: LOW, MEDIUM, HIGH, PEP, SANCTIONED',
            PEP_FLAG        COMMENT = 'Politically Exposed Person flag',
            ONBOARDED_AT    COMMENT = 'Date the customer was onboarded',
            TENURE_DAYS     COMMENT = 'Days since onboarding',
            KYC_OVERDUE_FLAG COMMENT = 'True if KYC verification is overdue for refresh'
        ),

    SENTINEL_DB.CORE.DIM_ACCOUNTS
        COMMENT = 'Account master with balances and status'
        PRIMARY KEY (ACCOUNT_ID)
        FOREIGN KEY (CUSTOMER_ID) REFERENCES DIM_CUSTOMERS
        WITH COLUMNS (
            ACCOUNT_ID      COMMENT = 'Unique account identifier',
            CUSTOMER_ID     COMMENT = 'Owning customer ID',
            ACCOUNT_TYPE    COMMENT = 'Account type: SAVINGS, CURRENT, LOAN, FD, NRE, NRO, CC',
            CURRENCY        COMMENT = 'Account currency (ISO 4217)',
            CURRENT_BALANCE COMMENT = 'Current account balance' METRIC,
            STATUS          COMMENT = 'Account status: ACTIVE, DORMANT, FROZEN, CLOSED',
            ACCOUNT_AGE_DAYS COMMENT = 'Days since account was opened'
        ),

    -- CORE facts
    SENTINEL_DB.CORE.FACT_TRANSACTIONS
        COMMENT = 'Enriched transactions with cross-border and high-value flags'
        PRIMARY KEY (TXN_ID)
        FOREIGN KEY (CUSTOMER_ID) REFERENCES DIM_CUSTOMERS
        FOREIGN KEY (ACCOUNT_ID) REFERENCES DIM_ACCOUNTS
        WITH COLUMNS (
            TXN_ID          COMMENT = 'Unique transaction identifier',
            ACCOUNT_ID      COMMENT = 'Account that initiated/received the transaction',
            CUSTOMER_ID     COMMENT = 'Customer who owns the account',
            TXN_TYPE        COMMENT = 'CREDIT or DEBIT',
            TXN_METHOD      COMMENT = 'Payment method: UPI, NEFT, RTGS, IMPS, SWIFT, CASH, CHEQUE, CARD, INTERNAL',
            AMOUNT          COMMENT = 'Transaction amount in account currency' METRIC,
            COUNTERPARTY_NAME    COMMENT = 'Name of the counterparty',
            COUNTERPARTY_COUNTRY COMMENT = 'Country of the counterparty',
            CHANNEL         COMMENT = 'Transaction channel: MOBILE, INTERNET, BRANCH, ATM, API',
            TXN_TIMESTAMP   COMMENT = 'Timestamp of the transaction',
            TXN_DATE        COMMENT = 'Date of the transaction',
            STATUS          COMMENT = 'Transaction status: COMPLETED, PENDING, FAILED, REVERSED',
            IS_CROSS_BORDER COMMENT = 'True if counterparty is in a different country',
            IS_HIGH_VALUE   COMMENT = 'True if amount >= 10 lakh INR',
            IS_CTR_REPORTABLE COMMENT = 'True if cash transaction >= 10 lakh (CTR threshold)'
        ),

    SENTINEL_DB.CORE.FACT_LOANS
        COMMENT = 'Loan portfolio with RBI NPA/SMA classification'
        PRIMARY KEY (LOAN_ID)
        FOREIGN KEY (CUSTOMER_ID) REFERENCES DIM_CUSTOMERS
        FOREIGN KEY (ACCOUNT_ID) REFERENCES DIM_ACCOUNTS
        WITH COLUMNS (
            LOAN_ID              COMMENT = 'Unique loan identifier',
            CUSTOMER_ID          COMMENT = 'Borrowing customer',
            LOAN_TYPE            COMMENT = 'Loan type: PERSONAL, HOME, VEHICLE, GOLD, BUSINESS, MICROFINANCE',
            PRINCIPAL            COMMENT = 'Original loan principal' METRIC,
            INTEREST_RATE        COMMENT = 'Annualised interest rate (%)',
            OUTSTANDING_BALANCE  COMMENT = 'Current outstanding balance' METRIC,
            DPD                  COMMENT = 'Days past due on repayment',
            NPA_FLAG             COMMENT = 'True if classified as NPA',
            STATUS               COMMENT = 'Loan status: ACTIVE, CLOSED, WRITTEN_OFF, RESTRUCTURED',
            ASSET_CLASSIFICATION COMMENT = 'RBI classification: STANDARD, SMA, NPA_SUBSTANDARD, NPA_DOUBTFUL, NPA_LOSS',
            SMA_CATEGORY         COMMENT = 'SMA sub-classification: SMA-0, SMA-1, SMA-2'
        ),

    SENTINEL_DB.CORE.FACT_LIQUIDITY
        COMMENT = 'ALM liquidity positions with LCR/NSFR ratios'
        PRIMARY KEY (POSITION_ID)
        WITH COLUMNS (
            POSITION_ID     COMMENT = 'Unique position identifier',
            REPORTING_DATE  COMMENT = 'ALM reporting date',
            BUCKET          COMMENT = 'Time bucket: OVERNIGHT, 2_7D, 8_14D, etc.',
            ASSET_CLASS     COMMENT = 'Asset class: CASH, GOVT_SECURITIES, etc.',
            INFLOWS         COMMENT = 'Expected inflows' METRIC,
            OUTFLOWS        COMMENT = 'Expected outflows' METRIC,
            NET_POSITION    COMMENT = 'Net inflow minus outflow' METRIC,
            LCR_RATIO       COMMENT = 'Liquidity Coverage Ratio' METRIC,
            NSFR_RATIO      COMMENT = 'Net Stable Funding Ratio' METRIC,
            LCR_BREACH      COMMENT = 'True if LCR < 100%',
            NSFR_BREACH     COMMENT = 'True if NSFR < 100%'
        ),

    -- RISK tables
    SENTINEL_DB.RISK.ALERTS
        COMMENT = 'Active fraud/AML/compliance alerts'
        PRIMARY KEY (ALERT_ID)
        FOREIGN KEY (FINDING_ID) REFERENCES FINDINGS
        WITH COLUMNS (
            ALERT_ID        COMMENT = 'Unique alert identifier',
            FINDING_ID      COMMENT = 'Finding that generated this alert',
            ENTITY_TYPE     COMMENT = 'Entity type: CUSTOMER, ACCOUNT, TRANSACTION',
            ENTITY_ID       COMMENT = 'Entity identifier',
            ALERT_TYPE      COMMENT = 'Alert type: FRAUD_SUSPECTED, AML_STR, CTR, KYC_OVERDUE, NPA_EARLY_WARNING, LIQUIDITY_BREACH',
            SEVERITY        COMMENT = 'Alert severity: LOW, MEDIUM, HIGH, CRITICAL',
            STATUS          COMMENT = 'Alert status: OPEN, INVESTIGATING, ESCALATED, CLOSED_TP, CLOSED_FP',
            ASSIGNED_TO     COMMENT = 'Analyst assigned to the alert',
            CREATED_AT      COMMENT = 'When the alert was created',
            SLA_DUE_AT      COMMENT = 'SLA deadline for resolution'
        ),

    SENTINEL_DB.RISK.FINDINGS
        COMMENT = 'Adjudicated risk findings from the detection pipeline'
        PRIMARY KEY (FINDING_ID)
        WITH COLUMNS (
            FINDING_ID      COMMENT = 'Unique finding identifier',
            ENTITY_TYPE     COMMENT = 'Entity type',
            ENTITY_ID       COMMENT = 'Entity identifier',
            TYPOLOGY        COMMENT = 'Risk typology: STRUCTURING, LAYERING, SMURFING, etc.',
            SEVERITY        COMMENT = 'Finding severity',
            CLASSIFICATION  COMMENT = 'TP/FP/ESCALATE/UNDER_REVIEW',
            NARRATIVE       COMMENT = 'AI-generated investigation narrative',
            RECOMMENDED_ACTION COMMENT = 'Recommended next step: DISMISS, MONITOR, ALERT, FILE_SAR, FREEZE_ACCOUNT'
        ),

    SENTINEL_DB.RISK.CASES
        COMMENT = 'Investigation cases grouping alerts and evidence'
        PRIMARY KEY (CASE_ID)
        WITH COLUMNS (
            CASE_ID         COMMENT = 'Unique case identifier',
            CASE_TYPE       COMMENT = 'Case type: FRAUD, AML, REGULATORY, COMPLIANCE',
            ENTITY_TYPE     COMMENT = 'Primary entity type under investigation',
            ENTITY_ID       COMMENT = 'Primary entity under investigation',
            SUBJECT         COMMENT = 'Case subject line',
            STATUS          COMMENT = 'Case status: OPEN, IN_PROGRESS, PENDING_SAR, CLOSED_TP, CLOSED_FP',
            PRIORITY        COMMENT = 'Case priority: LOW, MEDIUM, HIGH, CRITICAL',
            ASSIGNED_TO     COMMENT = 'Investigating analyst',
            OUTCOME         COMMENT = 'Case outcome: FILED_SAR, ACCOUNT_FROZEN, NO_ACTION, MONITORING',
            OPENED_AT       COMMENT = 'When the case was opened',
            CLOSED_AT       COMMENT = 'When the case was closed'
        ),

    SENTINEL_DB.RISK.SAR_FILINGS
        COMMENT = 'Suspicious Activity / Transaction Reports filed with regulators'
        PRIMARY KEY (SAR_ID)
        FOREIGN KEY (CASE_ID) REFERENCES CASES
        WITH COLUMNS (
            SAR_ID          COMMENT = 'Unique SAR identifier',
            CASE_ID         COMMENT = 'Parent case',
            FILING_TYPE     COMMENT = 'Filing type: STR, CTR, CROSS_BORDER, COUNTERFEIT',
            REGULATORY_BODY COMMENT = 'Target regulator: FIU_IND, FINCEN, NCA',
            AMOUNT_INVOLVED COMMENT = 'Total amount involved in the suspicious activity' METRIC,
            STATUS          COMMENT = 'Filing status: DRAFT, SUBMITTED, ACKNOWLEDGED, RETURNED'
        )
);
```

### P4.2 Validate Semantic View

```sql
DESCRIBE SEMANTIC VIEW SENTINEL_DB.APP.SENTINEL_SV;
```

---

## Phase 5 — Cortex Agent

### P5.1 Create the Agent

```sql
CREATE OR REPLACE CORTEX AGENT SENTINEL_DB.APP.SENTINEL_AGENT
    COMMENT = 'Sentinel: Banking fraud, AML & regulatory-reporting copilot'
    EXTERNAL_ACCESS_INTEGRATIONS = ()
AS
ANALYST(
    SEMANTIC_VIEW => 'SENTINEL_DB.APP.SENTINEL_SV'
)
SEARCH(
    SERVICE => 'SENTINEL_DB.APP.SENTINEL_SEARCH'
);
```

### P5.2 Test the Agent

Example queries to validate:

| # | Query | Expected Behaviour |
|---|-------|--------------------|
| 1 | "How many open CRITICAL alerts do we have?" | Analyst → SQL on RISK.ALERTS |
| 2 | "Show me the top 10 customers by transaction volume this month" | Analyst → SQL on CORE.FACT_TRANSACTIONS |
| 3 | "What is the RBI threshold for cash transaction reporting?" | Search → DOCS.REGULATION_DOCS |
| 4 | "List all NPA loans with outstanding > 50 lakh" | Analyst → SQL on CORE.FACT_LOANS |
| 5 | "What is our current LCR ratio?" | Analyst → SQL on CORE.FACT_LIQUIDITY |
| 6 | "Summarise the FATF recommendations on customer due diligence" | Search → DOCS.REGULATION_DOCS |
| 7 | "Show structuring alerts raised in the last 7 days with SLA breaches" | Analyst → SQL join ALERTS + FINDINGS |

---

## Phase Summary

| Phase | Deliverable | Dependencies |
|-------|-------------|--------------|
| **P0** | RAW + RISK + DOCS + AUDIT DDL, sample data | SENTINEL_DB, SENTINEL_WH (done) |
| **P1** | CORE dynamic tables (5 DTs) | P0 (RAW tables with data) |
| **P2** | Signal → Evidence → Finding DTs (10+ DTs) | P1 (CORE layer) |
| **P3** | Cortex Search service on DOCS | P0 (DOCS tables with data) |
| **P4** | Semantic View over CORE + RISK | P1 + P2 (tables must exist) |
| **P5** | Cortex Agent wiring SV + Search | P3 + P4 |

---

## Operational Checklist

- [ ] **Resource monitor**: SENTINEL_RM is active (150 credits, suspend at 90%) — done
- [ ] **Warehouse**: SENTINEL_WH X-Small with 60s auto-suspend — done
- [ ] **Grants**: Create roles `SENTINEL_ANALYST`, `SENTINEL_ENGINEER`, `SENTINEL_ADMIN` with appropriate privileges
- [ ] **Streams** (optional): Add streams on RAW tables if using Snowpipe Streaming for real-time ingestion
- [ ] **Alerts**: Create Snowflake ALERT objects for SLA breach monitoring on `RISK.ALERTS`
- [ ] **Tasks**: Schedule periodic cleanup of dismissed signals (> 90 days) and closed cases (> 1 year)
- [ ] **Tags**: Apply `SNOWFLAKE.CORE.CERTIFICATION_STATUS = 'CERTIFIED'` to CORE and RISK DTs after validation
