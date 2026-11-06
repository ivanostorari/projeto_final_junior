-- Grão: uma faixa etária (a idade só vale de 16 a 80; fora disso a idade é nula em refined).
-- Pergunta: a busca por tratamento muda com a idade?
-- As 8 respostas com idade impossível não somem: ficam na faixa 'sem_idade_valida'.
SELECT
    CASE
        WHEN idade IS NULL THEN 'sem_idade_valida'
        WHEN idade <= 24   THEN 'Até 24'
        WHEN idade <= 34   THEN '25 a 34'
        WHEN idade <= 44   THEN '35 a 44'
        ELSE '45 ou mais'
    END                                                                        AS faixa,
    CASE
        WHEN idade IS NULL THEN 5
        WHEN idade <= 24   THEN 1
        WHEN idade <= 34   THEN 2
        WHEN idade <= 44   THEN 3
        ELSE 4
    END                                                                        AS ordem,
    count(*)                                                                   AS respondentes,
    round(100.0 * count(*) FILTER (WHERE tratamento) / count(*), 1)            AS pct_tratamento,
    round(100.0 * count(*) FILTER (WHERE historico_familiar) / count(*), 1)    AS pct_historico_familiar
FROM refined.respostas
GROUP BY 1, 2
ORDER BY ordem;
