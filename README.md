# Empório da Música — Customer Service Agent

A customer service agent for Empório da Música, a musical instrument store in Campo Grande.
It answers questions about products, prices, promotions, orders, shipping, payment and returns
in Brazilian Portuguese, using the store's catalog, orders and policy manual. Everything that
must be exact (prices, discounts, installments, deadlines, eligibility, identity checks) is
computed in code; the language model only understands the customer and writes the answer.

## Quick start

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

    git clone https://github.com/Danilobrm/cs-agent.git
    cd cs-agent
    uv sync
    cp .env.example .env    # add GEMINI_API_KEY (free at https://aistudio.google.com/apikey)
    uv run cs-agent

Useful options:

    uv run cs-agent --debug                 # show every tool call and its result
    uv run cs-agent --date 2026-02-05       # simulate another "today" (default 2026-03-25)
    uv run cs-agent --time 10:00            # pin the clock (opening hours)
    uv run cs-agent --provider ollama --model qwen2.5:7b    # local model, no key
    uv run cs-agent --script docs/scripts/01-catalog.txt --debug --transcript out.md

Check the provider with `uv run python scripts/check_llm.py`. The tests need no API key:
`uv run pytest`.

In the chat: `/ajuda` lists commands, `/reset` starts a new conversation, `/debug` toggles the
tool trace, `/sair` exits. Errors are logged to `cs-agent.log`.

## How it works

The agent is a function-calling loop. Each customer message goes to the model together with
the conversation history, the system prompt and the tool definitions. The model either answers
or asks for tools; tools run in Python and their results go back to the model until it writes
the reply.

    customer --> CLI --> agent loop --> LLM (Gemini, Ollama or OpenAI)
                            |   ^
                   tool calls   results
                            v   |
                          tools --> rules  (prices, installments, shipping, returns, hours)
                            |
                            +-----> store  (CSV data loaded in memory)

The split of responsibilities is the core design decision. The model understands the request,
picks tools and writes the answer in the store's tone. Code does everything that must be
exact: prices, PIX discounts, installment limits, shipping, return and warranty deadlines,
stock and identity checks. Policy 7.1 says the assistant must never state prices, stock or
deadlines without checking the system, so the agent is built so that it cannot.

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
Function calling over structured data, with the full policy in the system prompt. I wrote the
loop directly on the `openai` SDK instead of using LangChain or an agent framework: it is about
a hundred lines, every step is visible, and there is nothing to configure. The loop has a cap on
tool rounds, a time limit and a fallback reply, so the customer always gets an answer even when
the model or the API fails.

### LLM

### Retrieval (why no RAG)
The policy is about 1,800 words (around 3k tokens), so it goes whole into the system prompt.
With the full text always present there is no retrieval step that can miss the right section,
and answers that combine sections (a return that touches the regret window, defects and
warranty) stay correct. Structured data is served by tools, because exact lookups beat semantic
search for "order 8" or "price of product 127". The prompt puts static content first and the
current date last, so providers that cache prompt prefixes reuse the policy on every call.
I would add retrieval if the knowledge base grew to many documents or long manuals, starting
with section-level search, and semantic search inside `search_products` for vague requests
over a large catalog.

### Data access
The CSVs are loaded once into memory with the standard `csv` module and exposed through a small
`Store` with typed accessors. At this size a database or a SQL agent would add moving parts
without benefit; in production the same accessors would query a database and the tools would not
change. Letting the model write SQL was ruled out: it would put arithmetic and filtering back
in the model's hands.

### Memory and state
Conversation history lives in memory for the CLI session; `/reset` clears it. A support chat is
a session, and persisting it would mean storing personal data (LGPD) with no gain for this case.
The session also holds which customers were verified, so a customer is asked for their details
once per conversation.

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
