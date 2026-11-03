# 01b · Data layer fixes (before merging 01)

Stay on `feature/data-layer` (not merged yet). Follow CLAUDE.md git rules.

## 1. Commit the pending CLAUDE.md edit
The author already corrected dataset figures in CLAUDE.md (65 products, ~1.8k words).
Commit it alone: `docs: correct dataset figures in project guidance`.

## 2. Accessors must not leak internal state
Today `order()`, `customer()`, `category()`, `categories()` return the stored dicts themselves,
and products share the same `specs` dict. A caller mutating a result corrupts the store.
- Every accessor returns deep copies (`copy.deepcopy`; data is tiny).
- Tests: mutate a returned order, customer, and a product's `specs`; the next accessor call
  returns the original values.
- Commits: `test(data): ensure accessor results are isolated copies` then
  `fix(data): return copies from store accessors` (test first is fine, or one fix commit with tests).

## 3. Replace pandas with the stdlib csv module
pandas is only used for `read_csv` before converting to dicts: an unnecessary heavy dependency.
- `_records` uses `csv.DictReader` (utf-8). Values arrive as strings: convert explicitly in the
  normalizers (ids, quantity, stock_quantity, category_id, customer_id, product_id,
  discount_percent -> int; is_active "1"/"0" -> bool; empty string -> None).
- Remove `_native` and all numpy/pandas handling. Keep the native-types contract and its test.
- `uv remove pandas`, update uv.lock.
- CLAUDE.md: replace pandas mentions with "in-memory dicts loaded with the csv module";
  the "no numpy/pandas types" rule becomes "native Python types only".
- All existing tests must pass unchanged in intent.
- Commit: `refactor(data): load CSVs with the csv module and drop pandas`
  (CLAUDE.md change in a separate `docs:` commit).

## 4. Finish
ruff check, ruff format, pytest. Show the diff summary and test output, then merge
feature/data-layer into develop with --no-ff. Show `git log --oneline --graph -15`.
