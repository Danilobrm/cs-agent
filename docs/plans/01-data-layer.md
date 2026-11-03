# 01 · Data layer

Branch `feature/data-layer` from develop. Follow CLAUDE.md git rules.
Goal: load all case data once into clean, typed structures. No business rules, no LLM code.

## Output contract (applies to every accessor)
Accessors return plain Python dicts/lists with NATIVE types only, so results are JSON-safe later:
`int`, `str`, `bool`, `datetime.date`, money as `Decimal` (via `to_money`), `None` for NaN/NaT/empty.
Never leak numpy/pandas types (int64, float64, Timestamp, NaT).

## 1. config.py
- Frozen dataclass `Settings` from .env (python-dotenv, loaded from the project root):
  llm_provider (default "gemini"), llm_model (optional), gemini_api_key, openai_api_key,
  ollama_base_url, data_dir, reference_date (`datetime.date`).
- data_dir default resolves relative to the project root, not the CWD.
- REFERENCE_DATE: ISO date or "today"; default 2026-03-25; invalid value raises a clear error.
- `load_settings()`. Do not validate API keys here.
- Tests for date parsing ("today", ISO, invalid).
- Commit: `feat(config): add settings loaded from environment`

## 2. money.py
- `to_money(value) -> Decimal`, quantized 0.01 ROUND_HALF_UP; accepts float/int/str/Decimal
  (floats via str to avoid binary noise).
- `format_brl(Decimal) -> str` giving `R$ 1.234,56`.
- Tests (e.g. 799.9 -> "R$ 799,90", 11499 -> "R$ 11.499,00", rounding half-up).
- Commit: `feat(money): add decimal money helpers`

## 3. data.py
- `load_store(data_dir) -> Store` reading the six CSVs with pandas.
- Normalize at load: parse dates (order_date, estimated_delivery, created_at); specs JSON -> dict;
  `phone_digits` (digits only, keep original phone); email lowercased/stripped;
  empty tracking_code/notes -> None; is_active -> bool; validate statuses
  (orders: pending, confirmed, shipped, delivered, cancelled;
  products: active, discontinued, coming_soon); unknown value raises.
- `Store` exposes ONLY accessors:
  product(id) (includes category_name), products(), category(id), categories(),
  customer(id), order(id), items_for_order(order_id) (joined with product name and
  `current_unit_price`; the data has no historical item price, name it accordingly),
  promotions_for_product(product_id), active_promotion(product_id)
  (is_active only; if several, highest discount; document in docstring).
- Missing id returns None (or [] for lists), never raises.
- Commit in at least two steps (loading/normalization, then accessors).

## 4. Tests (tests/test_data.py, real data)
- Row counts: 64 products, 50 customers, 20 orders, 22 order_items, 25 promotions, 9 categories.
- Customer 1 phone_digits == "67998123456"; email normalized; product 81 specs is a dict.
- active_promotion(127) is 10%; active_promotion(93) is None; order(999) is None;
  items_for_order(15) has 2 items; order(9)["tracking_code"] is None.
- Every value returned by order(1) and product(81) is a native type (no numpy/pandas).
- Remove tests/test_smoke.py if now redundant.
- Commit: `test(data): cover loading, normalization and accessors`

## 5. Policy text
- `scripts/extract_policy.py`: pypdf extraction of data/policies.pdf to stdout.
- `data/policies.md`: clean markdown of the FULL policy, faithful to the source. Fix only layout
  (headings, markdown tables, bullets, remove page headers/footers/numbers).
  Do NOT fix contradictions or typos (two WhatsApp numbers, installment minimum conflict,
  email with "ó"): keep them exactly as in the source.
- `load_policy(data_dir) -> str` in data.py + test that it contains "Política de Trocas".
- Commit: `feat(policy): add extracted store policy as markdown`

## 6. Stop for review
Run ruff check, ruff format, pytest. STOP before merging: show data/policies.md and test output.
After approval, merge into develop with --no-ff.
