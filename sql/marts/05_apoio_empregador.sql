-- Grão: uma pergunta de apoio do empregador × uma resposta (ex.: 'beneficios' × 'Sim').
-- Pergunta: o que as pessoas dizem saber sobre o apoio que o empregador oferece, e quem diz que
-- existe apoio busca mais tratamento? (Correlação na amostra; não diz que o apoio causa o tratamento.)
-- O denominador é sempre o total de respostas; quem respondeu 'Não sei' fica no denominador, porque
-- "não saber que existe" já é um resultado sobre o apoio.
WITH longo AS (  -- grão da CTE: uma pessoa × uma das cinco perguntas
    SELECT 'beneficios'         AS pergunta, beneficios         AS resposta, tratamento FROM refined.respostas
    UNION ALL
    SELECT 'opcoes_cuidado',     opcoes_cuidado,     tratamento FROM refined.respostas
    UNION ALL
    SELECT 'programa_bem_estar', programa_bem_estar, tratamento FROM refined.respostas
    UNION ALL
    SELECT 'recursos_ajuda',     recursos_ajuda,     tratamento FROM refined.respostas
    UNION ALL
    SELECT 'anonimato',          anonimato,          tratamento FROM refined.respostas
)
SELECT
    pergunta,
    resposta,
    CASE resposta WHEN 'Sim' THEN 1 WHEN 'Não' THEN 2 ELSE 3 END               AS ordem,
    count(*)                                                                   AS respondentes,
    round(100.0 * count(*) / sum(count(*)) OVER (PARTITION BY pergunta), 1)    AS pct_das_respostas,
    round(100.0 * count(*) FILTER (WHERE tratamento) / count(*), 1)            AS pct_tratamento
FROM longo
GROUP BY pergunta, resposta
ORDER BY pergunta, ordem, resposta;
