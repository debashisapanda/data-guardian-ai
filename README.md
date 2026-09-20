# DataGuardian AI

**Autonomous Data Quality & Trust Platform for Snowflake**

*"Find it. Explain it. Fix it. Prove it."*

---

## Problem Statement

Bad data is invisible until it becomes a bad decision. Organizations lose millions annually due to data quality issues that go undetected until they corrupt reports, break pipelines, or mislead executives. Traditional data quality tools require extensive manual configuration and provide no intelligent remediation.

## Solution

DataGuardian AI is an **autonomous agentic data quality platform** built entirely on Snowflake-native capabilities. It acts as an intelligent data quality engineer that:

1. **Discovers** tables and their structure automatically
2. **Scans** data using metadata-driven quality rules across 6 dimensions
3. **Detects** issues with severity classification and business impact analysis
4. **Explains** every problem in business-friendly language using Snowflake Cortex AI
5. **Recommends** safe SQL remediation with risk assessment
6. **Applies** approved fixes with full audit trail
7. **Validates** improvements with before/after health score comparison
8. **Trends** quality over time to demonstrate continuous improvement

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    STREAMLIT IN SNOWFLAKE                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │Executive │ │Discovery │ │AI Report │ │Fix Center│ ...    │
│  │Overview  │ │  & Scan  │ │& Explain │ │& Approve │       │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘       │
│       └─────────────┴────────────┴────────────┘              │
│                          │                                    │
│              ┌───────────┴───────────┐                       │
│              │   QUALITY ENGINE      │                       │
│              │  (Metadata-driven     │                       │
│              │   rule evaluation)    │                       │
│              └───────────┬───────────┘                       │
│                          │                                    │
│       ┌──────────────────┼──────────────────┐               │
│       │                  │                  │               │
│  ┌────┴────┐       ┌────┴────┐       ┌────┴────┐          │
│  │SNOWFLAKE│       │SNOWFLAKE│       │  SCAN   │          │
│  │ CORTEX  │       │SQL/DDL  │       │RESULTS  │          │
│  │  (AI)   │       │(Engine) │       │(History)│          │
│  └─────────┘       └─────────┘       └─────────┘          │
└─────────────────────────────────────────────────────────────┘
```

## Snowflake Components Used

| Component | Usage |
|-----------|-------|
| Streamlit in Snowflake | Full interactive dashboard and AI chat interface |
| Snowflake Cortex (LLM) | AI-powered issue explanations and natural language Q&A |
| Information Schema | Metadata-driven column discovery and type inference |
| SQL Engine | Dynamic quality rule evaluation |
| Tables | Scan results, audit trail, health history, quality rules |
| Stored Procedures | Reusable scan orchestration |
| RBAC | Governance and access control |

## Data Model

### Demo Data (DATA_GUARDIAN_DB.DEMO_DATA)
- **CUSTOMERS** (5,025 rows) - Customer master with intentional quality issues
- **ORDERS** (20,022 rows) - Transaction data with referential integrity violations
- **PRODUCTS** (510 rows) - Product catalog with pricing anomalies

### Quality Engine (DATA_GUARDIAN_DB.QUALITY_ENGINE)
- **QUALITY_RULES** - Rule metadata and configuration
- **SCAN_RESULTS** - Summary of each scan execution
- **SCAN_ISSUES** - Individual issues detected per scan
- **REMEDIATION_LOG** - Full audit trail of fixes applied
- **HEALTH_SCORE_HISTORY** - Historical trending data
- **QUALITY_CONTRACTS** - User-defined natural language rules
- **SCORE_WEIGHTS** - Configurable dimension weights

## Quality Dimensions & Scoring

| Dimension | Weight | What it Measures |
|-----------|--------|-----------------|
| Completeness | 25% | NULL values, missing mandatory fields |
| Uniqueness | 20% | Duplicate records and key violations |
| Validity | 20% | Format violations, range errors, impossible values |
| Consistency | 15% | Whitespace, casing, format inconsistencies |
| Integrity | 15% | Referential integrity, orphan records |
| Freshness | 5% | Data staleness and update recency |

**Health Score = Weighted sum of dimension scores (0-100)**

## Agent Workflow

```
USER → Discover → Profile → Detect → Reason → Prioritize
  → Recommend → Ask Approval → Remediate → Validate → Report
```

## Security & Governance

- **No blind modifications** - All fixes require explicit approval
- **Audit trail** - Every scan and remediation is logged
- **Safe patterns** - Uses staging, MERGE, and controlled updates
- **Risk assessment** - Each fix rated LOW/MEDIUM/HIGH risk
- **Rollback strategy** - Documented for every remediation

## Prerequisites

- A Snowflake account with `ACCOUNTADMIN` (or a role with `CREATE DATABASE`)
- A running warehouse (the script uses whatever warehouse is active)
- Snowsight access for the Streamlit deployment

## Setup

### 1. Create the database and seed demo data

Open a Snowflake worksheet and run the entire [`setup.sql`](setup.sql) script. It will:

- Create `DATA_GUARDIAN_DB` with three schemas (`DEMO_DATA`, `QUALITY_ENGINE`, `APP`)
- Generate ~5,000 customers, 500 products, and 20,000 orders
- Inject intentional quality issues (NULLs, duplicates, invalid emails, negative prices, future dates, orphan keys, etc.)
- Seed 16 quality rules, score weights, and a 6-day health-score trend for the dashboard

The final verification query should return:

| Table | Rows |
|-------|------|
| CUSTOMERS | ~5,025 |
| PRODUCTS | ~510 |
| ORDERS | ~20,022 |
| QUALITY_RULES | 16 |
| SCORE_WEIGHTS | 6 |
| HEALTH_HISTORY | 18 |

### 2. Deploy the Streamlit app

**Option A — Snowsight Workspaces (recommended)**

1. In Snowsight, go to **Projects > Workspaces**
2. Create a new workspace (or use an existing one)
3. Upload these files, preserving the folder structure:
   ```
   data-guardian-ai/
   ├── .streamlit/config.toml
   ├── snowflake.yml
   ├── pyproject.toml
   └── streamlit_app.py
   ```
4. Open `streamlit_app.py` and click **Run** to launch the app

**Option B — Snow CLI**

```bash
cd data-guardian-ai
snow streamlit deploy --replace
```

> **Note:** The app uses `COMPUTE_WH` as the query warehouse and `SYSTEM_COMPUTE_POOL_CPU` as the compute pool (configured in `snowflake.yml`). Adjust these to match your account if needed.

### 3. Run the demo

1. Open the Streamlit app in Snowsight
2. Navigate to the **Competition Demo** page
3. Click **RUN LIVE DEMO**
4. Watch the autonomous quality improvement cycle

## Project Structure

```
data-guardian-ai/
├── .streamlit/
│   └── config.toml           # Theme and UI configuration
├── setup.sql                  # Database DDL + demo data seeding
├── streamlit_app.py           # Main application (816 lines)
├── snowflake.yml              # Snowflake deployment config
├── pyproject.toml             # Python dependencies
├── README.md                  # This file
└── JUDGE_DEMO_SCRIPT.md       # Step-by-step demo walkthrough
```

## Business Value

- **80% reduction** in manual data cleaning effort
- **Real-time** data quality monitoring
- **AI-powered** root cause analysis
- **Governance-compliant** remediation with audit trail
- **Executive-friendly** trust score dashboard
- **Zero external dependencies** - 100% Snowflake-native

## Future Roadmap

- Snowflake Tasks for automated continuous monitoring
- Dynamic Tables for real-time quality materialization
- Streams for change-data-capture quality triggers
- Custom quality contracts via natural language
- Cross-database quality federation
- Slack/Teams notifications for critical issues
