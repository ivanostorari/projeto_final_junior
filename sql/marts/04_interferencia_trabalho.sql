-- Grão: uma resposta à pergunta "a condição de saúde mental interfere no seu trabalho?".
-- Pergunta: com que frequência interfere, e como isso se relaciona com ter buscado tratamento?
-- As 264 respostas nulas viram 'sem_resposta' (a pergunta só faz sentido para quem tem uma condição;
-- 260 delas são de quem não buscou tratamento, mas isso é hipótese e não está no dado).
SELECT
    coalesce(interferencia_trabalho, 'sem_resposta')                           AS interferencia,
    CASE interferencia_trabalho
        WHEN 'Nunca' THEN 1 WHEN 'Raramente' THEN 2 WHEN 'Às vezes' THEN 3
        WHEN 'Frequentemente' THEN 4 ELSE 5 END                                AS ordem,
    count(*)                                                                   AS respondentes,
    round(100.0 * count(*) / sum(count(*)) OVER (), 1)                         AS pct_das_respostas,
    round(100.0 * count(*) FILTER (WHERE tratamento) / count(*), 1)            AS pct_tratamento
FROM refined.respostas
GROUP BY interferencia_trabalho
ORDER BY ordem;
