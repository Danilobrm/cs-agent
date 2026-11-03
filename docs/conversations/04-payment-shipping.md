# Payment and shipping

Installments above the allowed maximum, the Campo Grande shipping fee, special freight
and carrier options for another city, and the rule for split payments.

*Model: gemini / gemini-2.5-flash · Reference date: 2026-03-25 · Time: 10:00 (fixed)*

**How to reproduce**

```
uv run cs-agent --script docs/scripts/04-payment-shipping.txt --debug --time 10:00 --transcript docs/conversations/04-payment-shipping.md
```

**Cliente:** Quero o Kala KA-C, dá pra parcelar em 6x?

**Assistente:** Olá! O Ukulele Kala KA-C Concert Mogno está disponível por R$ 349,90.

Para parcelar em 6x, a parcela mínima é de R$ 80,00. Como 6x de R$ 58,32 fica abaixo desse valor, o máximo que consigo para este produto é 4x de R$ 87,48.

O valor à vista no PIX fica R$ 332,41.

<details><summary>Ferramentas (2)</summary>

- `search_products(query='Kala KA-C')` · 19 ms → `{"results":[{"product_id":118,"name":"Kalani KAL-300S Soprano Natural","category":"Ukuleles","availability":"available","stock_quantity":12,"price":"R$ 179,90","promotion":null,"promo_price":null,"pi…`
- `quote_payment(product_ids=[120], installments=6)` · 1 ms → `{"items":[{"product_id":120,"name":"Kala KA-C Concert Mogno","quantity":1,"promotion":null,"list_price":"R$ 349,90","unit_card_price":"R$ 349,90","unit_pix_price":"R$ 332,41"}],"unavailable":[],"card…`

</details>

**Cliente:** E o frete pra Campo Grande?

**Assistente:** Para Campo Grande, o frete para o Ukulele Kala KA-C Concert Mogno fica R$ 35,00, com entrega em 1 a 3 dias úteis.

O frete é grátis para pedidos acima de R$ 500,00.

<details><summary>Ferramentas (1)</summary>

- `quote_shipping(product_ids=[120], city='Campo Grande')` · 0 ms → `{"city":"Campo Grande","order_value":"R$ 349,90","metro":true,"fee":"R$ 35,00","free":false,"needs_cep_quote":false,"special_freight":false,"options":[{"carrier":"Motoboy próprio","delivery_time":"1 …`

</details>

**Cliente:** E se eu levar também uma bateria Yamaha Kit 1 e mandar pra Dourados?

**Assistente:** Certo! A Bateria Acústica Yamaha Kit 1 Studio está disponível por R$ 4.439,00.

Para enviar o Ukulele Kala KA-C Concert Mogno e a Bateria Acústica Yamaha Kit 1 Studio para Dourados, o frete precisa de uma cotação especial, pois a bateria é um instrumento de grande porte.

As opções de envio são:
- PAC (Correios): 5 a 12 dias úteis
- SEDEX (Correios): 2 a 5 dias úteis
- Jadlog (.package): 3 a 8 dias úteis

Todos os envios incluem seguro contra extravios e danos. Para saber o valor exato do frete, preciso do seu CEP.

<details><summary>Ferramentas (2)</summary>

- `search_products(query='bateria Yamaha Kit 1')` · 24 ms → `{"results":[{"product_id":139,"name":"Bateria Acústica Yamaha Kit 1 Studio","category":"Baterias e Percussão","availability":"available","stock_quantity":8,"price":"R$ 4.439,00","promotion":null,"pro…`
- `quote_shipping(product_ids=[120, 139], city='Dourados')` · 1 ms → `{"city":"Dourados","order_value":"R$ 4.788,90","metro":false,"fee":null,"free":false,"needs_cep_quote":true,"special_freight":true,"options":[{"carrier":"PAC (Correios)","delivery_time":"5 a 12 dias …`

</details>

**Cliente:** Posso pagar metade no PIX e metade no cartão?

**Assistente:** Sim, para a compra do Ukulele Kala KA-C Concert Mogno e da Bateria Acústica Yamaha Kit 1 Studio, que totaliza R$ 4.788,90, você pode pagar metade no PIX e metade no cartão.

<details><summary>Ferramentas (1)</summary>

- `quote_payment(product_ids=[120, 139])` · 1 ms → `{"items":[{"product_id":120,"name":"Kala KA-C Concert Mogno","quantity":1,"promotion":null,"list_price":"R$ 349,90","unit_card_price":"R$ 349,90","unit_pix_price":"R$ 332,41"},{"product_id":139,"name…`

</details>
