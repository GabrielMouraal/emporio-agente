# Busca de violões por faixa de preço

**Objetivo:** Pergunta do enunciado. Deve consultar o catálogo, mostrar só itens disponíveis e ajudar a filtrar.
**Momento simulado:** 18/03/2026 10:30 (Campo Grande) · **Modelo:** gpt-4o-mini

---

**Cliente:** Oi! Quais opções de violões disponíveis custando até R$1000?

> `buscar_produtos({"categoria": "violões", "preco_max": 1000})`

**Lia:** Tenho 12 violões até R$ 1.000. Separei os 5 mais em conta:

- Tagima Memphis AC-39 Nylon Natural: R$ 429,90 (R$ 408,41 no PIX)
- Rozini RC-104 Nylon Estudante: R$ 459,90 (R$ 436,91 no PIX)
- Shelby SN-100 Folk Aço Preto: R$ 549,00 (R$ 521,55 no PIX)
- Giannini GF-1R Aço Folk Sunburst: R$ 579,90 (R$ 550,91 no PIX)
- Yamaha C40 Nylon Natural: R$ 599,90 (R$ 569,91 no PIX)

Valores no cartão, débito ou boleto; o PIX tem 5% de desconto. 

Se precisar de mais alguma informação ou quiser filtrar por tipo de corda, é só avisar! 🎸

**Cliente:** Prefiro nylon, é pro meu filho que tá começando

> `buscar_produtos({"categoria": "violões", "termo": "nylon", "preco_max": 1000})`

**Lia:** Aqui estão as opções de violões de nylon para iniciantes:

- Tagima Memphis AC-39 Nylon Natural: R$ 429,90 (R$ 408,41 no PIX)
- Rozini RC-104 Nylon Estudante: R$ 459,90 (R$ 436,91 no PIX)
- Yamaha C40 Nylon Natural: R$ 599,90 (R$ 569,91 no PIX)
- Giannini GN-15 Nylon Cedr Natural: R$ 689,00 (R$ 654,55 no PIX)
- Yamaha C70 Nylon Natural: R$ 849,00 (R$ 806,55 no PIX)

Valores no cartão, débito ou boleto; o PIX tem 5% de desconto. Algum desses chamou a atenção? 🎶
