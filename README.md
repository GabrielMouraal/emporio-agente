# Empório da Música · atendente virtual

Português · [English below](#english)

Este repositório é a minha solução para o desafio técnico de AI Engineer da Artefact. A ideia é um atendente por mensagem para a Empório da Música, uma loja fictícia de instrumentos em Campo Grande (MS). A atendente se chama Lia: ela responde sobre produtos, preços, pedidos e políticas da loja usando os dados do desafio, e não chuta quando não sabe.

Para rodar você precisa de Python 3.10 ou mais novo e de uma chave da OpenAI. Na pasta do projeto:

```bash
python -m venv .venv
source .venv/bin/activate          # no Windows: .venv\Scripts\activate
python -m pip install -e ".[dev,ui]"
cp .env.example .env               # no Windows: copy .env.example .env
```

Depois abra o `.env` e coloque a sua chave em `OPENAI_API_KEY`. O modelo padrão é o `gpt-4o-mini`, e dá para trocar em `OPENAI_MODEL`. Para conversar pelo terminal, rode `python app/cli.py`; com `--debug` aparecem as ferramentas que ela chamou em cada resposta. Se preferir a tela de chat, use `streamlit run app/streamlit_app.py`. Os testes rodam com `python -m pytest` e não precisam de chave nem de internet. No Windows, o pacote `tzdata` entra junto com as dependências porque o sistema não traz a base de fusos horários que o Python usa para saber o horário de Campo Grande.

As conversas de exemplo estão em `conversas/`. São cinco, geradas pelo `python scripts/gerar_conversas.py`, que roda roteiros fixos contra o modelo de verdade e confere se as ferramentas esperadas foram chamadas. Os pedidos da base vão só até março de 2026, então cada roteiro fixa uma data. A variável `EMPORIO_AGORA` faz o mesmo no chat, se você quiser testar um pedido dentro do prazo de devolução.

O código fica em `src/emporio`. O `data.py` carrega os CSVs, o `policies.py` lê as políticas, o `pricing.py` faz as contas de preço, o `tools.py` expõe tudo isso como ferramentas para o modelo, e o `agent.py` cuida da conversa. O `prompts.py` tem a persona e as regras de atendimento.

Usei function calling direto no SDK da OpenAI, sem LangChain ou outro framework. São cinco ferramentas e um loop curto, e assim dá para ler o fluxo inteiro em um arquivo e testar cada parte separada. O modelo decide quando consultar o catálogo, um pedido ou uma política, mas não faz conta nenhuma: preço com promoção, desconto do PIX, parcelamento e prazos de devolução são calculados em Python, com `Decimal`, e chegam para ele já formatados. Isso veio de teste real. Nas primeiras conversas o modelo confundiu a data da compra com a de entrega, escondeu opções da lista e não consultou a política de trocas quando devia. Cada um desses casos virou mudança no código, e o histórico de commits mostra essa sequência.

As políticas vieram de um PDF de oito páginas. Não usei busca vetorial, porque para um documento desse tamanho seria mais peça para manter sem ganho real. O `scripts/extrair_politicas.py` tira o texto do PDF, eu revisei e separei por tema em `data/politicas.md`, e a ferramenta devolve a seção pedida. Um teste confere se todo valor, prazo e horário citado no `.md` aparece também no PDF, para pegar erro de digitação na revisão.

Consultar pedido exige o número e também o e-mail ou o telefone do cadastro, por causa da LGPD. Se não bater, a resposta é a mesma de um pedido que não existe, para não dar pista de quais números são válidos. Os testes do agente usam um cliente falso da OpenAI, então dá para testar o loop, o limite de rodadas, o corte do histórico e a falha da API sem gastar nada.

Os dados têm alguns problemas, e preferi registrar em vez de corrigir por conta própria. O pedido 3 tem total de R$ 3.450,00, mas os itens somam R$ 3.498,00, e ele aparece como entregue com um produto que ainda está em pré-lançamento (Kala KA-ABP-CTG). O pedido 20 tem total de R$ 1.400,00 contra R$ 1.488,00 nos itens. Os pedidos 9 e 16 foram pagos em 6x com parcelas abaixo dos R$ 80,00 que a política exige, e o 18, que acabou cancelado, estava em 12x de R$ 38,32, quando o mínimo nessa faixa é R$ 100,00. O Giannini GF-3D está ativo, mas com estoque zero. As categorias de sopro e de cordas orquestrais existem, mas não têm nenhum produto, enquanto o manual fala em mais de 300 instrumentos. O e-mail bruno.martins@jmail.com aparece em dois clientes. O `Loja().auditar()` lista todos esses casos.

O PDF também se contradiz em alguns pontos. Há dois números de WhatsApp, (67) 3341-4444 e (67) 3321-4500, e o texto de política que a Lia consulta registra os dois em vez de escolher um. A tabela de pagamento diz que a parcela mínima é R$ 100,00, mas a seção 3.1 tem faixas: R$ 50,00 até 3x, R$ 80,00 de 4x a 6x e R$ 100,00 de 7x a 12x. Segui a seção 3.1, que é mais específica, e li o "sem valor mínimo, exceto abaixo de R$ 50,00" como mínimo de R$ 50,00. O frete grátis é para pedidos "acima de R$ 500,00", então um pedido de exatamente R$ 500,00 ainda paga a taxa. A base não tem a data em que o cliente recebeu o pedido, então os prazos de arrependimento e de garantia contam a partir da previsão de entrega.

Tem coisa que ficou de fora ou que funciona só em parte. O filtro de preço usa o preço de tabela, então um produto que só fica abaixo do teto com desconto não aparece na busca. As alternativas para um produto indisponível são escolhidas pela categoria e pelo preço mais próximo, sem olhar especificação, e um violão de aço pode receber como sugestão um de nylon. Feriados não estão no sistema. A conversa vive só na memória do processo, sem banco. O script de conversas confere se uma ferramenta foi chamada, mas não se foi chamada do jeito certo: numa das primeiras execuções o modelo passou um preço no lugar do id do produto, e o script marcou "ok" mesmo assim. Por isso as conversas foram lidas uma a uma. E as respostas do modelo variam de uma execução para outra, então os exemplos mostram um resultado típico, não garantido.

Usei o Claude, da Anthropic, como assistente de programação durante o projeto inteiro. Ele escreveu a maior parte do código e dos testes a partir do que eu pedia, e as escolhas de arquitetura foram discutidas antes de implementar. Rodei tudo na minha máquina e li cada conversa gerada com o modelo real. Foi assim que apareceram o erro de fuso horário no Windows, a confusão entre as datas do pedido e o id inventado, e cada um virou um ajuste. Os commits feitos com ajuda dele carregam a linha `Co-Authored-By`.

<a id="english"></a>

---

**English**

This repository is my solution to Artefact's AI Engineer technical challenge. It is a text-message assistant for Empório da Música, a fictional instrument store in Campo Grande, Brazil. The assistant is called Lia. She answers questions about products, prices, orders and store policies using the challenge data, and she doesn't guess when she doesn't know.

You need Python 3.10 or newer and an OpenAI API key. From the project folder:

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev,ui]"
cp .env.example .env               # Windows: copy .env.example .env
```

Then open `.env` and set `OPENAI_API_KEY`. The default model is `gpt-4o-mini` and can be changed with `OPENAI_MODEL`. To chat in the terminal, run `python app/cli.py`; add `--debug` to see which tools she called for each answer. For the chat UI, use `streamlit run app/streamlit_app.py`. Tests run with `python -m pytest` and need neither a key nor internet access. On Windows, the `tzdata` package is installed with the dependencies because the OS doesn't ship the timezone database Python needs for Campo Grande's local time.

The example conversations are in `conversas/` (in Portuguese, since the store is Brazilian). There are five, generated by `python scripts/gerar_conversas.py`, which runs fixed scripts against the real model and checks that the expected tools were called. The sample orders end in March 2026, so each script pins a date. The `EMPORIO_AGORA` variable does the same in the chat if you want to try an order that is still within the return window.

The code lives in `src/emporio`. `data.py` loads the CSVs, `policies.py` reads the policies, `pricing.py` does the price math, `tools.py` exposes all of that as tools for the model, and `agent.py` runs the conversation. `prompts.py` holds the persona and the service rules.

I used function calling directly through the OpenAI SDK, with no LangChain or other framework. There are five tools and a short loop, so the whole flow reads in one file and every part can be tested on its own. The model decides when to look up the catalog, an order or a policy, but it does no math: promotional prices, the PIX discount, installments and return deadlines are computed in Python with `Decimal` and reach the model already formatted. That came from real testing. In the first conversations the model mixed up the purchase date with the delivery date, hid options from a list and skipped the returns policy when it should have checked it. Each of those became a code change, and the commit history shows that sequence.

The policies came from an eight-page PDF. I didn't use vector search, because for a document this size it would be one more piece to maintain with no real gain. `scripts/extrair_politicas.py` pulls the text out of the PDF, I reviewed it and split it by topic in `data/politicas.md`, and the tool returns the requested section. A test checks that every amount, deadline and time mentioned in the `.md` also appears in the PDF, to catch typos from the manual review.

Looking up an order requires the order number plus the email or phone on file, because of Brazil's data protection law (LGPD). If they don't match, the answer is the same as for an order that doesn't exist, so it gives no hint about which numbers are valid. The agent tests use a fake OpenAI client, so the loop, the round limit, history trimming and API failures are all tested at no cost.

The data has a few problems, and I chose to document them rather than fix them on my own. Order 3 has a total of R$ 3,450.00 while its items add up to R$ 3,498.00, and it is marked as delivered with a product that is still in pre-launch (Kala KA-ABP-CTG). Order 20 has a total of R$ 1,400.00 against R$ 1,488.00 in items. Orders 9 and 16 were paid in 6 installments below the R$ 80.00 minimum the policy requires, and order 18, later cancelled, was set to 12 installments of R$ 38.32 when the minimum for that tier is R$ 100.00. The Giannini GF-3D is active but has zero stock. The wind and orchestral string categories exist but have no products, while the manual mentions over 300 instruments. The email bruno.martins@jmail.com belongs to two customers. `Loja().auditar()` lists all of these.

The PDF also contradicts itself in a few places. It has two WhatsApp numbers, (67) 3341-4444 and (67) 3321-4500, and the policy text Lia reads keeps both instead of picking one. The payment table says the minimum installment is R$ 100.00, but section 3.1 has tiers: R$ 50.00 up to 3x, R$ 80.00 from 4x to 6x and R$ 100.00 from 7x to 12x. I followed section 3.1, which is more specific, and read "no minimum, except below R$ 50.00" as a R$ 50.00 minimum. Free shipping applies to orders "above R$ 500.00", so an order of exactly R$ 500.00 still pays the fee. The data has no actual delivery date, so return and warranty deadlines count from the estimated delivery date.

Some things were left out or only partly work. The price filter uses the list price, so a product that only falls under the limit with a discount won't show up in search. Alternatives for an unavailable product are picked by category and closest price without looking at specs, so a steel-string guitar may get a nylon one as a suggestion. Holidays aren't in the system. The conversation lives only in process memory, with no database. The conversation script checks that a tool was called, not that it was called correctly: in one of the first runs the model passed a price instead of the product id and the script still said "ok". That's why every conversation was read one by one. And model answers vary between runs, so the examples show a typical result, not a guaranteed one.

I used Anthropic's Claude as a coding assistant throughout the project. It wrote most of the code and tests from what I asked for, and the architecture choices were discussed before implementing. I ran everything on my machine and read every conversation generated with the real model. That's how the Windows timezone error, the order date mix-up and the made-up product id surfaced, and each one became a fix. Commits made with its help carry the `Co-Authored-By` line.
