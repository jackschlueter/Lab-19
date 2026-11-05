"""Streamlit view of the Lab 18 three-investor 10-K panel."""

import os
import re
from pathlib import Path

import pandas as pd
import streamlit as st

from edgar import METRICS, fetch_report, fmt, fmt_multiple, render_text, unsupported_numbers

ROOT = Path(__file__).resolve().parent

st.set_page_config(page_title="Lab 19 investor panel", layout="wide")
st.title("Lab 19 investor panel")
st.caption("Data from SEC EDGAR; built with AI help, a learning demonstration, not investment advice.")
st.caption("Investor lenses: [FAskills Cathie Wood](https://github.com/CinderZhang/FAskills/blob/main/financial-researcher/experts/cathie_wood.md) · [FAskills Michael Burry](https://github.com/CinderZhang/FAskills/blob/main/financial-researcher/experts/michael_burry.md) · [Streamlit table docs](https://docs.streamlit.io/develop/concepts/design/dataframes). Check thresholds are classroom rules.")

ticker = st.text_input("Ticker", value="COST").strip().upper()
agent = st.text_input("SEC User-Agent (your name and email, if not set locally)", type="password")
if agent:
    os.environ["SEC_USER_AGENT"] = agent

if ticker:
    try:
        report = fetch_report(ticker)
    except Exception as error:
        st.error(str(error))
        st.stop()

    rows = report["rows"]
    st.subheader(f"{report['company']} ({ticker})")
    st.write("Fiscal years are labelled by year-end date. Values are USD; facts come only from 10-K filings.")
    st.link_button("Open SEC company facts", f"https://data.sec.gov/api/xbrl/companyfacts/CIK{report['cik']:010d}.json")

    st.subheader("Three views of the same facts")
    investors = (
        ("Buffett", ROOT / f"{ticker}.md", "buffett-10k"),
        ("Wood-style", ROOT / "wood-10k" / f"{ticker}.md", "wood-10k"),
        ("Burry-style", ROOT / "burry-10k" / f"{ticker}.md", "burry-10k"),
    )
    memos = {name: path.read_text() if path.exists() else "" for name, path, _ in investors}
    verdicts = {}
    for name, memo in memos.items():
        match = re.search(r"\*\*Decision:\s*([^*]+)\*\*", memo, re.IGNORECASE)
        verdicts[name] = match.group(1).strip().rstrip(".") if match else "not written"
    checks = (
        ("Buffett", "ROE at least 15% each year", report["checks"]["roe_15_each_year"]),
        ("Buffett", "Owner earnings positive each year", report["checks"]["owner_earnings_positive_each_year"]),
        ("Buffett", "Owner earnings grew first to last", report["checks"]["owner_earnings_grew_first_to_last"]),
        ("Wood-style", "Revenue growth at least 5% annually", report["panel_checks"]["wood_revenue_growth_5"]),
        ("Wood-style", "Latest R&D at least 5% of revenue", report["panel_checks"]["wood_rd_5"]),
        ("Burry-style", "Operating cash flow at least net income every year", report["panel_checks"]["burry_cash_at_least_income"]),
        ("Burry-style", "Latest liabilities at most twice equity", report["panel_checks"]["burry_liabilities_at_most_2x_equity"]),
    )
    st.dataframe(pd.DataFrame([
        {"Investor": name, "Check": label, "Result": {"yes": "pass", "no": "fail"}.get(result, result), "Verdict": verdicts[name]}
        for name, label, result in checks
    ]), hide_index=True, width="stretch")
    st.caption(f"Annualized revenue growth: {fmt(report['revenue_growth'], True)}. Latest R&D/revenue: {fmt(report['rd_to_revenue'], True)}. A missing filing fact is not known, not zero.")

    all_unsupported = []
    for column, (name, memo_path, skill_name) in zip(st.columns(3), investors):
        with column:
            st.markdown(f"### {name}")
            memo = memos[name]
            if memo:
                st.markdown(memo)
                unsupported = unsupported_numbers(memo, render_text(report))
                if unsupported:
                    all_unsupported.extend((name, number, line) for number, line in unsupported)
            else:
                st.info(f"No memo yet. Run the {skill_name} skill for {ticker}.")
            with st.expander(f"Edit {name} memo"):
                edited = st.text_area("Memo Markdown", value=memo, height=240, key=f"memo_{skill_name}")
                if st.button("Save memo", key=f"save_{skill_name}"):
                    memo_path.write_text(edited)
                    st.rerun()
    if all_unsupported:
        st.error("Unprinted numbers across memos: " + ", ".join(
            f"{name}: {number} (line {line})" for name, number, line in all_unsupported
        ))
    elif any(not memo for memo in memos.values()):
        st.info("Unprinted-number check is incomplete; missing memos: " + ", ".join(
            name for name, memo in memos.items() if not memo
        ))
    else:
        st.success("Unprinted-number check: none across the three memos.")

    panel_path = ROOT / f"PANEL_{ticker}.md"
    if panel_path.exists():
        st.subheader("Would you trust the panel?")
        st.markdown(panel_path.read_text())

    chart = pd.DataFrame([
        {"Fiscal year end": r["fiscal_year_end"], "Owner earnings": r["owner_earnings"], "Net income": r["net_income"]["value"]}
        for r in rows
    ])
    st.subheader("Owner earnings and net income")
    st.line_chart(chart, x="Fiscal year end", y=["Owner earnings", "Net income"])

    table_rows = []
    for row in rows:
        display = {"Fiscal year end": row["fiscal_year_end"]}
        for field in METRICS:
            display[field] = fmt(row[field]["value"])
            display[f"{field} tag"] = row[field]["tag"]
        display["ROE"] = row["roe_status"] or fmt(row["roe"], True)
        display["ROE tags"] = "NetIncomeLoss / StockholdersEquity"
        display["Liabilities / equity"] = row["liabilities_to_equity_status"] or fmt_multiple(row["liabilities_to_equity"])
        display["Owner earnings"] = fmt(row["owner_earnings"])
        display["Owner earnings tags"] = f"{row['operating_cash_flow']['tag']} - {row['capital_spending']['tag']}"
        table_rows.append(display)
    st.subheader("Five-year table")
    st.dataframe(pd.DataFrame(table_rows), hide_index=True, width="stretch")

    st.subheader("Buffett-style checks")
    labels = {
        "roe_15_each_year": "ROE at least 15% every year",
        "owner_earnings_positive_each_year": "Owner earnings positive every year",
        "owner_earnings_grew_first_to_last": "Owner earnings grew, first year to last",
    }
    for key, label in labels.items():
        st.write(f"**{label}:** {report['checks'][key]}")

