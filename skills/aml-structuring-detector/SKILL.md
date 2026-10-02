---
name: aml-structuring-detector
description: "Detect cash structuring (smurfing) patterns in banking transaction data. Identifies accounts making repeated cash deposits just below a regulatory reporting threshold within a sliding window. Use when: detect structuring, find smurfing, cash deposits below CTR threshold, split deposits, suspicious cash pattern, AML cash detection, PMLA structuring."
---

# AML Structuring Detector

Detect accounts that are deliberately splitting cash deposits to stay below the Cash Transaction Report (CTR) threshold — a money-laundering technique known as **structuring** or **smurfing**.

## Regulatory Context

| Regulation | Requirement | Source Verified |
|---|---|---|
| PMLA 2002 s12 / PML Rules 2005 r.3 | Reporting entities must file CTRs for cash transactions >= INR 10 lakh | *Not from loaded sources* — the PMLA Act text is not in our DOCS.CHUNKS corpus. This is general regulatory knowledge. |
| RBI KYC Master Direction p.22, clause (f) | "When a RE has reason to believe that a customer (account-based or walk-in) is intentionally structuring a transaction into a series of transactions below the threshold of rupees fifty thousand." | **Verified**: chunk `RBI_KYC_Master_Direction-P22-C2` |
| RBI KYC Master Direction p.68 | AML software must be capable of "capturing, generating and analysing alerts for the purpose of filing CTR/STR" | **Verified**: chunk `RBI_KYC_Master_Direction-P68-C1` |
| FATF Recommendations p.110 | FIUs should receive "suspicious transaction reports... cash transaction reports, wire transfers reports and other threshold-based declarations" | **Verified**: chunk `FATF_Recommendations-P110-C2` |

> **Note on thresholds**: The p.22 chunk uses "rupees fifty thousand" which is the walk-in/non-account-based threshold. The INR 10 lakh CTR threshold comes from PML Rules 2005 Rule 3, which is not in our loaded PDFs. The 10L ceiling used in the detection SQL is standard industry practice for account-based CTR avoidance detection.

## Purpose

Given a transaction table, find accounts where **N or more cash deposits**, each between a floor and a ceiling amount (just below the CTR limit), occur within a sliding window of D days. Score and classify matches by severity.

## Inputs

The skill expects a Snowflake table (or view) with at minimum these columns:

| Column | Type | Description |
|---|---|---|
| `ACCOUNT_ID` | VARCHAR | Unique account identifier |
| `TXN_TYPE` | VARCHAR | `CREDIT` or `DEBIT` |
| `TXN_METHOD` | VARCHAR | Payment method — structuring targets `CASH` |
| `AMOUNT` | NUMBER | Transaction amount in local currency |
| `TXN_TIMESTAMP` | TIMESTAMP | When the transaction occurred |

### Configurable Thresholds

| Parameter | Default | Description |
|---|---|---|
| `amount_floor` | 500000 | Minimum deposit amount to consider (INR 5L) |
| `amount_ceil` | 999999 | Maximum deposit amount — just below CTR limit (INR 10L) |
| `min_deposits` | 3 | Minimum number of qualifying deposits to trigger |
| `window_days` | 7 | Sliding window in calendar days |

The defaults match the Indian PMLA/RBI regime (CTR threshold = INR 10 lakh). For other jurisdictions, adjust: e.g. USD 10,000 for FinCEN/BSA, EUR 15,000 for EU 4AMLD.

## Detection SQL

### Step 1 — Identify Qualifying Deposits

```sql
SELECT
    ACCOUNT_ID,
    TXN_TIMESTAMP,
    AMOUNT
FROM <transaction_table>
WHERE TXN_METHOD = 'CASH'
  AND TXN_TYPE  = 'CREDIT'
  AND AMOUNT BETWEEN :amount_floor AND :amount_ceil
```

### Step 2 — Sliding-Window Aggregation

Use a self-join to find clusters of deposits within the window:

```sql
WITH cash_deposits AS (
    SELECT ACCOUNT_ID, TXN_TIMESTAMP AS TS, AMOUNT
    FROM <transaction_table>
    WHERE TXN_METHOD = 'CASH'
      AND TXN_TYPE  = 'CREDIT'
      AND AMOUNT BETWEEN :amount_floor AND :amount_ceil
),
windowed AS (
    SELECT
        a.ACCOUNT_ID,
        a.TS AS ANCHOR_TS,
        COUNT(*)    AS DEPOSIT_COUNT,
        SUM(b.AMOUNT) AS TOTAL_AMOUNT,
        MIN(b.TS)   AS FIRST_DEPOSIT,
        MAX(b.TS)   AS LAST_DEPOSIT,
        DATEDIFF('day', MIN(b.TS), MAX(b.TS)) AS SPAN_DAYS
    FROM cash_deposits a
    JOIN cash_deposits b
      ON  a.ACCOUNT_ID = b.ACCOUNT_ID
      AND b.TS BETWEEN a.TS AND DATEADD('day', :window_days, a.TS)
    GROUP BY a.ACCOUNT_ID, a.TS
    HAVING COUNT(*) >= :min_deposits
)
SELECT DISTINCT
    ACCOUNT_ID,
    MAX(DEPOSIT_COUNT)  AS MAX_DEPOSITS_IN_WINDOW,
    MAX(TOTAL_AMOUNT)   AS MAX_WINDOW_AMOUNT,
    MIN(FIRST_DEPOSIT)  AS EARLIEST_DEPOSIT,
    MAX(LAST_DEPOSIT)   AS LATEST_DEPOSIT
FROM windowed
GROUP BY ACCOUNT_ID
ORDER BY MAX_DEPOSITS_IN_WINDOW DESC;
```

### Step 3 — Score and Classify

```sql
-- Severity tiers based on deposit count and total amount
SELECT
    *,
    CASE
        WHEN MAX_DEPOSITS_IN_WINDOW >= 5 THEN 'CRITICAL'
        WHEN MAX_DEPOSITS_IN_WINDOW >= 4 THEN 'HIGH'
        WHEN MAX_DEPOSITS_IN_WINDOW >= 3 THEN 'MEDIUM'
    END AS SEVERITY,
    ROUND(LEAST(MAX_DEPOSITS_IN_WINDOW / 5.0, 1.0), 4) AS SCORE
FROM <step_2_result>;
```

### Step 4 — Generate Alert Reason

```sql
-- Human-readable reason for each alert
MAX_DEPOSITS_IN_WINDOW || ' cash deposits totalling Rs '
    || TO_CHAR(MAX_WINDOW_AMOUNT, '99,99,999')
    || ' over ' || SPAN_DAYS || ' days. Each below Rs 10L CTR limit. Possible structuring.'
```

## Full End-to-End Example

Apply to `SENTINEL_DB.RAW.TRANSACTIONS` with default thresholds:

```sql
-- Prompt: "Detect structuring in our transaction data"
WITH cash_deposits AS (
    SELECT ACCOUNT_ID,
           TXN_TIMESTAMP AS TS,
           AMOUNT
    FROM SENTINEL_DB.RAW.TRANSACTIONS
    WHERE TXN_METHOD = 'CASH'
      AND TXN_TYPE  = 'CREDIT'
      AND AMOUNT BETWEEN 500000 AND 999999
),
windowed AS (
    SELECT
        a.ACCOUNT_ID,
        COUNT(*)       AS DEP_COUNT,
        SUM(b.AMOUNT)  AS TOTAL_AMT,
        DATEDIFF('day', MIN(b.TS), MAX(b.TS)) AS SPAN_DAYS
    FROM cash_deposits a
    JOIN cash_deposits b
      ON  a.ACCOUNT_ID = b.ACCOUNT_ID
      AND b.TS BETWEEN a.TS AND DATEADD('day', 7, a.TS)
    GROUP BY a.ACCOUNT_ID, a.TS
    HAVING COUNT(*) >= 3
)
SELECT
    ACCOUNT_ID,
    MAX(DEP_COUNT) AS DEPOSITS,
    MAX(TOTAL_AMT) AS AMOUNT,
    CASE WHEN MAX(DEP_COUNT) >= 5 THEN 'CRITICAL'
         WHEN MAX(DEP_COUNT) >= 4 THEN 'HIGH'
         ELSE 'MEDIUM' END AS SEVERITY,
    ROUND(LEAST(MAX(DEP_COUNT) / 5.0, 1.0), 4) AS SCORE
FROM windowed
GROUP BY ACCOUNT_ID
ORDER BY SCORE DESC, DEPOSITS DESC;
```

## Example Prompts

These are natural-language questions this skill can handle:

1. "Detect cash structuring patterns in our transaction data"
2. "Find accounts splitting cash deposits below 10 lakh"
3. "Are any customers making repeated cash deposits just under the CTR threshold?"
4. "Run the smurfing detection rule on the last 30 days of transactions"
5. "Which accounts triggered RULE-001 and what amounts were involved?"

## Expected Output

The detection query returns one row per flagged account:

```
ACCOUNT_ID  | DEPOSITS | AMOUNT     | SEVERITY | SCORE
------------|----------|------------|----------|------
ACCT-000113 | 6        | 5,106,597  | CRITICAL | 1.0000
ACCT-000110 | 6        | 5,104,241  | CRITICAL | 1.0000
ACCT-000155 | 4        | 3,407,268  | HIGH     | 0.8000
ACCT-000200 | 3        | 2,550,123  | MEDIUM   | 0.6000
```

Each row should be written to `RISK.ALERTS` with:
- `ALERT_TYPE = 'STRUCTURING'`
- `RULE_ID = 'RULE-001'`
- A human-readable REASON string (see Step 4)
- The SCORE and SEVERITY from the classification tier

## Integration with Sentinel

When deployed inside the Sentinel system, this skill's output feeds into:

1. **RISK.ALERTS** — persisted alert rows with score, severity, reason
2. **RISK.RULE_POLICY_LINKS** — primary citation: `RBI_KYC_Master_Direction` p.22 (structuring below threshold)
3. **APP.SENTINEL_AGENT** — the agent references these alerts when users ask about structuring
4. **APP.GENERATE_REPORT** — produces a formal SAR narrative grounded in the alert's evidence
5. **Streamlit Dashboard** — structuring alert count and precision/recall vs FRAUD_TRUTH

## Tuning Guide

| Scenario | Adjustment |
|---|---|
| Too many false positives | Raise `amount_floor` (e.g. 700000) or `min_deposits` (e.g. 4) |
| Missing split deposits across weeks | Increase `window_days` to 14 |
| Different jurisdiction (USD) | Set `amount_floor=8000`, `amount_ceil=9999`, per BSA/FinCEN |
| Hard-negative stress test | Add accounts with legitimate high-value cash (jewellers, petrol stations) — they should NOT trigger if amounts are above the ceiling or below the floor |

## Limitations

1. **Cash method only.** The rule filters on `TXN_METHOD = 'CASH'`. Structuring via cheque, demand draft, or digital wallets requires separate rules.
2. **Single-account scope.** Does not detect cross-account structuring where the same beneficial owner splits deposits across multiple accounts. That requires an entity-resolution step first.
3. **Fixed sliding window.** Uses a calendar-day window, not a rolling business-day window. Weekend deposits may cluster and inflate counts in a 7-day frame.
4. **No velocity decay.** All deposits within the window are weighted equally. A more sophisticated model could apply recency weighting.
5. **Threshold sensitivity.** The `amount_floor` of 500K is arbitrary — sophisticated structurers may deposit smaller amounts (e.g. 200K–400K). Lowering the floor will increase both recall and false positives.
6. **No counterparty analysis.** Does not check if the same depositor appears at multiple branches or uses different identities.
7. **Depends on TXN_METHOD accuracy.** If upstream data misclassifies payment methods (e.g. CASH tagged as INTERNAL), the rule will miss those transactions.
