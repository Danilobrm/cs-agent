# First run of the example scripts

The first run of the six scripts in `docs/scripts/` on Gemini (gemini-2.5-flash, temperature
0.2, reference date 2026-03-25, time pinned at 10:00) broke 9 rules. No reply was the fallback
message, so these are behavior problems, not infrastructure errors. The fixes are listed below
the table; after them the scripts were run again.

| Script | Turn | What happened | Rule broken | Fix |
|--------|------|---------------|-------------|-----|
| 04-payment-shipping | 1 | Said the Kala KA-C can be paid "em até 6x sem juros, com parcelas mínimas de R$ 80,00" without calling `quote_payment`. The real maximum for R$ 349,90 is 4x. | Made-up installment option | B |
| 05-edge-cases | 4 | Asked about saxophones, said the store has "flautas, clarinetes e trompetes". Both wind categories have no products; the names came from the category descriptions. | Made-up stock | E, G |
| 05-edge-cases | 3 | Answered "A capital da França é Paris!" | Off-topic question answered | D |
| 02-order-tracking | 3 | After a successful `verify_customer`, said "Só um instante enquanto eu verifico o status" and ended the turn without calling `get_order`. | Turn ends promising a check | A |
| 02-order-tracking | 4 | Opened a handoff ticket for the delay without ever calling `get_order`; the delay came from the customer, not from the data. | Order status not verified | A |
| 03-returns, 03b-returns-expired | 2 | After verification, asked again whether it was regret or a defect, although the customer had said it. `check_return_eligibility` was never called, so no deadline or days left. | Asks instead of calling the tool | A |
| 03-returns | 3 | "Depois do prazo de 30 dias… garantia do fabricante", with no tool call. Follows the policy text literally and skips the 90-day legal warranty that the code applies. | Not grounded; contradicts the tool | B, H, I |
| 01-catalog | 3 | Searched the Giannini GF-3D with `only_available=True`, which hid it, then said it "não está disponível" without knowing why. Alternatives came from that search, not from `get_product`. | Availability guessed | C |
| 01-catalog, 04-payment-shipping | 1, 3 | Markdown bold and `*` bullets in a chat channel; no PIX price in the first product list. | Format (minor) | F |

## Fixes

- **A. Act, do not ask.** When the conversation already has what a tool needs, call it in the
  same turn; never end a turn saying a check will happen. "Me arrependi" maps to regret and
  "deu defeito" to defect.
- **B. Policy numbers are rules, not answers.** To say what applies to a product or order,
  call the tool.
- **C. Named products.** Look a named product up without `only_available`.
- **D. Off-topic.** Do not answer at all, then offer help with the store.
- **E. What the store carries.** Never say the store carries a type of product unless a tool
  returned it; category names are not stock.
- **F. No markdown.** No bold or headings; a plain "-" list is fine.
- **G. Category search.** `search_products` also matches category descriptions, so
  "saxofone" returns `category_not_carried` instead of the list of category names.
- **H. Next warranty stage.** For defects, `check_return_eligibility` also returns
  `next_path` and `next_deadline`, so "what if the defect shows up later?" has a computed
  answer.
- **I. Tool over policy text.** The policy explains the rules, but tool results carry the
  store's interpretation; when they differ, say what the tool returned.
- **J. Temperature 0** for reproducible transcripts and checks.
