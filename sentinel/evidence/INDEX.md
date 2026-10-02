# Sentinel Hackathon — Evidence Index

Maps each hackathon phase to the CoCo prompts executed, Snowflake objects created, and screenshots in this folder.

---

## Phase 0: Planning & Architecture

**Folder:** `01_planning/`

| Screenshot | What it shows |
|---|---|
| `Screenshot 2026-10-02 161639.png` | CoCo prompt: "I'm building a banking/NBFC fraud, AML and regulatory-reporting copilot on Snowflake. Draft the data model..." → ENTER_PLAN_MODE → proposed schema table (RAW, CORE, RISK, DOCS, APP, AUDIT) |
| `Screenshot 2026-10-02 161709.png` | Plan continuation: ontology (17 entities), signal→evidence→finding workflow, 5-phase build plan, critical files |
| `Screenshot 2026-10-02 161723.png` | EXIT_PLAN_MODE confirmed → WRITE of 4 markdown deliverables: 01_data_model.md (+583 lines), 02_ontology.md (+219), 03_signal_evidence_finding.md (+416), 04_build_plan.md (+485) |
| `Screenshot 2026-10-02 161733.png` | Deliverable summaries: data model (20 tables/DTs across 6 schemas), ontology (Mermaid ER), workflow (DAG), build plan (P0–P5) |
| `Screenshot 2026-10-02 161758.png` | Build plan detail: Dynamic Tables, Cortex Search, Semantic View, Cortex Agent phase breakdown |

**CoCo prompts:**
1. "I'm building a banking/NBFC fraud, AML and regulatory-reporting copilot on Snowflake. Draft the data model, the ontology, the signal→evidence→finding workflow, and a build plan."

**Objects created (files):**
- `sentinel/docs/01_data_model.md` — Full DDL for 20 tables/DTs across 6 schemas
- `sentinel/docs/02_ontology.md` — Entity catalog, relationship map, Mermaid ER, fraud/AML typology
- `sentinel/docs/03_signal_evidence_finding.md` — Three-tier detection workflow with SQL
- `sentinel/docs/04_build_plan.md` — 5-phase build plan with operational checklist

---

## Phase 1: Development — Infrastructure & Data

**Folder:** `02_dev_data/`

| Screenshot | What it shows |
|---|---|
| `01_img.png` | Phase 0 infrastructure: CREATE WAREHOUSE, RESOURCE MONITOR, DATABASE, SCHEMAS SQL execution |
| `02_img.png` | RAW table creation (8 tables: CUSTOMERS, ACCOUNTS, TRANSACTIONS, LOANS, etc.) |
| `03_img.png` | Synthetic data generation procedure (GENERATE_SYNTHETIC_DATA) with planted fraud patterns |
| `04_img.png` | Validation report: row counts (5K customers, 8K accounts, 283K txns, 600 loans), FK integrity — all zero orphans |
| `05_img.png` | Transaction regeneration with realistic log-normal amounts, method-aware channel mapping |
| `06_img.png` | CORE dynamic table creation (DIM_CUSTOMERS, DIM_ACCOUNTS, FACT_TRANSACTIONS, FACT_LOANS, FACT_LIQUIDITY) |
| `07_img.png` | Data quality fix: CASH-on-MOBILE consistency check (319 rows fixed), sample transaction rows |

**CoCo prompts:**
1. "Create a warehouse SENTINEL_WH (X-Small, auto-suspend 60s), resource monitor 150 credits, database SENTINEL_DB, schemas RAW/CORE/RISK/DOCS/APP/AUDIT."
2. "Proceed with Phase 0: create RAW tables, hidden FRAUD_TRUTH, generate synthetic data with fixed seed, plant fraud patterns in 1-2%."
3. "Regenerate background transactions with real randomness — log-normal amounts, correct method/channel combos, counterparties, time patterns."

**Snowflake objects created:**
- `SENTINEL_WH` — X-Small warehouse, auto-suspend 60s
- `SENTINEL_RM` — Resource monitor, 150 credit quota, suspend at 90%
- `SENTINEL_DB` — Database with 6 schemas
- RAW tables: CUSTOMERS, ACCOUNTS, TRANSACTIONS, LOANS, LOAN_REPAYMENTS, LIQUIDITY_POSITIONS, WATCHLISTS, FRAUD_TRUTH
- CORE dynamic tables: DIM_CUSTOMERS, DIM_ACCOUNTS, FACT_TRANSACTIONS, FACT_LOANS, FACT_LIQUIDITY, ACCOUNT_DAILY_FEATURES
- Procedures: RAW.GENERATE_SYNTHETIC_DATA(), RAW.REGENERATE_BACKGROUND_TXNS()

---

## Phase 2: Development — Detection & Search

**Folder:** `03_exec_detection/`

| Screenshot | What it shows |
|---|---|
| `01_img.png` | Data quality audit: CASH-on-MOBILE issue identified and fixed with UPDATE statement, 10 random transaction rows |
| `02_img.png` | Detection rule execution: RISK.RULES catalogue (7 rules), RISK.ALERTS population |
| `03_img.png` | Detection results: alert counts by type and severity, precision/recall against FRAUD_TRUTH |
| `04_img.png` | Hard-negative stress testing: 40 accounts with suspicious-but-legitimate patterns |
| `05_img.png` | Detection improvements: mule chain 48-hour window, DPD_WATCH LOW severity tier |
| `06_img.png` | Improved precision/recall evaluation with hard negatives showing 10 FPs per rule |

**Subfolder:** `03_exec_policy_search/`

| Screenshot | What it shows |
|---|---|
| `00_img.png` | Curated primary citations per rule: RULE-001 Structuring (RBI KYC p.22), RULE-002 Velocity (p.39), RULE-003 Mule Chain (p.61), RULE-004 Round-Tripping (FATF p.129) |
| `01_img.png` | Policy chunk loading: DOCS.CHUNKS table (1,334 rows from 4 PDFs) |
| `02_img.png` | Cortex Search service DOCS.POLICY_SEARCH creation and verification |
| `03_img.png` | RULE_POLICY_LINKS table: 22 rows linking rules to policy citations with IS_PRIMARY flag |
| `04_img.png` | Cortex Search test: 5 policy questions with results showing doc name, page, relevance |

**CoCo prompts:**
1. "Proceed with Phase 1 (CORE layer and alerts): build enriched transactions, RISK.RULES catalogue, alerts table, evaluate detection against FRAUD_TRUTH."
2. "Improve detection rules: mule chain 48-hour rolling window, DPD_WATCH severity tier, 40 hard-negative accounts, re-run detection."
3. "Proceed with Phase 2a (policy documents and Cortex Search): create stage, parse PDFs, chunk text, create search service, link rules, test with 5 questions."
4. "Improve policy retrieval quality: for each rule show linked chunks, run targeted searches, pick best clause, identify missing documents."

**Snowflake objects created:**
- RISK.RULES — 7 detection rules with thresholds and regulation references
- RISK.ALERTS — 414 alerts with score, severity, plain-English reason
- RISK.RULE_POLICY_LINKS — 22 rows linking rules to policy citations
- DOCS.CHUNKS — 1,334 policy text chunks from 4 PDFs
- DOCS.POLICY_SEARCH — Cortex Search service over policy chunks
- Procedure: DOCS.LOAD_CHUNKS()

---

## Phase 3: Execution — Semantic View, Agent & App

**Subfolder:** `05_exec_app/`

| Screenshot | What it shows |
|---|---|
| `00_img.png` | Streamlit app deployed: SENTINEL at `https://app.snowflake.com/HFTPCWG-PH93773/#/streamlit-apps/SENTINEL_DB.APP.SENTINEL` with 6 pages listed (Home, Copilot, Alert Queue, Case View, Dashboard, Audit) |

**CoCo prompts:**
1. "Proceed with Phase 2b: create semantic view APP.SENTINEL_SV with 7 tables, 5 relationships, 12 VQRs, test with 20 NL questions."
2. "Proceed with the Cortex Agent: create GET_ACCOUNT_EVIDENCE, GENERATE_REPORT, LOG_FINDING procedures; create SENTINEL_AGENT with semantic view + search + procedures; test with 10 questions."
3. "Build and deploy a Streamlit in Snowflake app called SENTINEL: Copilot, Alert Queue, Case View, Dashboard, Audit pages."
4. "Add governance: create roles FRAUD_ANALYST, COMPLIANCE_OFFICER, AUDITOR; masking policies; row access policy; audit logging."
5. "Create 30 test cases, run through agent, record results, fix failures, re-run."
6. "Create a reusable skill aml-structuring-detector."

**Snowflake objects created:**
- APP.SENTINEL_SV — Semantic view with 7 tables, 5 relationships, 12 VQRs
- APP.SENTINEL_AGENT — Cortex Agent with 5 tools (analyst, policy_search, 3 procedures)
- APP.GET_ACCOUNT_EVIDENCE — Returns account evidence as JSON
- APP.GENERATE_REPORT — LLM-narrated investigation report with number validation
- APP.LOG_FINDING — Writes to FINDINGS + AUDIT_LOG
- APP.AGENT_CHAT — Wrapper that logs every agent call to AUDIT_LOG
- APP.MASK_PII_STRING — Masking policy for PII columns
- APP.RAP_CITY_FILTER — Row access policy for city-based filtering
- RISK.FINDINGS — Investigation findings table
- RISK.ANALYST_CITY_ASSIGNMENTS — Role→city mapping
- AUDIT.AUDIT_LOG — Full audit trail
- AUDIT.TEST_RESULTS — 30-case evaluation results
- SENTINEL (Streamlit) — 5-page app deployed to SiS
- Roles: FRAUD_ANALYST, COMPLIANCE_OFFICER, AUDITOR

**Local files created:**
- `sentinel_app/` — Streamlit project (snowflake.yml, streamlit_app.py, 5 page files)
- `cortex_project/SENTINEL_SV.sv.yaml` — Semantic view YAML
- `tests/test_questions.csv` — 30 evaluation test cases
- `skills/aml-structuring-detector/SKILL.md` — Reusable detection skill

---

## Phase 0 (meta): CoCo Installation

**Folder:** `00_installed_successfully_and_working/`

| Screenshot | What it shows |
|---|---|
| `Screenshot 2026-10-02 160150.png` | Cortex Code v1.1.87 startup in VS Code terminal, connected to PH93773/HFTPCWG-PH93773, showing 00_setup.sql with infrastructure DDL and cortex-code-guide skill loaded |

---

## Summary of All Snowflake Objects

| Schema | Objects |
|---|---|
| RAW | CUSTOMERS, ACCOUNTS, TRANSACTIONS, LOANS, LOAN_REPAYMENTS, LIQUIDITY_POSITIONS, WATCHLISTS, FRAUD_TRUTH, GENERATE_SYNTHETIC_DATA(), REGENERATE_BACKGROUND_TXNS() |
| CORE | DIM_CUSTOMERS, DIM_ACCOUNTS, FACT_TRANSACTIONS, FACT_LOANS, FACT_LIQUIDITY, ACCOUNT_DAILY_FEATURES |
| RISK | RULES, ALERTS, RULE_POLICY_LINKS, FINDINGS, CASES, ANALYST_CITY_ASSIGNMENTS |
| DOCS | CHUNKS, POLICY_SEARCH (Cortex Search service), LOAD_CHUNKS() |
| APP | SENTINEL_SV (semantic view), SENTINEL_AGENT (Cortex Agent), GET_ACCOUNT_EVIDENCE(), GENERATE_REPORT(), LOG_FINDING(), AGENT_CHAT(), MASK_PII_STRING (masking policy), RAP_CITY_FILTER (row access policy), SENTINEL (Streamlit app) |
| AUDIT | AUDIT_LOG, TEST_RESULTS |
