---
name: wood-10k
description: Evaluate a company's five-year SEC 10-K facts through a Cathie Wood-style disruptive innovation lens for the Lab 18 investor panel.
---

# Wood-style 10-K review

From the Lab 18 folder, run `python3 edgar.py TICKER` after setting `SEC_USER_AGENT` to your real name and email. Use the same printed report given to the other panel skills. The script owns fact selection and arithmetic; do not fill missing facts with estimates.

Write `wood-10k/TICKER.md` with a decision of **fit**, **watch**, or **pass**. Read the script's coded checks: first-to-last revenue growth of at least 5% annually using `(last / first)^(1/4) - 1`, and latest-year `ResearchAndDevelopmentExpense` of at least 5% of revenue. Report pass, fail, or not known for each; a missing R&D tag is not zero. The growth threshold is the Lab 19 probe choice; the thresholds are classroom screen rules, not claims about Wood's actual trading criteria. Record the threshold kept and why below the memo.

Test whether the company plausibly enables or benefits from disruptive innovation over a five-year horizon. Ask what S-curve adoption, expanding TAM, falling unit costs under Wright's Law, and platform convergence would have to look like. These selected 10-K fields do not supply the adoption, cost-curve, or market data needed to quantify those ideas, so identify them as open questions. Separate what the filings show from judgment about technology adoption or future growth. A conventional high-quality business may be a poor fit for this mandate. A market sell-off alone is not evidence of opportunity. This lens is adapted from the [FAskills Cathie Wood page](https://github.com/CinderZhang/FAskills/blob/main/financial-researcher/experts/cathie_wood.md); do not install its paid data pipeline.

Use only numeric values printed by `edgar.py` in the memo. State what the selected 10-K facts cannot establish, especially product-level adoption, future growth, and price relative to future value. Do not claim to speak for Cathie Wood or predict her trades. ARK describes its five-year horizon and its approach to volatility in [Wood's market commentary](https://www.ark-invest.com/articles/market-commentary/innovation-stocks-are-not-in-a-bubble).

Run `python3 edgar.py TICKER --check-memo wood-10k/TICKER.md` before finishing. The memo is read by `app.py`.
