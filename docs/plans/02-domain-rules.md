# 02 · Domain rules

Branch `feature/domain-rules` from develop. Follow CLAUDE.md. Effort: high.
Goal: every policy rule that involves numbers, dates or eligibility as PURE functions
(no I/O, no Store, no LLM, no `date.today()`). The reference date is always a parameter.
These get the heaviest tests in the project.

## 0. Commit the pending CLAUDE.md edit
`docs: let plans drive README updates` (README ownership rule).

## Layout
`src/cs_agent/rules/` with `__init__.py`, `pricing.py`, `payment.py`, `shipping.py`,
`returns.py`, `orders.py`, `hours.py`. Results are frozen dataclasses with native types
(Decimal money, `date`). Each function's docstring cites its policy section (e.g. "Policy 6.2").
One module per commit (`feat(rules): ...`) with its tests (`tests/rules/test_<module>.py`).

## 1. pricing.py (Policy 3, 6.2)
`price_quote(list_price: Decimal, promo_percent: int | None) -> PriceQuote` with:
list_price, promo_percent, promo_price (or None), pix_price, final_card_price.
- promo_price = list * (1 - p/100), rounded with to_money.
- PIX 5% applies ONLY when there is no active promotion (not cumulative). With a promo,
  pix_price == promo_price.
- final_card_price = promo_price or list_price.
Tests: no promo (799.90 -> pix 759.91), with promo (359 at 10% -> 323.10, pix 323.10),
rounding half-up.

## 2. payment.py (Policy 3, 3.1)
Installment tiers, per-installment minimum:
- 1x to 3x: R$ 50 (source says "sem valor mínimo (exceto abaixo de R$ 50,00)", read as a
  R$ 50 minimum);
- 4x to 6x: R$ 80; 7x to 12x: R$ 100. Max 12x.
- The payment table's "parcela mínima de R$ 100,00" is treated as the 7–12x tier summary;
  section 3.1 is more specific and wins.
Functions:
- `check_installments(amount, n) -> InstallmentCheck` (valid, installment_value, min_required,
  reason when invalid). 1x is always valid. n outside 1..12 is invalid.
- `max_installments(amount) -> int` (largest valid n, at least 1).
- `can_combine_methods(amount) -> bool` (strictly > R$ 2.000,00).
Tests: 349.90 in 6x invalid (58.32 < 80), 349.90 in 3x valid, 120 in 3x invalid (40 < 50),
1000 -> max 10x, 1200 -> 12x, 100 -> 2x, 2000 not combinable, 2000.01 combinable.

## 3. shipping.py (Policy 5)
`shipping_quote(city: str, order_value: Decimal, category_ids: set[int]) -> ShippingQuote`.
- Metro region = city "Campo Grande" only (case/accent-insensitive compare); the data has
  no other metro cities.
- Metro: free when value >= 500 (policy says "acima" and "abaixo", 500 itself is undefined:
  resolve in the customer's favor), else R$ 35. Delivery 1–3 business days, own courier.
- Other cities: fee None + needs_cep_quote True, options PAC 5–12, SEDEX 2–5, Jadlog 3–8
  business days, insurance included.
- special_freight True if any category in {3 (drums), 4 (keyboards/digital pianos)}.
Tests for each branch, including 500.00 exactly and "campo grande" lowercase.

## 4. returns.py (Policy 4, 8)
`return_eligibility(status, order_date, delivery_date, reason, ref_date) -> ReturnDecision`
where reason in {"regret", "preference", "defect"}.
Assumptions (document in docstring):
- delivery_date is the order's estimated_delivery (data has no actual delivery date).
- Day counts are calendar days, deadline inclusive.
- Preference exchange window (7 days) counts from delivery, like regret.
Rules:
- status cancelled -> not eligible ("order cancelled").
- status pending/confirmed/shipped -> not eligible yet ("not delivered"); shipped adds note:
  refuse delivery if damaged (Policy 5.2).
- regret / preference: eligible while ref_date <= delivery + 7. Regret: free return shipping,
  refund in up to 10 business days to the original method. Preference: subject to stock,
  price difference charged or refunded.
- defect: store exchange while ref_date <= order_date + 30; else legal warranty while
  ref_date <= delivery + 90 (store can intermediate); else manufacturer warranty
  (6 months to 2 years, see certificate).
- Always return `conditions` the agent must mention (original packaging, no use, and the
  Policy 4.4 exclusions), since the data cannot tell if they apply.
ReturnDecision: eligible, path ("store_return", "store_exchange", "legal_warranty",
"manufacturer_warranty", None), deadline (date or None), days_left (int or None),
reason_code, conditions (list[str]), policy_section.
Tests: day 7 eligible, day 8 not; defect day 30 store, day 31 legal warranty, day 91
manufacturer; each non-delivered status.

## 5. orders.py
- `delivery_status(status, estimated_delivery, ref_date)` -> "on_time" | "delayed" | None
  (only for shipped; delayed when ref_date > estimated_delivery).
- `total_matches(recorded_total, items)` where items have quantity and current_unit_price ->
  (matches: bool, computed: Decimal). Mismatch is informational: prices may have changed.
Tests with orders 8 (delayed at 2026-03-25), 3 and 20 (mismatch), 15 (match).

## 6. hours.py (Policy 2)
- `is_open(dt: datetime) -> bool`: Mon–Fri 09:00–18:00, Sat 09:00–13:00, Sun closed.
- `next_opening(dt) -> datetime`.
- No holiday calendar (documented limitation).
Tests: Friday 17:59 open, 18:00 closed, Saturday 13:00 closed -> next Monday 09:00.

## 7. README
Fill the "Assumptions" section with this content (adjust only if implementation differs):

```
The data and the policy contain gaps and contradictions. I kept the source files untouched
and resolved each case in code, in the customer's favor when the policy is silent.

- **"Today".** Orders end in March 2026, so the agent uses a configurable `REFERENCE_DATE`
  (default 2026-03-25). Set it to `today` to use the real date.
- **Delivery date.** The data only has `estimated_delivery`; it is treated as the date the
  customer received the order for return and warranty windows.
- **Installments.** The payment table says "minimum R$ 100" while section 3.1 defines tiers.
  Section 3.1 wins as the more specific rule; its "no minimum (except below R$ 50)" for up to
  3x is read as a R$ 50 minimum.
- **Free shipping at exactly R$ 500.** The policy says "above" and "below" R$ 500. Exactly
  R$ 500 ships free.
- **Preference exchanges.** The 7-day window counts from delivery, like the regret window.
- **Metropolitan region.** Only Campo Grande counts; other cities get carrier options and a
  CEP-based quote.
- **Order totals.** Orders 3 and 20 do not match the sum of their items at current prices.
  The data has no historical prices, so the agent reports the recorded total and offers a
  human review instead of correcting it.
- **Contact details.** The manual lists two WhatsApp numbers and a misspelled email. The agent
  uses the WhatsApp channel number from section 7 and the cover email.
```
Commit: `docs(readme): document data and policy assumptions`.

## 8. Finish
ruff check, ruff format, pytest. Show test summary, then merge into develop with --no-ff.
