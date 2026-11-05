"""Keyless SEC EDGAR five-year 10-K fact selector for the class exercise."""

import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

import requests

METRICS = {
    "revenue": ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"),
    "net_income": ("NetIncomeLoss",),
    "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
    "capital_spending": ("PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"),
    "research_and_development": ("ResearchAndDevelopmentExpense",),
    "equity": ("StockholdersEquity",),
    "liabilities": ("Liabilities",),
}
FLOW_FIELDS = {"revenue", "net_income", "operating_cash_flow", "capital_spending", "research_and_development"}
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{:010d}.json"


def user_agent():
    agent = os.environ.get("SEC_USER_AGENT", "").strip()
    if not re.search(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b", agent) or len(agent.split()) < 2:
        raise ValueError("Set SEC_USER_AGENT to your real name and email before requesting SEC data.")
    return agent


def get_json(url, agent):
    response = requests.get(url, headers={"User-Agent": agent, "Accept": "application/json"}, timeout=30)
    response.raise_for_status()
    return response.json()


def resolve_ticker(ticker, agent):
    ticker = ticker.upper().strip()
    for company in get_json(TICKERS_URL, agent).values():
        if company["ticker"].upper() == ticker:
            return company["cik_str"], company["title"]
    raise ValueError(f"Ticker {ticker} was not found in the SEC ticker map.")


def annual_fact(item, flow):
    if item.get("form") != "10-K" or item.get("fp") != "FY" or not item.get("end") or not item.get("filed"):
        return False
    if flow:
        if not item.get("start"):
            return False
        try:
            days = (date.fromisoformat(item["end"]) - date.fromisoformat(item["start"])).days
        except ValueError:
            return False
        return 330 <= days <= 380
    return not item.get("start")


def entries(facts, tag, flow):
    units = facts.get("facts", {}).get("us-gaap", {}).get(tag, {}).get("units", {})
    return [item for item in units.get("USD", []) if annual_fact(item, flow)]


def choose_fact(facts, field, fiscal_end):
    for tag in METRICS[field]:
        matches = [item for item in entries(facts, tag, field in FLOW_FIELDS) if item["end"] == fiscal_end]
        if matches:
            selected = max(matches, key=lambda x: (x["filed"], x.get("accn", "")))
            return {"value": selected["val"], "tag": tag, "filed": selected["filed"]}
    return {"value": None, "tag": "not found", "filed": None}


def tri_check(values, predicate):
    if not values or any(v is None for v in values):
        return "not known"
    return "yes" if predicate(values) else "no"


def panel_check(values, predicate):
    if not values or any(value is None for value in values):
        return "not known"
    return "pass" if predicate(values) else "fail"


def build_report(ticker, cik, company, facts):
    ends = set()
    for field in FLOW_FIELDS - {"research_and_development"}:
        for tag in METRICS[field]:
            ends.update(item["end"] for item in entries(facts, tag, True))
    fiscal_ends = sorted(ends, reverse=True)[:5]
    rows = []
    for fiscal_end in reversed(fiscal_ends):
        row = {"fiscal_year_end": fiscal_end}
        for field in METRICS:
            row[field] = choose_fact(facts, field, fiscal_end)
        income, equity = row["net_income"]["value"], row["equity"]["value"]
        liabilities = row["liabilities"]["value"]
        cash, capex = row["operating_cash_flow"]["value"], row["capital_spending"]["value"]
        row["roe_status"] = "not found" if income is None or equity is None else "not known" if equity <= 0 else None
        row["liabilities_to_equity_status"] = "not found" if liabilities is None or equity is None else "not known" if equity <= 0 else None
        row["roe"] = None if income is None or equity is None or equity <= 0 else income / equity
        row["liabilities_to_equity"] = None if liabilities is None or equity is None or equity <= 0 else liabilities / equity
        row["owner_earnings"] = None if cash is None or capex is None else cash - capex
        rows.append(row)
    checks = {
        "roe_15_each_year": tri_check([r["roe"] for r in rows] if len(rows) == 5 else [None], lambda v: all(x >= 0.15 for x in v)),
        "owner_earnings_positive_each_year": tri_check([r["owner_earnings"] for r in rows] if len(rows) == 5 else [None], lambda v: all(x > 0 for x in v)),
        "owner_earnings_grew_first_to_last": tri_check([rows[0]["owner_earnings"], rows[-1]["owner_earnings"]] if len(rows) == 5 else [None], lambda v: v[-1] > v[0]),
    }
    first_revenue = rows[0]["revenue"]["value"] if len(rows) == 5 else None
    last_revenue = rows[-1]["revenue"]["value"] if len(rows) == 5 else None
    latest_rd = rows[-1]["research_and_development"]["value"] if len(rows) == 5 else None
    revenue_growth = None if first_revenue is None or last_revenue is None or first_revenue <= 0 or last_revenue < 0 else (last_revenue / first_revenue) ** (1 / 4) - 1
    rd_to_revenue = None if latest_rd is None or last_revenue is None or last_revenue <= 0 else latest_rd / last_revenue
    cash_minus_income = [
        None if row["operating_cash_flow"]["value"] is None or row["net_income"]["value"] is None
        else row["operating_cash_flow"]["value"] - row["net_income"]["value"]
        for row in rows
    ] if len(rows) == 5 else [None]
    latest_leverage = rows[-1]["liabilities_to_equity"] if len(rows) == 5 else None
    panel_checks = {
        "wood_revenue_growth_5": panel_check([revenue_growth], lambda v: v[0] >= 0.05),
        "wood_rd_5": panel_check([rd_to_revenue], lambda v: v[0] >= 0.05),
        "burry_cash_at_least_income": panel_check(cash_minus_income, lambda v: all(x >= 0 for x in v)),
        "burry_liabilities_at_most_2x_equity": panel_check([latest_leverage], lambda v: v[0] <= 2),
    }
    return {"ticker": ticker.upper(), "cik": cik, "company": company, "rows": rows, "checks": checks, "panel_checks": panel_checks, "revenue_growth": revenue_growth, "rd_to_revenue": rd_to_revenue}


def fmt(value, ratio=False):
    if value is None:
        return "not known" if ratio else "not found"
    return f"{value:.2%}" if ratio else f"{value:,.0f}"


def fmt_multiple(value):
    return "not known" if value is None else f"{value:.2f}"


def render_text(report):
    lines = [f"{report['company']} ({report['ticker']}) | CIK {report['cik']}", "Source: SEC EDGAR companyfacts; 10-K; USD; fiscal-year-end dates", ""]
    for row in report["rows"]:
        lines.append(f"Fiscal year end: {row['fiscal_year_end']}")
        for field in METRICS:
            fact = row[field]
            lines.append(f"  {field}: {fmt(fact['value'])} | us-gaap:{fact['tag']} | filed {fact['filed'] or 'not found'}")
        lines.append(f"  roe: {row['roe_status'] or fmt(row['roe'], True)} | NetIncomeLoss / StockholdersEquity")
        lines.append(f"  liabilities_to_equity: {row['liabilities_to_equity_status'] or fmt_multiple(row['liabilities_to_equity'])} | Liabilities / StockholdersEquity")
        lines.append(f"  owner_earnings: {fmt(row['owner_earnings'])} | {row['operating_cash_flow']['tag']} - {row['capital_spending']['tag']}")
        lines.append("")
    lines.append("Checks:")
    for label, result in report["checks"].items():
        lines.append(f"  {label}: {result}")
    lines.append(f"  revenue_growth_first_to_last_annualized: {fmt(report['revenue_growth'], True)} | (last revenue / first revenue)^(1/4) - 1")
    lines.append(f"  latest_rd_to_revenue: {fmt(report['rd_to_revenue'], True)} | ResearchAndDevelopmentExpense / revenue")
    descriptions = {
        "wood_revenue_growth_5": "at least 5% annually",
        "wood_rd_5": "at least 5% of latest revenue",
        "burry_cash_at_least_income": "operating cash flow at least net income every year",
        "burry_liabilities_at_most_2x_equity": "latest liabilities at most 2 times equity",
    }
    for label, result in report["panel_checks"].items():
        lines.append(f"  {label}: {result} | {descriptions[label]}")
    return "\n".join(lines)


NUMBER = re.compile(r"(?<![A-Za-z0-9])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?(?![A-Za-z0-9])")


def unsupported_numbers(memo, printed):
    allowed = set(NUMBER.findall(printed))
    return [(match.group(), memo.count("\n", 0, match.start()) + 1) for match in NUMBER.finditer(memo) if match.group() not in allowed]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ticker")
    parser.add_argument("--json", action="store_true", help="print machine-readable report")
    parser.add_argument("--check-memo", type=Path, help="flag numeric tokens absent from the printed report")
    args = parser.parse_args()
    try:
        report = fetch_report(args.ticker)
        printed = render_text(report)
        if args.check_memo:
            issues = unsupported_numbers(args.check_memo.read_text(), printed)
            if issues:
                for number, line in issues:
                    print(f"Unsupported number on memo line {line}: {number}")
                return 1
            print("Memo numeric check: all numbers appeared in the script output.")
        elif args.json:
            print(json.dumps(report, indent=2))
        else:
            print(printed)
        return 0
    except (ValueError, requests.RequestException, OSError, KeyError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


def fetch_report(ticker):
    agent = user_agent()
    cik, company = resolve_ticker(ticker, agent)
    return build_report(ticker, cik, company, get_json(FACTS_URL.format(cik), agent))


if __name__ == "__main__":
    raise SystemExit(main())
