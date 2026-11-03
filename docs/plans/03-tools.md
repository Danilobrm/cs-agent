# 03 · Tools

Branch `feature/tools` from develop. Follow CLAUDE.md. Effort: high.
Goal: the functions the LLM can call, wrapping Store (data) and rules (logic). No LLM code yet.
Tools decide nothing the rules already decide; they fetch, combine, gate and serialize.

## Layout
`src/cs_agent/tools/`: `context.py`, `serialize.py`, `catalog.py`, `orders.py`,
`commerce.py`, `support.py`, `registry.py`. Pure check in `src/cs_agent/rules/catalog.py`.
Tests in `tests/tools/` with the real Store and a fixed `ref_date = 2026-03-25`.
One commit per module with its tests (`feat(tools): ...`).

## 1. context.py
- `Session` (mutable dataclass): `verified_customer_ids: set[int]`, `failed_verifications: int`,
  `handoffs: list[dict]`.
- `ToolContext` (frozen): `store`, `ref_date: date`, `now: datetime`, `session`.
  `now` = REFERENCE_DATE combined with the real current time (documented: hours use the
  simulated day and the real clock).

## 2. serialize.py
`to_json_safe(obj)`: recursively converts dataclasses/dicts/lists/tuples; `Decimal` ->
`format_brl` string ("R$ 1.234,56"); `date` -> "DD/MM/YYYY"; `datetime` -> "DD/MM/YYYY HH:MM".
Every tool result passes through it. Test that `json.dumps` works on every tool's output.

## 3. rules/catalog.py (pure)
- `KNOWN_BRANDS`: Yamaha, Tagima, Giannini, Rozini, Shelby, Crafter, Martin, Taylor, Takamine,
  Kala, Ohana, Kalani, Fender, Gibson, Ibanez, PRS, Music Man, Pearl, Tama, Roland, Korg, Nord.
- `description_conflicts(name, description) -> bool`: True when the description mentions a known
  brand that does not appear in the name (case/accent-insensitive, whole words).
- `availability(status, stock) -> str`: "available" (active, stock > 0), "out_of_stock"
  (active, 0), "discontinued", "coming_soon".
- `normalize_text(s)`: lowercase, strip accents (used for search and city compare).
Tests: 135, 137, 139, 140, 142, 144 conflict; 81, 141, 143, 145 do not.

## 4. catalog.py
Product summary shape (shared): product_id, name, category, availability, stock_quantity,
price (list), promotion ({name, discount_percent} or null), promo_price, pix_price
(from `rules.pricing.price_quote` with the ACTIVE promotion only).

- `search_products(query=None, category=None, max_price=None, min_price=None,
  only_available=False, limit=5)`
  - Accent/case-insensitive token match over name, description, category name and spec values;
    score = matched tokens; sort by score desc, then price asc. Prices filter on the final card
    price (promo applied). limit capped at 10.
  - `category` matched against category names (accent-insensitive, prefix ok: "violao",
    "teclado"). Unknown category -> `{"results": [], "note": "category_not_found",
    "categories": [names]}`. Known category with no products (6, 7, 8) ->
    `note: "category_not_carried"`.
  - Return `{"results": [...], "total_matches": n}`.
- `get_product(product_id)`: summary + specs + description, plus:
  - if `description_conflicts`: description = null and
    `data_warning: "description conflicts with product name; rely on name and specs"`.
  - `past_promotions`: inactive promotions as `{name, discount_percent}` with
    `active: false` (so the agent can say a deal ended, Policy 7.3).
  - if not available: `alternatives` = up to 3 available products from the same category,
    closest final price first.
  - unknown id -> `{"error": "product_not_found"}`.
- `list_active_promotions()`: active promotions as product summaries, sorted by discount desc.

## 5. orders.py (LGPD gate)
- `verify_customer(order_id, email_or_phone)`
  - If the session has 3 failed attempts: `{"verified": false, "error": "too_many_attempts"}`
    and the agent must offer a human.
  - Email: normalized exact match. Phone: digits only, at least 8 digits, match by suffix in
    either direction (handles "+55 67 ...", "(67) ...", or the number without area code).
  - Unknown order OR mismatch -> the same `{"verified": false, "error": "not_matched"}`
    (no enumeration of orders), increments `failed_verifications`.
  - Success: adds the order's customer_id to `verified_customer_ids`; returns
    `{"verified": true, "first_name": ...}` only (no other personal data).
- `get_order(order_id)`: requires the order's customer to be verified, else
  `{"error": "verification_required"}`. Unknown id after verification checks -> the same
  `verification_required` (no enumeration). Returns: order_id, status, order_date, payment
  (human label: "PIX", "Boleto", "Cartão de débito", "Cartão de crédito em 6x"), recorded total,
  items (name, quantity), tracking_code, estimated_delivery, `delivery_status`
  (rules.orders), `total_check` ({matches, computed_at_current_prices}), cancellation_reason
  (notes, cancelled only).
- `check_return_eligibility(order_id, reason)`: same gate; reason in regret|preference|defect
  (invalid -> `{"error": "invalid_reason"}`); wraps `rules.returns.return_eligibility` with
  delivery_date = estimated_delivery.

## 6. commerce.py
Both take `product_ids: list[int]` (repeat an id for quantity) so totals are always computed in
code, never by the model. Unknown or non-purchasable ids (discontinued, coming_soon,
out_of_stock) are returned in `unavailable` and excluded from totals.
- `quote_payment(product_ids, installments=None)`: per-item final price, `card_total`
  (promo applied), `pix_total` (PIX 5% only on items without promotion), `max_installments`
  with installment value, `requested` (`check_installments` when installments given),
  `can_combine_methods`.
- `quote_shipping(city, product_ids)`: order value = card_total (promo applied, before PIX);
  wraps `rules.shipping.shipping_quote` with the items' category ids.

## 7. support.py
- `request_human_handoff(reason, summary)` with reason in complaint|order_issue|other:
  appends to `session.handoffs` with id `ATD-0001`, `ATD-0002`...; returns
  `{ticket_id, sla: "retorno em até 24 horas úteis", store_open_now, next_opening}`
  (rules.hours with `ctx.now`).

## 8. registry.py
- `ToolSpec(name, description, parameters, handler)`. Descriptions in English, precise about
  when to call (e.g. get_order: "Call only after verify_customer succeeded for this order").
- JSON Schemas FLAT and simple (Gemini's OpenAI-compatible layer): types string, integer,
  number, boolean, array of integer; enums for reason fields; no nested objects, no oneOf.
- `openai_tool_schemas()` -> list in OpenAI `{"type": "function", "function": {...}}` format.
- `execute(ctx, name, raw_args) -> dict`: accepts a JSON string or dict; coerces numeric strings
  ("15" -> 15); unknown tool -> `{"error": "unknown_tool"}`; bad args ->
  `{"error": "invalid_arguments", "detail": ...}`; any exception -> `{"error": "tool_failed"}`
  (logged, never raised). Always returns `to_json_safe` output.
Tests: every schema is valid and flat; dispatch errors; numeric coercion.

## 9. Scenario tests (tests/tools/test_scenarios.py)
- get_order(8) before verification -> verification_required; verify with wrong email ->
  not_matched; with customer 2's phone "+55 (67) 99654-7821" -> verified; get_order(8) ->
  delivery_status "delayed".
- 3 failed verifications -> too_many_attempts even with correct data.
- get_product(96) -> out_of_stock with alternatives; get_product(113) -> discontinued;
  get_product(135) -> description null + data_warning; get_product(91) has a past
  Black Friday 30% promotion and no active one.
- search_products(category="sopro") -> category_not_carried.
- quote_payment([127]) -> promo 10%, pix_total == card_total; quote_payment([81]) -> pix 5%.
- quote_shipping("Campo Grande", [127]) -> R$ 35 (323,10 < 500);
  quote_shipping("Dourados", [139]) -> needs CEP quote + special freight.
- check_return_eligibility for a delivered order with regret -> expired at 2026-03-25 window.

## 10. README
Fill "### Tools" under "How it works" with this table (adjust names only if implementation
differs):

```
| Tool | What it answers | Policy |
|------|-----------------|--------|
| `search_products` | Find instruments by text, category or price range | 7.2 |
| `get_product` | Details, stock, current price, ended promotions, alternatives | 6.2, 7.3 |
| `list_active_promotions` | Deals running now, with original and promotional price | 6.2 |
| `verify_customer` | Confirms identity with order id plus email or phone | 9 |
| `get_order` | Status, items, tracking, delays (verified customers only) | 5.3, 9 |
| `check_return_eligibility` | Return, exchange or warranty path and deadline | 4, 8 |
| `quote_payment` | PIX and card totals, installment options | 3, 6.2 |
| `quote_shipping` | Fee and delivery time for a city | 5 |
| `request_human_handoff` | Opens a ticket for complaints and cases the agent cannot solve | 7.3 |

Tools return values that are already computed and formatted. The model chooses which tool to
call and how to phrase the answer; it never does arithmetic, date math or eligibility checks.
```

Append to "## Assumptions":

```
- **Conflicting product descriptions.** Several products between 135 and 144 have descriptions that name a
  different brand than the product name (e.g. "Music Man Bass" described as a Fender Jazz Bass)
  and specs that disagree with the text. Name and structured specs are treated as the source of
  truth; a description that mentions another brand is withheld from the agent.
- **Identity check.** Order details are personal data (LGPD, section 9), so the agent asks for
  the order number plus the email or phone on file before showing them. Failures return the same
  message whether the order exists or not, and three failures lead to a human.
- **Value for free shipping.** The R$ 500 threshold uses the price with promotions applied,
  before the PIX discount.
```
Commit: `docs(readme): document tools and new assumptions`.

## 11. Finish
ruff check, ruff format, pytest. Show the test summary, then merge into develop with --no-ff.
