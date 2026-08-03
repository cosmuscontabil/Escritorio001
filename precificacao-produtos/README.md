# Modelo de Precificação de Produtos

Planilha (`Modelo_Precificacao_Produtos.xlsx`) para calcular preço de venda considerando
regime tributário, impostos (inclusive IBS/CBS da Reforma Tributária) e margem desejada.

## Como usar

1. Abra a aba **Precificação**. Cada linha é um produto.
2. Preencha os campos em **azul**: custo, regime tributário, alíquotas dos impostos que
   incidem sobre o produto e as 3 margens desejadas (mínima, ideal, otimizada).
3. Os campos em **preto** são calculados automaticamente: custo total, carga tributária
   total e os 3 preços sugeridos.
4. A linha 5 (fundo amarelo) é um exemplo preenchido — pode apagar ou usar de referência.
5. Se carga tributária + margem chegar a 100% ou mais, o preço mostra "Inviável" (a conta
   não fecha e a margem precisa ser revista).

A aba **Instruções** explica a fórmula usada, qual campo preencher por regime (Simples
Nacional Regular/Híbrido, Lucro Presumido, Lucro Real) e traz uma tabela de referência das
alíquotas vigentes em 2026 (ano-teste do IBS/CBS).

Revisar as alíquotas de referência todo início de ano — a Reforma Tributária muda os
percentuais de CBS/IBS e reduz ICMS/ISS gradualmente até 2033.
