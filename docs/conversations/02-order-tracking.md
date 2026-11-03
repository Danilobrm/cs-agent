# Order tracking with identity check

The identity gate (LGPD), no data leak after a failed check, verification by phone,
delay detection, a handoff ticket, and refusal to show another customer's order.

*Model: gemini / gemini-2.5-flash · Reference date: 2026-03-25 · Time: 10:00 (fixed)*

**How to reproduce**

```
uv run cs-agent --script docs/scripts/02-order-tracking.txt --debug --time 10:00 --transcript docs/conversations/02-order-tracking.md
```

**Cliente:** Oi, meu pedido 8 ainda não chegou

**Assistente:** Olá! Para eu verificar seu pedido, preciso que me informe também o e-mail ou telefone que você usou na compra, por favor.

**Cliente:** ana.ferreira@gmail.com

**Assistente:** Não consegui encontrar seu pedido com os dados informados. Por favor, verifique se o número do pedido e o e-mail estão corretos. Se precisar, posso te ajudar a falar com um de nossos atendentes.

<details><summary>Ferramentas (1)</summary>

- `verify_customer(order_id=8, email_or_phone='ana.ferreira@gmail.com')` · 0 ms → `{"verified":false,"error":"not_matched"}`

</details>

**Cliente:** Desculpa, é (67) 99654-7821

**Assistente:** Ana, seu pedido 8, do Ukulele Kala KA-C Concert Mogno, está com 25 dias de atraso na entrega. Ele foi enviado em 15/02/2026 e a previsão de entrega era 28/02/2026.

O código de rastreamento é BRJL5544332BR.

Se você quiser, posso abrir um chamado para um de nossos atendentes verificar o que aconteceu com a entrega.

<details><summary>Ferramentas (2)</summary>

- `verify_customer(email_or_phone='(67) 99654-7821', order_id=8)` · 0 ms → `{"verified":true,"first_name":"Ana"}`
- `get_order(order_id=8)` · 1 ms → `{"order_id":8,"status":"shipped","order_date":"15/02/2026","payment":"Cartão de débito","total":"R$ 349,90","items":[{"name":"Kala KA-C Concert Mogno","quantity":1}],"tracking_code":"BRJL5544332BR","…`

</details>

**Cliente:** Já passou muito da data, quero falar com alguém

**Assistente:** Ana, abri um chamado para você com o número ATD-0001. Um de nossos atendentes entrará em contato em até 24 horas úteis para te ajudar com a entrega do seu pedido.

<details><summary>Ferramentas (1)</summary>

- `request_human_handoff(summary='Cliente com pedido 8 atrasado em 25 dias, quer falar com um atendente para resolver a entrega.', reason='order_issue')` · 0 ms → `{"ticket_id":"ATD-0001","sla":"retorno em até 24 horas úteis","store_open_now":true,"next_opening":null}`

</details>

**Cliente:** E o pedido 1, de quem é?

**Assistente:** Para eu verificar o pedido 1, preciso que me informe também o e-mail ou telefone que você usou na compra, por favor.
