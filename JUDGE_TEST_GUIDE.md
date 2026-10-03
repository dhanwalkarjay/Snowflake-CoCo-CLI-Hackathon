# SENTINEL Judge Testing Guide

## Credentials

| Field             | Value                        |
|-------------------|------------------------------|
| Account           | `HFTPCWG-PH93773`           |
| Snowsight URL     | https://app.snowflake.com/HFTPCWG/PH93773/ |
| Username          | `SENTINEL_JUDGE_USER`        |
| Password          | `S3nt!nel_Jdg#2026xQ`       |
| Default Role      | `SENTINEL_JUDGE`             |
| Default Warehouse | `SENTINEL_JUDGE_WH`         |

## Streamlit App URL

https://app.snowflake.com/HFTPCWG/PH93773/#/streamlit-apps/SENTINEL_DB.APP.SENTINEL

## Test Steps

### Step 1 — Log in
1. Open the Snowsight URL above in a browser.
2. Enter the username and password.
3. You should land with role `SENTINEL_JUDGE` and warehouse `SENTINEL_JUDGE_WH`.

### Step 2 — Open the Streamlit App
1. Navigate to the Streamlit app URL above, or go to Projects > Streamlit > SENTINEL.
2. The app should load and be fully interactive.

### Step 3 — Test the Cortex Agent
Run in a SQL worksheet or use the app's chat:
```sql
CALL SENTINEL_DB.APP.AGENT_CHAT('How many open alerts are there by severity?');
```

### Step 4 — Test Report Generation
```sql
CALL SENTINEL_DB.APP.GENERATE_REPORT('ALRT-DPD-1');
```

### Step 5 — Test Account Evidence
```sql
CALL SENTINEL_DB.APP.GET_ACCOUNT_EVIDENCE('ACCT-000100');
```

### Step 6 — Verify PII Masking
```sql
-- FULL_NAME should show ***MASKED***
SELECT CUSTOMER_ID, FULL_NAME, RISK_RATING
FROM SENTINEL_DB.CORE.DIM_CUSTOMERS LIMIT 5;

-- PAN, Aadhaar, Phone, Email should all show ***MASKED***
SELECT CUSTOMER_ID, FULL_NAME, PAN_NUMBER, AADHAAR_HASH, PHONE, EMAIL
FROM SENTINEL_DB.RAW.CUSTOMERS LIMIT 5;
```

### Step 7 — Verify Fraud Truth is Blocked
```sql
-- This MUST fail with "does not exist or not authorized"
SELECT * FROM SENTINEL_DB.RAW.FRAUD_TRUTH LIMIT 1;
```

### Step 8 — Verify Read-Only (No Write Access)
```sql
-- All of these MUST fail
UPDATE SENTINEL_DB.RISK.ALERTS SET STATUS = 'CLOSED' WHERE 1=1;
DELETE FROM SENTINEL_DB.RISK.ALERTS WHERE 1=1;
DROP TABLE SENTINEL_DB.RISK.ALERTS;
CREATE TABLE SENTINEL_DB.RISK.HACK (ID INT);
ALTER TABLE SENTINEL_DB.RISK.ALERTS ADD COLUMN HACK VARCHAR;
```

### Step 9 — Verify INSERT Only on Audit Tables
```sql
-- This should SUCCEED (audit log)
INSERT INTO SENTINEL_DB.AUDIT.AUDIT_LOG
  (LOG_ID, EVENT_TYPE, ACTOR, ENTITY_TYPE, ENTITY_ID, DETAILS, EVENT_TIMESTAMP)
VALUES ('TEST-JUDGE', 'ACCESS_TEST', CURRENT_USER(), 'TEST', 'TEST', NULL, CURRENT_TIMESTAMP());

-- This should SUCCEED (findings)
INSERT INTO SENTINEL_DB.RISK.FINDINGS
  (FINDING_ID, ALERT_ID, ENTITY_ID, TYPOLOGY, SEVERITY, CLASSIFICATION,
   NARRATIVE, EVIDENCE, POLICY_CITATION, RECOMMENDED_ACTION, CREATED_AT)
VALUES ('FND-TEST', 'ALRT-TEST', 'ACCT-TEST', 'TEST', 'LOW', 'TEST',
        'test finding', NULL, NULL, 'REVIEW', CURRENT_TIMESTAMP());

-- This should FAIL (no INSERT on data tables)
INSERT INTO SENTINEL_DB.RISK.ALERTS (ALERT_ID) VALUES ('HACK');
```

### Step 10 — Test Policy Search
```sql
SELECT PARSE_JSON(SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
  'SENTINEL_DB.DOCS.POLICY_SEARCH',
  '{"query":"What is the minimum LCR ratio?","columns":["CONTENT","DOC_NAME"],"limit":2}'
))['results'] AS results;
```

## Expected Results Summary

| Test                        | Expected                          |
|-----------------------------|-----------------------------------|
| Login                       | Success, role = SENTINEL_JUDGE    |
| Streamlit app               | Loads and works                   |
| AGENT_CHAT                  | Returns answer from agent         |
| GENERATE_REPORT             | Returns JSON report               |
| GET_ACCOUNT_EVIDENCE        | Returns evidence package          |
| PII columns                 | Show `***MASKED***`               |
| RAW.FRAUD_TRUTH             | Access denied                     |
| UPDATE/DELETE/DROP/CREATE/ALTER | Access denied                  |
| INSERT on AUDIT_LOG         | Success                           |
| INSERT on FINDINGS          | Success                           |
| INSERT on any other table   | Access denied                     |
| Policy search               | Returns regulatory content        |

## Resource Monitor

The judge warehouse (`SENTINEL_JUDGE_WH`) has a 10-credit monthly cap via `SENTINEL_JUDGE_RM`.
It notifies at 80% and suspends at 100%. The Streamlit app runs on the shared `SENTINEL_WH` (150-credit cap).
