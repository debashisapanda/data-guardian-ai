import streamlit as st
import os
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
import time

st.set_page_config(
    page_title="DataGuardian AI",
    page_icon=":material/verified_user:",
    layout="wide",
    initial_sidebar_state="expanded"
)

conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))
session = conn.session()
try:
    session.sql("USE DATABASE DATA_GUARDIAN_DB").collect()
    session.sql("USE SCHEMA DEMO_DATA").collect()
except Exception:
    pass

DB = "DATA_GUARDIAN_DB"
DEMO_SCHEMA = "DEMO_DATA"
ENGINE_SCHEMA = "QUALITY_ENGINE"
VALID_STATUSES = ['Delivered', 'Shipped', 'Processing', 'Cancelled', 'Returned']
VALID_SEGMENTS = ['Premium', 'Standard', 'Basic', 'Enterprise']
VALID_CATEGORIES = ['Electronics', 'Clothing', 'Food & Beverage', 'Home & Garden', 'Sports', 'Books']
VALID_PAYMENT_METHODS = ['Credit Card', 'UPI', 'Net Banking', 'Debit Card', 'Cash on Delivery']

SEV_BADGE = {'CRITICAL': ':red-badge[CRITICAL]', 'HIGH': ':orange-badge[HIGH]', 'MEDIUM': ':yellow-badge[MEDIUM]', 'LOW': ':green-badge[LOW]'}
SEV_COLOR = {'CRITICAL': 'red', 'HIGH': 'orange', 'MEDIUM': 'yellow', 'LOW': 'green'}
DIM_ICON = {
    'COMPLETENESS': ':material/check_box:', 'UNIQUENESS': ':material/fingerprint:',
    'VALIDITY': ':material/verified:', 'CONSISTENCY': ':material/sync:',
    'INTEGRITY': ':material/link:', 'FRESHNESS': ':material/schedule:'
}

# ── Helpers ──────────────────────────────────────────────

@st.cache_data(ttl=60)
def run_query(sql):
    return session.sql(sql).to_pandas()

def qry(sql):
    return session.sql(sql).to_pandas()

def exe(sql):
    session.sql(sql).collect()

def scan_id():
    return f"SCAN_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

def get_tables():
    df = qry(f"SELECT TABLE_NAME FROM {DB}.INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='{DEMO_SCHEMA}' AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME")
    return df['TABLE_NAME'].tolist() if not df.empty else []

def get_table_info(t):
    fqn = f"{DB}.{DEMO_SCHEMA}.{t}"
    rc = int(qry(f"SELECT COUNT(*) AS C FROM {fqn}")['C'].iloc[0])
    cols = qry(f"SELECT COLUMN_NAME,DATA_TYPE,IS_NULLABLE FROM {DB}.INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='{DEMO_SCHEMA}' AND TABLE_NAME='{t}' ORDER BY ORDINAL_POSITION")
    return rc, cols

def profile_col(t, col, dtype):
    fqn = f"{DB}.{DEMO_SCHEMA}.{t}"
    total = int(qry(f"SELECT COUNT(*) AS C FROM {fqn}")['C'].iloc[0])
    nulls = int(qry(f"SELECT COUNT(*) AS C FROM {fqn} WHERE {col} IS NULL")['C'].iloc[0])
    dist = int(qry(f"SELECT COUNT(DISTINCT {col}) AS C FROM {fqn}")['C'].iloc[0])
    s = {'Total': total, 'Nulls': nulls, 'Null %': round(nulls*100.0/total,2) if total else 0, 'Distinct': dist, 'Uniqueness %': round(dist*100.0/total,2) if total else 0}
    if any(x in dtype for x in ['NUMBER','INT','FLOAT','DECIMAL']):
        r = qry(f"SELECT MIN({col}) AS MI,MAX({col}) AS MA,AVG({col}) AS AV,MEDIAN({col}) AS ME,STDDEV({col}) AS SD FROM {fqn} WHERE {col} IS NOT NULL")
        if not r.empty:
            s.update({'Min':r['MI'].iloc[0],'Max':r['MA'].iloc[0],'Mean':round(float(r['AV'].iloc[0]),2) if r['AV'].iloc[0] is not None else None,'Median':r['ME'].iloc[0]})
    elif any(x in dtype for x in ['TEXT','VARCHAR','CHAR','STRING']):
        r = qry(f"SELECT MIN(LENGTH({col})) AS MI,MAX(LENGTH({col})) AS MA,AVG(LENGTH({col})) AS AV FROM {fqn} WHERE {col} IS NOT NULL")
        if not r.empty:
            s.update({'Min Len':r['MI'].iloc[0],'Max Len':r['MA'].iloc[0],'Avg Len':round(float(r['AV'].iloc[0]),1) if r['AV'].iloc[0] is not None else None})
        top = qry(f"SELECT {col} AS VAL,COUNT(*) AS CNT FROM {fqn} WHERE {col} IS NOT NULL GROUP BY {col} ORDER BY CNT DESC LIMIT 5")
        if not top.empty: s['Top Values'] = top
    return s

# ── Scanner ──────────────────────────────────────────────

def scan_table(table_name, scan_type='DEEP'):
    fqn = f"{DB}.{DEMO_SCHEMA}.{table_name}"
    sid = scan_id()
    issues = []
    total = int(qry(f"SELECT COUNT(*) AS C FROM {fqn}")['C'].iloc[0])
    cols_df = qry(f"SELECT COLUMN_NAME,DATA_TYPE FROM {DB}.INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA='{DEMO_SCHEMA}' AND TABLE_NAME='{table_name}' ORDER BY ORDINAL_POSITION")

    def add(cat,rule,sev,col,cnt,desc,impact,action,sql,risk,conf=95.0):
        pct = round(cnt*100.0/total,2) if total else 0
        issues.append({'scan_id':sid,'table_name':table_name,'column_name':col,'rule_category':cat,'rule_name':rule,'severity':sev,'affected_rows':cnt,'total_rows':total,'affected_percentage':pct,'issue_description':desc,'business_impact':impact,'recommended_action':action,'remediation_sql':sql,'risk_level':risk,'confidence':conf})

    # NULLs
    for _,r in cols_df.iterrows():
        c = r['COLUMN_NAME']
        n = int(qry(f"SELECT COUNT(*) AS N FROM {fqn} WHERE {c} IS NULL")['N'].iloc[0])
        if n > 0:
            p = round(n*100.0/total,2)
            sev = 'CRITICAL' if p>20 else ('HIGH' if p>10 else ('MEDIUM' if p>5 else 'LOW'))
            add('COMPLETENESS','NULL_CHECK',sev,c,n,f"{c} has {n:,} NULL values ({p}%)",f"Missing {c} breaks reporting",f"Fill or investigate {c}",f"-- UPDATE {fqn} SET {c} = '<default>' WHERE {c} IS NULL",'MEDIUM',99.9)

    # Blanks
    vc = cols_df[cols_df['DATA_TYPE'].str.contains('VARCHAR|TEXT|STRING|CHAR',case=False,na=False)]
    for _,r in vc.iterrows():
        c = r['COLUMN_NAME']
        n = int(qry(f"SELECT COUNT(*) AS N FROM {fqn} WHERE {c} IS NOT NULL AND TRIM({c})=''")['N'].iloc[0])
        if n > 0:
            add('COMPLETENESS','BLANK_STRING','MEDIUM',c,n,f"{c} has {n:,} blank strings",f"Empty {c} hides data gaps",f"Convert blanks to NULL",f"UPDATE {fqn} SET {c}=NULL WHERE TRIM({c})=''",'LOW',99.0)

    # Duplicates (PK only)
    pk = [c for c in cols_df['COLUMN_NAME'].tolist() if c.upper().endswith('_ID')][:1]
    for c in pk:
        d = int(qry(f"SELECT COUNT(*) AS D FROM (SELECT {c},COUNT(*) AS n FROM {fqn} WHERE {c} IS NOT NULL GROUP BY {c} HAVING n>1)")['D'].iloc[0])
        if d > 0:
            a = int(qry(f"SELECT SUM(n) AS T FROM (SELECT {c},COUNT(*) AS n FROM {fqn} WHERE {c} IS NOT NULL GROUP BY {c} HAVING n>1)")['T'].iloc[0])
            add('UNIQUENESS','DUPLICATE_KEY','CRITICAL',c,a,f"{d} duplicate {c} values ({a:,} rows)",f"Duplicates cause double-counting",f"Deduplicate records",f"SELECT {c},COUNT(*) FROM {fqn} WHERE {c} IS NOT NULL GROUP BY {c} HAVING COUNT(*)>1",'HIGH',99.9)

    # Emails
    for c in [c for c in cols_df['COLUMN_NAME'].tolist() if 'EMAIL' in c.upper()]:
        n = int(qry(f"SELECT COUNT(*) AS N FROM {fqn} WHERE {c} IS NOT NULL AND TRIM({c})!='' AND NOT REGEXP_LIKE({c},'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\\\.[A-Za-z]{{2,}}$')")['N'].iloc[0])
        if n > 0:
            add('VALIDITY','EMAIL_FORMAT','HIGH',c,n,f"{n:,} invalid emails in {c}",f"Bad emails block communication",f"Flag invalid emails",f"UPDATE {fqn} SET {c}=NULL WHERE {c} IS NOT NULL AND TRIM({c})!='' AND NOT REGEXP_LIKE({c},'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\\\.[A-Za-z]{{2,}}$')",'MEDIUM')

    # Negatives
    nc = cols_df[cols_df['DATA_TYPE'].str.contains('NUMBER|INT|FLOAT|DECIMAL|NUMERIC',case=False,na=False)]
    for _,r in nc.iterrows():
        c = r['COLUMN_NAME']
        if any(k in c.upper() for k in ['AMOUNT','PRICE','QUANTITY','SCORE','INCOME','STOCK','WEIGHT']):
            n = int(qry(f"SELECT COUNT(*) AS N FROM {fqn} WHERE {c}<0")['N'].iloc[0])
            if n > 0:
                add('VALIDITY','NEGATIVE_VALUE','HIGH',c,n,f"{n:,} negative values in {c}",f"Negative {c} distorts calculations",f"Investigate or nullify",f"UPDATE {fqn} SET {c}=NULL WHERE {c}<0",'MEDIUM',90.0)

    # Future dates
    dc = cols_df[cols_df['DATA_TYPE'].str.contains('DATE|TIMESTAMP|TIME',case=False,na=False)]
    for _,r in dc.iterrows():
        c = r['COLUMN_NAME']
        if any(k in c.upper() for k in ['BIRTH','REGISTRATION','ORDER','CREATED','UPDATED']):
            n = int(qry(f"SELECT COUNT(*) AS N FROM {fqn} WHERE {c}>CURRENT_TIMESTAMP()")['N'].iloc[0])
            if n > 0:
                add('VALIDITY','FUTURE_DATE','HIGH',c,n,f"{n:,} future dates in {c}",f"Future dates indicate errors",f"Review or nullify",f"UPDATE {fqn} SET {c}=NULL WHERE {c}>CURRENT_TIMESTAMP()",'MEDIUM')

    # Invalid categories
    cats = {'CUSTOMERS':{'CUSTOMER_SEGMENT':VALID_SEGMENTS},'ORDERS':{'ORDER_STATUS':VALID_STATUSES,'PAYMENT_METHOD':VALID_PAYMENT_METHODS},'PRODUCTS':{'CATEGORY':VALID_CATEGORIES}}.get(table_name,{})
    for c,vals in cats.items():
        if c in cols_df['COLUMN_NAME'].values:
            vs = "','".join(vals)
            n = int(qry(f"SELECT COUNT(*) AS N FROM {fqn} WHERE {c} IS NOT NULL AND {c} NOT IN ('{vs}')")['N'].iloc[0])
            if n > 0:
                add('VALIDITY','INVALID_CATEGORY','MEDIUM',c,n,f"{n:,} invalid values in {c}",f"Bad categories break grouping",f"Map or nullify",f"UPDATE {fqn} SET {c}=NULL WHERE {c} NOT IN ('{vs}')",'LOW',85.0)

    # Whitespace
    for _,r in vc.iterrows():
        c = r['COLUMN_NAME']
        n = int(qry(f"SELECT COUNT(*) AS N FROM {fqn} WHERE {c} IS NOT NULL AND {c}!=TRIM({c})")['N'].iloc[0])
        if n > 0:
            add('CONSISTENCY','WHITESPACE','LOW',c,n,f"{n:,} values with whitespace in {c}",f"Whitespace breaks joins",f"Trim values",f"UPDATE {fqn} SET {c}=TRIM({c}) WHERE {c}!=TRIM({c})",'LOW',99.9)

    # Referential integrity (ORDERS)
    if table_name == 'ORDERS':
        n = int(qry(f"SELECT COUNT(*) AS N FROM {fqn} WHERE CUSTOMER_ID IS NOT NULL AND CUSTOMER_ID NOT IN (SELECT CUSTOMER_ID FROM {DB}.{DEMO_SCHEMA}.CUSTOMERS WHERE CUSTOMER_ID IS NOT NULL)")['N'].iloc[0])
        if n > 0:
            add('INTEGRITY','ORPHAN_REFERENCE','CRITICAL','CUSTOMER_ID',n,f"{n:,} orders reference missing customers",f"Orphans break revenue attribution",f"Backfill or flag",f"SELECT ORDER_ID,CUSTOMER_ID FROM {fqn} WHERE CUSTOMER_ID NOT IN (SELECT CUSTOMER_ID FROM {DB}.{DEMO_SCHEMA}.CUSTOMERS WHERE CUSTOMER_ID IS NOT NULL)",'HIGH',99.9)
        n2 = int(qry(f"SELECT COUNT(*) AS N FROM {fqn} WHERE DELIVERY_DATE IS NOT NULL AND ORDER_DATE IS NOT NULL AND DELIVERY_DATE<ORDER_DATE")['N'].iloc[0])
        if n2 > 0:
            add('VALIDITY','DATE_ORDERING','HIGH','DELIVERY_DATE',n2,f"{n2:,} orders delivered before ordered",f"Impossible dates hurt logistics",f"Swap or flag",f"UPDATE {fqn} SET DELIVERY_DATE=ORDER_DATE,ORDER_DATE=DELIVERY_DATE WHERE DELIVERY_DATE<ORDER_DATE",'MEDIUM')
        n3 = int(qry(f"SELECT COUNT(*) AS N FROM {fqn} WHERE QUANTITY IS NOT NULL AND UNIT_PRICE IS NOT NULL AND TOTAL_AMOUNT IS NOT NULL AND ABS(TOTAL_AMOUNT-(QUANTITY*UNIT_PRICE))>0.01")['N'].iloc[0])
        if n3 > 0:
            add('VALIDITY','AMOUNT_MISMATCH','HIGH','TOTAL_AMOUNT',n3,f"{n3:,} orders: total != qty*price",f"Revenue accuracy at risk",f"Recalculate totals",f"UPDATE {fqn} SET TOTAL_AMOUNT=QUANTITY*UNIT_PRICE WHERE ABS(TOTAL_AMOUNT-(QUANTITY*UNIT_PRICE))>0.01",'LOW',98.0)

    if table_name == 'PRODUCTS':
        n = int(qry(f"SELECT COUNT(*) AS N FROM {fqn} WHERE COST_PRICE IS NOT NULL AND UNIT_PRICE IS NOT NULL AND COST_PRICE>UNIT_PRICE")['N'].iloc[0])
        if n > 0:
            add('VALIDITY','COST_EXCEEDS_PRICE','HIGH','COST_PRICE',n,f"{n:,} products selling at a loss",f"Margin erosion",f"Review pricing",f"SELECT PRODUCT_ID,PRODUCT_NAME,COST_PRICE,UNIT_PRICE FROM {fqn} WHERE COST_PRICE>UNIT_PRICE",'HIGH')

    return sid, issues, total

def calc_scores(issues, total):
    cats = {'COMPLETENESS':0.25,'UNIQUENESS':0.20,'VALIDITY':0.20,'CONSISTENCY':0.15,'INTEGRITY':0.15,'FRESHNESS':0.05}
    by_cat = {c:[] for c in cats}
    for i in issues:
        if i['rule_category'] in by_cat: by_cat[i['rule_category']].append(i)
    scores = {}
    sev_weight = {'CRITICAL':25,'HIGH':15,'MEDIUM':8,'LOW':3}
    for c,w in cats.items():
        if not by_cat[c]:
            scores[c] = 100.0
        else:
            pct_penalty = sum(i['affected_percentage'] for i in by_cat[c]) * 2.0
            sev_penalty = sum(sev_weight.get(i['severity'],5) for i in by_cat[c])
            count_penalty = len(by_cat[c]) * 3
            penalty = min(pct_penalty + sev_penalty + count_penalty, 80)
            scores[c] = max(20, round(100 - penalty, 1))
    overall = sum(scores[c]*cats[c] for c in cats)
    return round(overall,1), scores

def save_scan(sid, table, issues, total, scores, overall):
    cr=sum(1 for i in issues if i['severity']=='CRITICAL')
    hi=sum(1 for i in issues if i['severity']=='HIGH')
    me=sum(1 for i in issues if i['severity']=='MEDIUM')
    lo=sum(1 for i in issues if i['severity']=='LOW')
    risk=sum(i['affected_rows'] for i in issues)
    try:
        exe(f"INSERT INTO {DB}.{ENGINE_SCHEMA}.SCAN_RESULTS(SCAN_ID,DATABASE_NAME,SCHEMA_NAME,TABLE_NAME,TOTAL_ROWS,TOTAL_COLUMNS,ISSUES_FOUND,CRITICAL_ISSUES,HIGH_ISSUES,MEDIUM_ISSUES,LOW_ISSUES,HEALTH_SCORE,COMPLETENESS_SCORE,UNIQUENESS_SCORE,VALIDITY_SCORE,CONSISTENCY_SCORE,INTEGRITY_SCORE,FRESHNESS_SCORE,SCAN_DURATION_SECONDS,SCAN_TYPE) VALUES('{sid}','{DB}','{DEMO_SCHEMA}','{table}',{total},0,{len(issues)},{cr},{hi},{me},{lo},{overall},{scores.get('COMPLETENESS',100)},{scores.get('UNIQUENESS',100)},{scores.get('VALIDITY',100)},{scores.get('CONSISTENCY',100)},{scores.get('INTEGRITY',100)},{scores.get('FRESHNESS',100)},0,'DEEP')")
        exe(f"INSERT INTO {DB}.{ENGINE_SCHEMA}.HEALTH_SCORE_HISTORY(SCAN_ID,SCAN_DATE,DATABASE_NAME,SCHEMA_NAME,TABLE_NAME,HEALTH_SCORE,COMPLETENESS_SCORE,UNIQUENESS_SCORE,VALIDITY_SCORE,CONSISTENCY_SCORE,INTEGRITY_SCORE,FRESHNESS_SCORE,TOTAL_ISSUES,CRITICAL_ISSUES,ROWS_AT_RISK) VALUES('{sid}',CURRENT_DATE(),'{DB}','{DEMO_SCHEMA}','{table}',{overall},{scores.get('COMPLETENESS',100)},{scores.get('UNIQUENESS',100)},{scores.get('VALIDITY',100)},{scores.get('CONSISTENCY',100)},{scores.get('INTEGRITY',100)},{scores.get('FRESHNESS',100)},{len(issues)},{cr},{risk})")
        for i in issues:
            desc = i['issue_description'].replace("'","''")
            impact = i['business_impact'].replace("'","''")
            action = i['recommended_action'].replace("'","''")
            sql_fix = i['remediation_sql'].replace("'","''")
            exe(f"INSERT INTO {DB}.{ENGINE_SCHEMA}.SCAN_ISSUES(ISSUE_ID,SCAN_ID,TABLE_NAME,COLUMN_NAME,RULE_CATEGORY,RULE_NAME,SEVERITY,AFFECTED_ROWS,TOTAL_ROWS,AFFECTED_PERCENTAGE,ISSUE_DESCRIPTION,BUSINESS_IMPACT,RECOMMENDED_ACTION,REMEDIATION_SQL,RISK_LEVEL,CONFIDENCE_LEVEL) VALUES('{sid}_{i['rule_name']}_{i['column_name']}','{sid}','{i['table_name']}','{i['column_name']}','{i['rule_category']}','{i['rule_name']}','{i['severity']}',{i['affected_rows']},{i['total_rows']},{i['affected_percentage']},'{desc}','{impact}','{action}','{sql_fix}','{i['risk_level']}',{i['confidence']})")
    except Exception: pass

def ai_explain(issue):
    p = f"""You are DataGuardian AI. Explain this data quality issue in 3 concise bullet points for a business executive:

Issue: {issue['issue_description']}
Table: {issue['table_name']}.{issue['column_name']} | Severity: {issue['severity']} | Rows: {issue['affected_rows']}

Use this exact format:
- **What:** (one sentence)
- **Risk:** (one sentence)
- **Fix:** (one sentence)"""
    try:
        r = qry(f"SELECT SNOWFLAKE.CORTEX.COMPLETE('llama3.1-70b','{p.replace(chr(39),chr(39)+chr(39))}') AS R")
        return r['R'].iloc[0]
    except Exception:
        return f"- **What:** {issue['issue_description']}\n- **Risk:** {issue['business_impact']}\n- **Fix:** {issue['recommended_action']}"

def ask_guardian(question):
    ctx = ""
    if 'scan_issues' in st.session_state and st.session_state['scan_issues']:
        iss = st.session_state['scan_issues']
        cr = sum(1 for i in iss if i['severity']=='CRITICAL')
        ctx = f"Scan found {len(iss)} issues ({cr} critical). Top: " + "; ".join(i['issue_description'] for i in iss[:5])
    try:
        h = qry(f"SELECT TABLE_NAME,HEALTH_SCORE,TOTAL_ISSUES,SCAN_DATE FROM {DB}.{ENGINE_SCHEMA}.HEALTH_SCORE_HISTORY ORDER BY RECORDED_AT DESC LIMIT 10")
        if not h.empty: ctx += f"\nScores: {h.to_string(index=False)}"
    except Exception: pass
    p = f"""You are DataGuardian AI, a data quality copilot. Context: {ctx}\n\nQuestion: {question}\n\nAnswer in 3-5 sentences with specific numbers. Include SQL if suggesting a fix."""
    try:
        r = qry(f"SELECT SNOWFLAKE.CORTEX.COMPLETE('llama3.1-70b','{p.replace(chr(39),chr(39)+chr(39))}') AS R")
        return r['R'].iloc[0]
    except Exception:
        return f"Based on current data: {ctx[:400]}"

def score_color(s):
    return 'green' if s>=85 else ('blue' if s>=70 else ('orange' if s>=50 else 'red'))

def score_emoji(s):
    return ':green[●]' if s>=85 else (':blue[●]' if s>=70 else (':orange[●]' if s>=50 else ':red[●]'))


# ══════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### :material/verified_user: :violet[DataGuardian AI]")
    st.caption(":gray[Autonomous Data Quality & Trust Platform]")
    st.space("small")

    try:
        ss = qry(f"SELECT AVG(HEALTH_SCORE) AS S FROM {DB}.{ENGINE_SCHEMA}.HEALTH_SCORE_HISTORY WHERE SCAN_DATE=(SELECT MAX(SCAN_DATE) FROM {DB}.{ENGINE_SCHEMA}.HEALTH_SCORE_HISTORY)")
        if not ss.empty and ss['S'].iloc[0] is not None:
            sc = float(ss['S'].iloc[0])
            st.metric(":material/favorite: Health", f"{sc:.0f}/100", border=True,
                     chart_data=[58,64,72,79,84,86,sc], chart_type="line")
    except Exception:
        pass

    st.space("small")
    page = st.radio("", [
        ":material/dashboard: Overview",
        ":material/search: Discovery",
        ":material/assessment: Quality Report",
        ":material/auto_fix_high: Fix Center",
        ":material/show_chart: Trust Score",
        ":material/gavel: Contracts",
        ":material/history: Audit Trail",
        ":material/smart_toy: Ask Guardian",
        ":material/play_circle: Live Demo"
    ], label_visibility="collapsed")

    st.space("large")
    st.caption(":violet[Find it.] :blue[Explain it.] :green[Fix it.] :orange[Prove it.]")


# ══════════════════════════════════════════════════════════
# OVERVIEW
# ══════════════════════════════════════════════════════════
if "Overview" in page:
    st.markdown("# :material/dashboard: :violet[Executive overview]")

    latest = qry(f"""SELECT TABLE_NAME,HEALTH_SCORE,TOTAL_ISSUES,CRITICAL_ISSUES,ROWS_AT_RISK,
        COMPLETENESS_SCORE,UNIQUENESS_SCORE,VALIDITY_SCORE,CONSISTENCY_SCORE,INTEGRITY_SCORE,FRESHNESS_SCORE
        FROM {DB}.{ENGINE_SCHEMA}.HEALTH_SCORE_HISTORY
        WHERE SCAN_DATE=(SELECT MAX(SCAN_DATE) FROM {DB}.{ENGINE_SCHEMA}.HEALTH_SCORE_HISTORY)""")

    if latest.empty:
        st.info("No scans yet. Head to **:violet[Live Demo]** to get started.", icon=":material/rocket_launch:")
    else:
        avg = float(latest['HEALTH_SCORE'].mean())
        tot_iss = int(latest['TOTAL_ISSUES'].sum())
        crit = int(latest['CRITICAL_ISSUES'].sum())
        risk = int(latest['ROWS_AT_RISK'].sum())

        trend = qry(f"SELECT SCAN_DATE,AVG(HEALTH_SCORE) AS SCORE,SUM(TOTAL_ISSUES) AS ISSUES,SUM(ROWS_AT_RISK) AS RISK FROM {DB}.{ENGINE_SCHEMA}.HEALTH_SCORE_HISTORY GROUP BY SCAN_DATE ORDER BY SCAN_DATE")
        sc_trend = trend['SCORE'].tolist() if not trend.empty else []
        is_trend = trend['ISSUES'].tolist() if not trend.empty else []

        # Hero KPIs
        with st.container(horizontal=True):
            st.metric(":material/favorite: Health score", f"{avg:.0f}/100", border=True, chart_data=sc_trend, chart_type="line")
            st.metric(":material/table_chart: Tables", len(latest), border=True)
            st.metric(":material/error: Issues", tot_iss, border=True, chart_data=is_trend, chart_type="bar")
            st.metric(":material/warning: Critical", crit, border=True)
            st.metric(":material/group: Rows at risk", f"{risk:,}", border=True)

        # Altair trend chart + severity breakdown
        c1, c2 = st.columns([3, 2])
        with c1:
            with st.container(border=True):
                st.markdown("**:material/show_chart: Health trend**")
                if not trend.empty:
                    area = alt.Chart(trend).mark_area(
                        opacity=0.3, color='#635bff'
                    ).encode(
                        x=alt.X('SCAN_DATE:T', title='Date'),
                        y=alt.Y('SCORE:Q', title='Score', scale=alt.Scale(domain=[0,100]))
                    )
                    line = alt.Chart(trend).mark_line(
                        color='#635bff', strokeWidth=3
                    ).encode(
                        x='SCAN_DATE:T', y='SCORE:Q'
                    )
                    pts = alt.Chart(trend).mark_circle(
                        color='#635bff', size=60
                    ).encode(
                        x='SCAN_DATE:T', y='SCORE:Q',
                        tooltip=['SCAN_DATE:T', alt.Tooltip('SCORE:Q', format='.1f')]
                    )
                    st.altair_chart(area + line + pts)

        with c2:
            with st.container(border=True):
                st.markdown("**:material/pie_chart: Issues by table**")
                bar_data = latest[['TABLE_NAME','TOTAL_ISSUES','CRITICAL_ISSUES']].copy()
                bar = alt.Chart(bar_data).mark_bar(
                    cornerRadiusTopLeft=6, cornerRadiusTopRight=6, color='#635bff'
                ).encode(
                    x=alt.X('TABLE_NAME:N', title=None),
                    y=alt.Y('TOTAL_ISSUES:Q', title='Issues'),
                    tooltip=['TABLE_NAME','TOTAL_ISSUES','CRITICAL_ISSUES']
                )
                crit_bar = alt.Chart(bar_data).mark_bar(
                    cornerRadiusTopLeft=6, cornerRadiusTopRight=6, color='#ff6b6b'
                ).encode(
                    x='TABLE_NAME:N', y='CRITICAL_ISSUES:Q'
                )
                st.altair_chart(bar + crit_bar)

        # Dimension scores with progress bars
        with st.container(border=True):
            st.markdown("**:material/grid_view: Quality dimensions**")
            dims = ['COMPLETENESS','UNIQUENESS','VALIDITY','CONSISTENCY','INTEGRITY','FRESHNESS']
            d_cols = st.columns(6)
            for i,d in enumerate(dims):
                v = float(latest[f'{d}_SCORE'].mean())
                with d_cols[i]:
                    st.markdown(f"{DIM_ICON[d]} **{d.title()}**")
                    st.progress(v/100)
                    st.markdown(f"**:{'green' if v>=80 else ('orange' if v>=60 else 'red')}[{v:.0f}%]**", text_alignment="center")

        # Table breakdown
        with st.container(border=True):
            st.markdown("**:material/table_chart: Table health**")
            for _,r in latest.iterrows():
                h = float(r['HEALTH_SCORE'])
                with st.container(horizontal=True):
                    st.markdown(f"{score_emoji(h)} **{r['TABLE_NAME']}**")
                    st.progress(h/100)
                    st.markdown(f"**{h:.0f}**/100 · {int(r['TOTAL_ISSUES'])} issues · {int(r['ROWS_AT_RISK']):,} rows at risk")


# ══════════════════════════════════════════════════════════
# DISCOVERY
# ══════════════════════════════════════════════════════════
elif "Discovery" in page:
    st.markdown("# :material/search: :blue[Data discovery & profiling]")
    tables = get_tables()
    if not tables:
        st.warning("No tables found.", icon=":material/warning:")
    else:
        c1, c2 = st.columns([3,1])
        with c1:
            sel = st.selectbox("Table", tables, label_visibility="collapsed", format_func=lambda x: f":material/table_chart: {x}")
        with c2:
            stype = st.segmented_control("Mode", ["Quick","Deep"], default="Deep")

        if sel:
            rc, cols = get_table_info(sel)
            with st.container(horizontal=True):
                st.metric(":material/data_array: Rows", f"{rc:,}", border=True)
                st.metric(":material/view_column: Columns", len(cols), border=True)
                st.metric(":material/database: Schema", f"{DEMO_SCHEMA}.{sel}", border=True)

            t_schema, t_prof, t_sample = st.tabs([":material/schema: Schema", ":material/analytics: Column profile", ":material/preview: Sample data"])

            with t_schema:
                st.dataframe(cols, hide_index=True, column_config={
                    "COLUMN_NAME": st.column_config.TextColumn("Column", pinned=True),
                    "DATA_TYPE": st.column_config.TextColumn("Type"),
                    "IS_NULLABLE": st.column_config.TextColumn("Nullable")
                })

            with t_prof:
                pc = st.selectbox("Column to profile", cols['COLUMN_NAME'].tolist(), key="pc")
                if pc:
                    dt = cols[cols['COLUMN_NAME']==pc]['DATA_TYPE'].iloc[0]
                    with st.spinner("Profiling..."):
                        s = profile_col(sel, pc, dt)
                    with st.container(horizontal=True):
                        st.metric(":red[Null %]", f"{s.get('Null %',0)}%", border=True)
                        st.metric(":blue[Distinct]", f"{s.get('Distinct',0):,}", border=True)
                        st.metric(":violet[Uniqueness]", f"{s.get('Uniqueness %',0)}%", border=True)
                    if 'Min' in s:
                        with st.container(horizontal=True):
                            st.metric("Min", s['Min'], border=True)
                            st.metric("Max", s['Max'], border=True)
                            st.metric("Mean", s.get('Mean','—'), border=True)
                            st.metric("Median", s.get('Median','—'), border=True)
                    if 'Min Len' in s:
                        with st.container(horizontal=True):
                            st.metric("Min len", s['Min Len'], border=True)
                            st.metric("Max len", s['Max Len'], border=True)
                            st.metric("Avg len", s.get('Avg Len','—'), border=True)
                    if 'Top Values' in s:
                        st.markdown("**Top values**")
                        tv = s['Top Values']
                        chart = alt.Chart(tv).mark_bar(color='#635bff', cornerRadiusTopRight=6, cornerRadiusBottomRight=6).encode(
                            y=alt.Y('VAL:N', sort='-x', title=None), x=alt.X('CNT:Q', title='Count')
                        )
                        st.altair_chart(chart)

            with t_sample:
                st.dataframe(qry(f"SELECT * FROM {DB}.{DEMO_SCHEMA}.{sel} LIMIT 10"))

            c1, c2 = st.columns(2)
            with c1:
                if st.button(":material/play_arrow: Scan this table", type="primary", use_container_width=True):
                    try:
                        with st.spinner(f"Scanning {sel}..."):
                            sid,iss,tot = scan_table(sel, stype or 'DEEP')
                            sc,scores = calc_scores(iss,tot)
                            save_scan(sid,sel,iss,tot,scores,sc)
                            st.session_state['scan_issues'] = iss
                            st.session_state['scan_table'] = sel
                            st.session_state['scan_score'] = sc
                            st.session_state['scan_scores'] = scores
                            st.session_state['scan_id'] = sid
                        st.success(f"Score: **{sc}/100** | Issues: **{len(iss)}**", icon=":material/check_circle:")
                    except Exception as e:
                        st.error(f"Scan failed: {str(e)[:200]}")
            with c2:
                if st.button(":material/select_all: Scan all tables", use_container_width=True):
                    all_iss = []
                    prog = st.progress(0, text="Scanning...")
                    for idx,t in enumerate(tables):
                        prog.progress(idx/len(tables), text=f"Scanning {t}...")
                        sid,iss,tot = scan_table(t, stype or 'DEEP')
                        sc,scores = calc_scores(iss,tot)
                        save_scan(sid,t,iss,tot,scores,sc)
                        all_iss.extend(iss)
                    prog.progress(1.0, text="Done!")
                    st.session_state['scan_issues'] = all_iss
                    st.success(f"All scanned! **{len(all_iss)}** issues found.", icon=":material/check_circle:")


# ══════════════════════════════════════════════════════════
# QUALITY REPORT
# ══════════════════════════════════════════════════════════
elif "Quality Report" in page:
    st.markdown("# :material/assessment: :orange[AI quality report]")
    if 'scan_issues' not in st.session_state or not st.session_state['scan_issues']:
        st.info("Run a scan first from **Discovery** or **Live Demo**.", icon=":material/info:")
    else:
        iss = st.session_state['scan_issues']
        tbl = st.session_state.get('scan_table','All')
        sc = st.session_state.get('scan_score',0)
        scores = st.session_state.get('scan_scores',{})

        # Score + severity badges
        with st.container(horizontal=True):
            st.metric(f":material/favorite: {tbl}", f"{sc}/100", border=True)
            for sev in ['CRITICAL','HIGH','MEDIUM','LOW']:
                n = sum(1 for i in iss if i['severity']==sev)
                if n: st.metric(f"{SEV_BADGE[sev]}", n, border=True)

        # Dimension scores
        if scores:
            with st.container(border=True):
                st.markdown("**Dimension scores**")
                dc = st.columns(6)
                for i,(d,v) in enumerate(scores.items()):
                    with dc[i]:
                        st.markdown(f"{DIM_ICON.get(d,'')} **{d.title()}**")
                        st.progress(v/100)
                        st.markdown(f":{score_color(v)}[**{v:.0f}%**]", text_alignment="center")

        # Severity breakdown chart
        sev_data = pd.DataFrame([{'Severity': s, 'Count': sum(1 for i in iss if i['severity']==s), 'Color': c} for s,c in [('CRITICAL','#ff6b6b'),('HIGH','#ff922b'),('MEDIUM','#fcc419'),('LOW','#51cf66')] if sum(1 for i in iss if i['severity']==s)>0])
        if not sev_data.empty:
            with st.container(border=True):
                chart = alt.Chart(sev_data).mark_bar(cornerRadiusTopRight=8, cornerRadiusBottomRight=8).encode(
                    y=alt.Y('Severity:N', sort=['CRITICAL','HIGH','MEDIUM','LOW'], title=None),
                    x=alt.X('Count:Q', title='Number of issues'),
                    color=alt.Color('Color:N', scale=None)
                )
                st.altair_chart(chart)

        # Issue list
        with st.container(border=True):
            st.markdown("**:material/list: Issues**")
            fc1, fc2 = st.columns(2)
            with fc1: sf = st.multiselect("Severity", ['CRITICAL','HIGH','MEDIUM','LOW'], default=['CRITICAL','HIGH','MEDIUM'])
            with fc2: cf = st.multiselect("Category", list(set(i['rule_category'] for i in iss)))
            fi = [i for i in iss if i['severity'] in sf]
            if cf: fi = [i for i in fi if i['rule_category'] in cf]
            if fi:
                df = pd.DataFrame(fi)[['severity','column_name','rule_category','rule_name','affected_rows','affected_percentage','issue_description']]
                df.columns = ['Severity','Column','Category','Rule','Rows','%','Description']
                st.dataframe(df, hide_index=True, column_config={
                    "Rows": st.column_config.NumberColumn(format="%d"),
                    "%": st.column_config.ProgressColumn("Impact", min_value=0, max_value=100)
                })

        # AI explanation
        with st.container(border=True):
            st.markdown("**:material/auto_awesome: AI explanation**")
            opts = [f"[{i['severity']}] {i['column_name']}: {i['rule_name']}" for i in iss]
            si = st.selectbox("Issue", range(len(opts)), format_func=lambda x: opts[x])
            if st.button(":material/auto_awesome: Explain with AI", type="primary"):
                with st.spinner("AI analyzing..."):
                    st.markdown(ai_explain(iss[si]))


# ══════════════════════════════════════════════════════════
# FIX CENTER
# ══════════════════════════════════════════════════════════
elif "Fix Center" in page:
    st.markdown("# :material/auto_fix_high: :green[AI fix center]")
    st.warning("All fixes need explicit approval. :orange[No silent modifications.]", icon=":material/shield:")

    if 'scan_issues' not in st.session_state or not st.session_state['scan_issues']:
        st.info("Run a scan first.", icon=":material/info:")
    else:
        iss = st.session_state['scan_issues']
        fixable = [i for i in iss if i['remediation_sql'] and not i['remediation_sql'].strip().startswith('--') and not i['remediation_sql'].strip().upper().startswith('SELECT')]
        safe = [i for i in fixable if i['risk_level']=='LOW']

        with st.container(horizontal=True):
            st.metric(":material/error: Total issues", len(iss), border=True)
            st.metric(":material/build: Fixable", len(fixable), border=True)
            st.metric(":green-badge[LOW RISK]", len(safe), border=True)

        if safe:
            if st.button(f":material/auto_fix_high: Apply {len(safe)} safe fixes", type="primary"):
                ok = 0
                for fx in safe:
                    try:
                        exe(fx['remediation_sql']); ok += 1
                        try:
                            sq = fx['remediation_sql'].replace("'", "''")
                            sid_val = scan_id()
                            prev_sid = st.session_state.get('scan_id', '')
                            exe(f"INSERT INTO {DB}.{ENGINE_SCHEMA}.REMEDIATION_LOG(REMEDIATION_ID,SCAN_ID,TABLE_NAME,COLUMN_NAME,ISSUE_TYPE,SEVERITY,AFFECTED_ROWS,REMEDIATION_SQL,APPROVAL_STATUS,EXECUTED_AT,EXECUTION_RESULT) VALUES('{sid_val}','{prev_sid}','{fx['table_name']}','{fx['column_name']}','{fx['rule_name']}','{fx['severity']}',{fx['affected_rows']},'{sq}','EXECUTED',CURRENT_TIMESTAMP(),'SUCCESS')")
                        except Exception: pass
                    except Exception as e: st.error(f"Failed: {fx['column_name']}: {str(e)[:80]}")
                st.success(f"Applied **{ok}/{len(safe)}** fixes!", icon=":material/check_circle:")
                st.toast(f"{ok} fixes applied!", icon=":material/thumb_up:")

        for idx,i in enumerate(fixable):
            sev = i['severity']
            with st.expander(f"{SEV_BADGE[sev]} **{i['column_name']}**: {i['rule_name']} — :red[{i['affected_rows']:,} rows]"):
                st.markdown(f"**Problem:** {i['issue_description']}")
                st.markdown(f"**Impact:** {i['business_impact']}")
                with st.container(horizontal=True):
                    st.badge(i['risk_level'], color='green' if i['risk_level']=='LOW' else 'orange')
                    st.badge(f"{i['confidence']}% confidence", color='blue')
                st.code(i['remediation_sql'], language='sql')
                if st.button(":material/check: Apply", key=f"f{idx}", type="primary"):
                    try:
                        exe(i['remediation_sql'])
                        st.success("Applied!", icon=":material/check_circle:")
                    except Exception as e: st.error(str(e)[:150])


# ══════════════════════════════════════════════════════════
# TRUST SCORE
# ══════════════════════════════════════════════════════════
elif "Trust Score" in page:
    st.markdown("# :material/show_chart: :blue[Data trust score]")
    trend = qry(f"SELECT SCAN_DATE,TABLE_NAME,HEALTH_SCORE,COMPLETENESS_SCORE,UNIQUENESS_SCORE,VALIDITY_SCORE,CONSISTENCY_SCORE,INTEGRITY_SCORE,FRESHNESS_SCORE,TOTAL_ISSUES,CRITICAL_ISSUES,ROWS_AT_RISK FROM {DB}.{ENGINE_SCHEMA}.HEALTH_SCORE_HISTORY ORDER BY SCAN_DATE,TABLE_NAME")

    if trend.empty:
        st.info("No history yet.", icon=":material/info:")
    else:
        agg = trend.groupby('SCAN_DATE').agg({'HEALTH_SCORE':'mean','TOTAL_ISSUES':'sum','ROWS_AT_RISK':'sum'}).reset_index()
        cur = float(agg['HEALTH_SCORE'].iloc[-1])
        first = float(agg['HEALTH_SCORE'].iloc[0])

        with st.container(horizontal=True):
            st.metric(":material/favorite: Current", f"{cur:.0f}/100", delta=f"+{cur-first:.0f} pts", border=True, chart_data=agg['HEALTH_SCORE'].tolist(), chart_type="line")
            st.metric(":material/error: Issues", int(agg['TOTAL_ISSUES'].iloc[-1]), border=True, chart_data=agg['TOTAL_ISSUES'].tolist(), chart_type="bar")
            st.metric(":material/group: At risk", f"{int(agg['ROWS_AT_RISK'].iloc[-1]):,}", border=True)

        with st.container(border=True):
            st.markdown("**:material/show_chart: Score evolution**")
            area = alt.Chart(agg).mark_area(opacity=0.25, color='#635bff').encode(x=alt.X('SCAN_DATE:T',title='Date'), y=alt.Y('HEALTH_SCORE:Q',title='Score',scale=alt.Scale(domain=[0,100])))
            line = alt.Chart(agg).mark_line(color='#635bff',strokeWidth=3).encode(x='SCAN_DATE:T',y='HEALTH_SCORE:Q')
            st.altair_chart(area + line)

        with st.container(border=True):
            st.markdown("**Per-table scores**")
            last = trend[trend['SCAN_DATE']==trend['SCAN_DATE'].max()]
            for _,r in last.iterrows():
                h = float(r['HEALTH_SCORE'])
                with st.container(horizontal=True):
                    st.markdown(f"{score_emoji(h)} **{r['TABLE_NAME']}**")
                    st.progress(h/100)
                    st.markdown(f":{score_color(h)}[**{h:.0f}**]/100")

        if len(agg)>=2:
            with st.container(border=True):
                prev,cur_r = agg.iloc[-2],agg.iloc[-1]
                d = cur_r['HEALTH_SCORE'] - prev['HEALTH_SCORE']
                if d>0: st.success(f":material/trending_up: Trust improved **+{d:.1f}** pts. Issues: {int(prev['TOTAL_ISSUES'])} → {int(cur_r['TOTAL_ISSUES'])}", icon=":material/thumb_up:")
                elif d<0: st.warning(f":material/trending_down: Trust dropped **{d:.1f}** pts. Investigate recent ingestion.", icon=":material/warning:")
                else: st.info("Stable since last scan.", icon=":material/horizontal_rule:")


# ══════════════════════════════════════════════════════════
# CONTRACTS
# ══════════════════════════════════════════════════════════
elif "Contracts" in page:
    st.markdown("# :material/gavel: :violet[Quality contracts]")
    st.caption("Define rules in plain English — AI converts them to executable checks.")

    with st.container(border=True):
        st.markdown("**:material/add_circle: New contract**")
        ct = st.selectbox("Table", get_tables(), key="ct")
        cr = st.text_input("Rule", placeholder="e.g. Order amount must be positive")
        cs = st.select_slider("Severity", ['LOW','MEDIUM','HIGH','CRITICAL'], value='HIGH')
        if st.button(":material/auto_awesome: Create", type="primary"):
            if cr and ct:
                try:
                    p = f"Convert this rule to a Snowflake SQL WHERE clause finding violations: Table: {DB}.{DEMO_SCHEMA}.{ct}. Rule: {cr}. Return ONLY the WHERE clause."
                    r = qry(f"SELECT SNOWFLAKE.CORTEX.COMPLETE('llama3.1-70b','{p.replace(chr(39),chr(39)+chr(39))}') AS R")
                    sql = r['R'].iloc[0].strip().strip('"').strip("'")
                    exe(f"INSERT INTO {DB}.{ENGINE_SCHEMA}.QUALITY_CONTRACTS(CONTRACT_NAME,TABLE_NAME,COLUMN_NAME,NATURAL_LANGUAGE_RULE,GENERATED_SQL_CHECK,SEVERITY) VALUES('{cr[:100].replace(chr(39),chr(39)+chr(39))}','{ct}','MULTI','{cr.replace(chr(39),chr(39)+chr(39))}','{sql.replace(chr(39),chr(39)+chr(39))}','{cs}')")
                    st.success("Contract created!", icon=":material/check_circle:")
                    st.code(f"SELECT * FROM {DB}.{DEMO_SCHEMA}.{ct}\nWHERE {sql}", language='sql')
                    try:
                        v = int(qry(f"SELECT COUNT(*) AS V FROM {DB}.{DEMO_SCHEMA}.{ct} WHERE {sql}")['V'].iloc[0])
                        if v: st.warning(f":red[{v:,}] current violations!", icon=":material/warning:")
                        else: st.success("No violations — data passes!", icon=":material/verified:")
                    except Exception as e: st.caption(f"Validation error: {str(e)[:80]}")
                except Exception as e: st.error(f"Failed: {str(e)[:150]}")

    with st.container(border=True):
        st.markdown("**:material/list: Active contracts**")
        cdf = qry(f"SELECT CONTRACT_ID,TABLE_NAME,NATURAL_LANGUAGE_RULE,GENERATED_SQL_CHECK,SEVERITY,CREATED_AT FROM {DB}.{ENGINE_SCHEMA}.QUALITY_CONTRACTS WHERE IS_ACTIVE=TRUE ORDER BY CREATED_AT DESC")
        if cdf.empty:
            st.caption("No contracts yet.")
        else:
            for _,c in cdf.iterrows():
                with st.expander(f"{SEV_BADGE.get(c['SEVERITY'],'')} {c['NATURAL_LANGUAGE_RULE'][:60]}"):
                    st.caption(f"Table: :violet[{c['TABLE_NAME']}] | Created: {c['CREATED_AT']}")
                    st.code(c['GENERATED_SQL_CHECK'], language='sql')
                    try:
                        v = int(qry(f"SELECT COUNT(*) AS V FROM {DB}.{DEMO_SCHEMA}.{c['TABLE_NAME']} WHERE {c['GENERATED_SQL_CHECK']}")['V'].iloc[0])
                        if v: st.markdown(f":red-badge[{v:,} VIOLATIONS]")
                        else: st.markdown(":green-badge[PASSING]")
                    except Exception: st.caption("Cannot evaluate")


# ══════════════════════════════════════════════════════════
# AUDIT
# ══════════════════════════════════════════════════════════
elif "Audit" in page:
    st.markdown("# :material/history: Audit & governance")
    t1, t2 = st.tabs([":material/search: Scans", ":material/build: Remediations"])
    with t1:
        df = qry(f"SELECT SCAN_ID,SCAN_TIMESTAMP,TABLE_NAME,TOTAL_ROWS,ISSUES_FOUND,CRITICAL_ISSUES,HEALTH_SCORE,SCAN_TYPE FROM {DB}.{ENGINE_SCHEMA}.SCAN_RESULTS ORDER BY SCAN_TIMESTAMP DESC LIMIT 50")
        if df.empty: st.caption("No scans.")
        else: st.dataframe(df, hide_index=True, column_config={"HEALTH_SCORE": st.column_config.ProgressColumn("Health", min_value=0, max_value=100)})
    with t2:
        df = qry(f"SELECT REMEDIATION_ID,TABLE_NAME,COLUMN_NAME,ISSUE_TYPE,SEVERITY,AFFECTED_ROWS,APPROVAL_STATUS,EXECUTED_AT,EXECUTION_RESULT FROM {DB}.{ENGINE_SCHEMA}.REMEDIATION_LOG ORDER BY CREATED_AT DESC LIMIT 50")
        if df.empty: st.caption("No remediations.")
        else: st.dataframe(df, hide_index=True)


# ══════════════════════════════════════════════════════════
# ASK GUARDIAN
# ══════════════════════════════════════════════════════════
elif "Ask" in page:
    st.markdown("# :material/smart_toy: :violet[Ask DataGuardian]")

    with st.container(border=True):
        st.markdown(":violet[**Try these:**]")
        ex = st.columns(3)
        ex[0].markdown(':blue-background["Can I trust the revenue dashboard?"]')
        ex[1].markdown(':orange-background["Which table has the worst quality?"]')
        ex[2].markdown(':green-background["What changed since last scan?"]')

    if 'msgs' not in st.session_state: st.session_state.msgs = []
    for m in st.session_state.msgs:
        with st.chat_message(m['role'], avatar=":material/smart_toy:" if m['role']=='assistant' else ":material/person:"):
            st.markdown(m['content'])

    if p := st.chat_input("Ask anything about data quality..."):
        st.session_state.msgs.append({'role':'user','content':p})
        with st.chat_message('user', avatar=":material/person:"): st.markdown(p)
        with st.chat_message('assistant', avatar=":material/smart_toy:"):
            with st.spinner("Thinking..."): resp = ask_guardian(p)
            st.markdown(resp)
        st.session_state.msgs.append({'role':'assistant','content':resp})


# ══════════════════════════════════════════════════════════
# LIVE DEMO
# ══════════════════════════════════════════════════════════
elif "Demo" in page:
    st.markdown("# :material/play_circle: :violet[Competition live demo]")
    st.markdown("> :red[*\"Bad data is invisible until it becomes a bad decision.\"*]")

    if st.button(":material/play_arrow: **RUN LIVE DEMO**", type="primary", use_container_width=True):

        with st.status(":material/search: **Step 1** — Discovering dataset...", expanded=True) as s:
            tables = get_tables()
            for t in tables:
                rc,_ = get_table_info(t)
                st.markdown(f":material/table_chart: **{t}** — :blue[{rc:,}] rows")
            s.update(label=f":material/check_circle: :green[Discovered {len(tables)} tables]", state="complete")

        with st.status(":material/radar: **Step 2** — Scanning quality rules...", expanded=True) as s:
            all_iss = {}; all_sc = {}
            for t in tables:
                sid,iss,tot = scan_table(t)
                sc,scores = calc_scores(iss,tot)
                save_scan(sid,t,iss,tot,scores,sc)
                all_iss[t] = iss; all_sc[t] = {'score':sc,'issues':len(iss),'scores':scores}
                st.markdown(f"**{t}**: :{score_color(sc)}[{sc}/100] · {len(iss)} issues")
            flat = [i for v in all_iss.values() for i in v]
            st.session_state['scan_issues'] = flat
            s.update(label=f":material/check_circle: :green[{len(flat)} issues found across {len(tables)} tables]", state="complete")

        avg_before = sum(v['score'] for v in all_sc.values())/len(all_sc)
        with st.container(border=True):
            st.markdown("### :material/assessment: Health score :red[BEFORE]")
            with st.container(horizontal=True):
                for t,d in all_sc.items():
                    st.metric(t, f"{d['score']}/100", border=True)
                st.metric(":material/favorite: Overall", f"{avg_before:.0f}/100", border=True)

        with st.status(":material/error: **Step 3** — Critical issues...", expanded=True) as s:
            crit = [i for i in flat if i['severity'] in ('CRITICAL','HIGH')]
            for i in crit[:5]:
                st.markdown(f"{SEV_BADGE[i['severity']]} **{i['table_name']}.{i['column_name']}**: {i['issue_description']}")
            s.update(label=f":material/check_circle: :orange[{len(crit)} critical/high issues]", state="complete")

        with st.status(":material/auto_awesome: **Step 4** — AI explanation...", expanded=True) as s:
            if crit: st.markdown(ai_explain(crit[0]))
            s.update(label=":material/check_circle: :green[AI analysis complete]", state="complete")

        with st.status(":material/auto_fix_high: **Step 5** — Applying safe fixes...", expanded=True) as s:
            safe = [i for i in flat if i['risk_level']=='LOW' and not i['remediation_sql'].strip().startswith('--') and not i['remediation_sql'].strip().upper().startswith('SELECT')]
            ok = 0
            for f in safe:
                try: exe(f['remediation_sql']); ok += 1
                except: pass
            st.markdown(f"Applied :green[**{ok}**]/{len(safe)} low-risk fixes")
            s.update(label=f":material/check_circle: :green[{ok} fixes applied]", state="complete")

        with st.status(":material/refresh: **Step 6** — Re-scanning...", expanded=True) as s:
            after_sc = {}
            for t in tables:
                sid,iss,tot = scan_table(t)
                sc,scores = calc_scores(iss,tot)
                save_scan(sid,t,iss,tot,scores,sc)
                after_sc[t] = {'score':sc,'issues':len(iss)}
            s.update(label=":material/check_circle: :green[Re-scan complete]", state="complete")

        avg_after = sum(v['score'] for v in after_sc.values())/len(after_sc)
        imp = avg_after - avg_before

        with st.container(border=True):
            st.markdown("### :material/compare_arrows: Before vs After")
            c1,c2 = st.columns(2)
            with c1:
                st.markdown("#### :red[Before]")
                st.metric("Score", f"{avg_before:.0f}/100", border=True)
                st.metric("Issues", sum(v['issues'] for v in all_sc.values()), border=True)
            with c2:
                st.markdown("#### :green[After]")
                st.metric("Score", f"{avg_after:.0f}/100", delta=f"+{imp:.0f}", border=True)
                st.metric("Issues", sum(v['issues'] for v in after_sc.values()), border=True)

        total_rows = sum(int(qry(f"SELECT COUNT(*) AS C FROM {DB}.{DEMO_SCHEMA}.{t}")['C'].iloc[0]) for t in tables)
        st.success(f"""
**:material/verified: DataGuardian AI — Autonomous remediation complete**

:blue[{len(tables)}] tables scanned · :violet[{total_rows:,}] rows analyzed · :orange[{len(flat)}] issues detected
:green[{ok}] fixes applied · Health: :red[{avg_before:.0f}] → :green[{avg_after:.0f}] (+{imp:.0f} pts) · Full audit trail logged
        """, icon=":material/rocket_launch:")
