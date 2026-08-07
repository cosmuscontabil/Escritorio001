---
name: prospeccao-clientes
description: Busca empresas por nicho e raio de distância ao redor de um endereço ou cidade, e monta uma lista de leads para prospecção do escritório contábil (nome da empresa, endereço, telefone e e-mail institucionais, e quando possível o CNPJ e o nome dos sócios/administradores via dados públicos da Receita Federal). Também pode gerar links de busca no LinkedIn para os decisores encontrados. Use quando o usuário pedir para "prospectar clientes", "buscar leads", "captar empresas por nicho", "achar empresas num raio de X km", etc.
---

# Prospecção de clientes por nicho + raio

Gera uma lista de leads (empresas de um nicho, dentro de um raio de um
endereço/cidade) usando só fontes **públicas e gratuitas**:

1. **OpenStreetMap** (Nominatim + Overpass API) — encontra as empresas do
   nicho no raio pedido: nome, endereço, telefone/site quando cadastrados.
2. **BrasilAPI** (espelho de dados abertos da Receita Federal) — quando o
   CNPJ da empresa é encontrado no próprio site dela, busca a razão social,
   o quadro de sócios/administradores (QSA) e telefone/e-mail cadastrados no
   CNPJ. Tudo dado público de registro empresarial (não é dado pessoal
   sensível).
3. **LinkedIn (opcional, sem scraping)** — gera um link de busca pronto
   (`linkedin.com/search/results/people/?keywords=...`) para cada decisor
   encontrado, para você conferir manualmente. **Não** fazemos login nem
   scraping automatizado do LinkedIn: violaria os Termos de Uso deles e
   exigiria burlar a detecção de bots, o que não fazemos.

## Como executar

```bash
python3 .claude/skills/prospeccao-clientes/scripts/buscar_leads.py \
  --nicho "contador" \
  --local "Osasco, SP" \
  --raio 5 \
  --limite 30 \
  --saida leads.csv \
  --enriquecer-cnpj \
  --gerar-linkedin
```

Parâmetros:
- `--nicho`: termo do ramo (ex: `"restaurante"`, `"clinica medica"`,
  `"advogado"`). A lista de nichos já mapeados para categorias do
  OpenStreetMap está em `scripts/nichos.json` — se o nicho pedido não
  estiver lá, o script cai automaticamente para uma busca por palavra no
  nome do estabelecimento (menos precisa, mas funciona).
- `--local`: endereço, bairro ou cidade de referência (ex:
  `"Osasco, SP"`, `"Av. Paulista, São Paulo"`).
- `--raio`: raio em km (padrão 5).
- `--limite`: máximo de empresas retornadas (padrão 30).
- `--enriquecer-cnpj`: tenta achar o CNPJ no site de cada empresa e
  consultar sócios/telefone/e-mail públicos na Receita. Deixa a busca
  mais lenta (uma requisição por empresa), então avalie o `--limite`.
- `--gerar-linkedin`: adiciona uma coluna com links de busca no LinkedIn
  por decisor encontrado.

## O que fazer quando o usuário pedir isso pelo chat

Quando o usuário pedir algo como "busca contadores num raio de 5km em
Osasco" ou "quero prospectar clínicas em São Paulo":

1. Extraia nicho, local e raio do pedido (use os padrões se ele não
   especificar raio/limite).
2. Rode o script via Bash com esses parâmetros, salvando em um CSV no
   diretório de trabalho ou no scratchpad.
3. Leia o CSV gerado e apresente os resultados numa tabela markdown,
   nesta ordem de colunas: Empresa, Endereço, Telefone, E-mail, Decisor(es),
   Cargo. Se não achou decisor/CNPJ para alguma empresa, deixe claro que
   não foi localizado (não invente dado).
4. Se `--gerar-linkedin` foi usado, ofereça os links à parte (não precisa
   colocar todos na tabela principal).
5. Avise, uma vez, o lembrete de LGPD abaixo — não repita a cada busca.

## Limitações e avisos importantes

- **Cobertura do OpenStreetMap varia por região.** Em cidades menores ou
  nichos muito específicos, pode retornar poucos ou nenhum resultado —
  isso é limitação da fonte de dados gratuita, não bug do script.
- **O enriquecimento com CNPJ só funciona se a empresa publica o CNPJ no
  próprio site** (rodapé, política de privacidade etc.). Não há hoje uma
  API pública gratuita de "busca de CNPJ por nome da empresa" — se
  precisar de cobertura maior nesse ponto, a alternativa é um serviço
  pago (ex: Casa dos Dados, Speedio) com busca por CNAE + cidade.
- **LGPD:** os dados automatizados aqui são de registro público/
  institucional (CNPJ é cadastro público; nome de sócio/administrador em
  CNPJ também é público). Ainda assim, ao fazer contato comercial:
  identifique o escritório, explique de onde veio o dado (registro
  público da Receita/CNPJ) e ofereça opção de descadastro. Não use os
  dados para nada além de prospecção B2B razoável.
- **Rede:** o script faz chamadas HTTPS para `nominatim.openstreetmap.org`,
  `overpass-api.de` e `brasilapi.com.br`. Se rodar num ambiente com
  política de rede restrita (alguns sandboxes de CI/cloud bloqueiam
  domínios não listados), essas chamadas podem falhar com erro de
  proxy/403 — nesse caso, rode localmente ou em um ambiente com acesso
  geral à internet.
