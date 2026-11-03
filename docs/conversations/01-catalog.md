# Catalog: search, promotions and stock

Search with a price filter and the PIX price, a promotion that already ended, an
out-of-stock product with alternatives, and accessories the store does not sell.

*Model: gemini / gemini-2.5-flash · Reference date: 2026-03-25 · Time: 10:00 (fixed)*

**How to reproduce**

```
uv run cs-agent --script docs/scripts/01-catalog.txt --debug --time 10:00 --transcript docs/conversations/01-catalog.md
```

**Cliente:** Oi! Tô procurando um violão até 800 reais pra começar a estudar

**Assistente:** Opa! Que legal que você quer começar a estudar violão! Temos algumas opções bem bacanas até 800 reais:

- Tagima Memphis AC-39 Nylon Natural por R$ 429,90 (R$ 408,41 no PIX)
- Rozini RC-104 Nylon Estudante por R$ 459,90 (R$ 436,91 no PIX)
- Shelby SN-100 Folk Aço Preto por R$ 549,00 (R$ 521,55 no PIX)
- Giannini GF-1R Aço Folk Sunburst por R$ 579,90 (R$ 550,91 no PIX)
- Yamaha C40 Nylon Natural por R$ 599,90 (R$ 569,91 no PIX)

Qual desses te interessa mais? Se quiser, posso te dar mais detalhes sobre algum deles!

<details><summary>Ferramentas (1)</summary>

- `search_products(only_available=True, max_price=800, category='violão')` · 2 ms → `{"results":[{"product_id":83,"name":"Tagima Memphis AC-39 Nylon Natural","category":"Violões","availability":"available","stock_quantity":15,"price":"R$ 429,90","promotion":null,"promo_price":null,"p…`

</details>

**Cliente:** O Tagima Woodstock ainda tá com aquele desconto de 30% da Black Friday?

**Assistente:** Oi! A promoção de Black Friday para o Tagima Woodstock já terminou. Ele está disponível por R$ 899,00 (ou R$ 854,05 no PIX).

<details><summary>Ferramentas (1)</summary>

- `search_products(only_available=False, query='Tagima Woodstock')` · 16 ms → `{"results":[{"product_id":91,"name":"Tagima Woodstock Dreadnought Natural","category":"Violões","availability":"available","stock_quantity":11,"price":"R$ 899,00","promotion":null,"promo_price":null,…`

</details>

**Cliente:** E o Giannini GF-3D Dreadnought, tem?

**Assistente:** Puxa, o Giannini GF-3D Dreadnought Sunburst está esgotado no momento.

Mas temos algumas alternativas que você pode gostar:

- Giannini GF-1R Aço Folk Sunburst por R$ 579,90 (R$ 550,91 no PIX)
- Giannini GN-15 Nylon Cedr Natural por R$ 689,00 (R$ 654,55 no PIX)
- Shelby SGD-195E Elétrico Aço Sunburst por R$ 799,00 (R$ 759,05 no PIX)
- Tagima Woodstock Dreadnought Natural por R$ 899,00 (R$ 854,05 no PIX)

Qualquer um desses te interessa?

<details><summary>Ferramentas (1)</summary>

- `search_products(query='Giannini GF-3D Dreadnought', only_available=False)` · 22 ms → `{"results":[{"product_id":96,"name":"Giannini GF-3D Dreadnought Sunburst","category":"Violões","availability":"out_of_stock","stock_quantity":0,"price":"R$ 799,90","promotion":null,"promo_price":null…`

</details>

**Cliente:** Beleza. Vocês vendem cordas e afinador também?

**Assistente:** Oi! A gente trabalha exclusivamente com instrumentos musicais, então não vendemos acessórios como cordas e afinadores.
