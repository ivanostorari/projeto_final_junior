-- Grão: uma resposta à pergunta "tem histórico familiar de doença mental?" (Sim ou Não).
-- Pergunta: quem tem histórico familiar busca mais tratamento?
SELECT
    CASE WHEN historico_familiar THEN 'Sim' ELSE 'Não' END                     AS historico_familiar,
    count(*)                                                                   AS respondentes,
    round(100.0 * count(*) FILTER (WHERE tratamento) / count(*), 1)            AS pct_tratamento
FROM refined.respostas
GROUP BY historico_familiar
ORDER BY historico_familiar DESC;
