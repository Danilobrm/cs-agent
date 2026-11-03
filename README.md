# Empório da Música — Customer Service Agent

<!-- One paragraph: what this is, who it serves, the single most important design idea. -->

## Quick start

<!-- Requirements (Python version, API key), install, run CLI, run tests. Copy-pasteable commands only. -->

## How it works

<!-- 5-8 lines + a small diagram: user -> agent loop -> tools -> pandas tables / policy.
     Say what the LLM decides and what code decides. -->

### Tools

| Tool | What it answers | Policy section |
|------|-----------------|----------------|
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

## Technical decisions

<!-- One short subsection per decision: what you chose, why, what you rejected and when you'd switch. -->

### Framework / approach
### LLM
### Retrieval (why no RAG)
### Data access
### Memory and state

## Assumptions

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
- **Special freight.** The policy lists "contrabaixos" among large items that may need an
  individual freight quote, but the catalog uses that word for electric basses too. I only flag
  drums (category 3) and keyboards and pianos (category 4), so a double bass would not be flagged.
- **Warranty after 30 days.** Within 30 days of purchase a defect is exchanged by the store.
  After that the 90-day legal warranty applies and the store can help on request. Once it
  expires, the manufacturer warranty is the only path, and the store has no obligation there.
- **Return conditions.** The data cannot say if a product is unused, in its original packaging
  or a "final sale" item, so the agent always lists these conditions instead of deciding them.
- **Online purchases.** The 7-day regret right is for online purchases, but orders have no
  channel. All delivered orders are treated as eligible.
- **Holidays.** The store is closed on holidays, but there is no holiday calendar, so a holiday
  is reported as open.
- **Conflicting product descriptions.** Several products between 135 and 144 have descriptions that name a
  different brand than the product name (e.g. "Music Man Bass" described as a Fender Jazz Bass)
  and specs that disagree with the text. Name and structured specs are treated as the source of
  truth; a description that mentions another brand is withheld from the agent.
- **Identity check.** Order details are personal data (LGPD, section 9), so the agent asks for
  the order number plus the email or phone on file before showing them. Failures return the same
  message whether the order exists or not, and three failures lead to a human.
- **Value for free shipping.** The R$ 500 threshold uses the price with promotions applied,
  before the PIX discount.

## Example conversations

<!-- 3-5 conversations. One line before each saying what it demonstrates. Full transcripts in docs/conversations.md if long. -->

## Limitations and next steps

<!-- What is out of scope today, and what you'd do with more time or in production. -->

## Use of AI assistants

<!-- Which tools, for what, and what you decided yourself. Be specific and honest. -->
