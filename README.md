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
|      |                 |                |

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

## Example conversations

<!-- 3-5 conversations. One line before each saying what it demonstrates. Full transcripts in docs/conversations.md if long. -->

## Limitations and next steps

<!-- What is out of scope today, and what you'd do with more time or in production. -->

## Use of AI assistants

<!-- Which tools, for what, and what you decided yourself. Be specific and honest. -->
