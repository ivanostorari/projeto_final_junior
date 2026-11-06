-- Grão: uma faixa de tamanho da empresa (número de funcionários).
-- Pergunta: empresas maiores oferecem mais benefícios e facilitam mais a licença?
-- As faixas vêm da pesquisa como estão ('26-100' e '100-500' dividem o valor 100: é da fonte).
SELECT
    tamanho_empresa                                                            AS faixa,
    CASE tamanho_empresa
        WHEN '1-5' THEN 1 WHEN '6-25' THEN 2 WHEN '26-100' THEN 3
        WHEN '100-500' THEN 4 WHEN '500-1000' THEN 5 ELSE 6 END                AS ordem,
    count(*)                                                                   AS respondentes,
    round(100.0 * count(*) FILTER (WHERE beneficios = 'Sim') / count(*), 1)    AS pct_beneficios_sim,
    round(100.0 * count(*) FILTER (WHERE licenca IN ('Muito fácil', 'Um pouco fácil')) / count(*), 1)
                                                                               AS pct_licenca_facil,
    round(100.0 * count(*) FILTER (WHERE tratamento) / count(*), 1)            AS pct_tratamento
FROM refined.respostas
GROUP BY tamanho_empresa
ORDER BY ordem;
