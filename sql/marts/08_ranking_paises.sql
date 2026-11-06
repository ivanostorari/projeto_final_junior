-- Grão: um país com 20 respostas ou mais.
-- Pergunta: em quais países as pessoas mais dizem que o empregador oferece benefícios de saúde mental?
-- HAVING >= 20: um país com 8 respostas no topo do ranking é sorteio, não resultado. O corte é uma
-- escolha (a spec registra por quê); abaixo dele a amostra não sustenta um percentual comparável.
WITH por_pais AS (  -- grão da CTE: um país (com o que for preciso para o ranking)
    SELECT
        r.pais,
        p.continente,
        p.regiao_onu,
        count(*)                                                               AS respondentes,
        round(100.0 * count(*) FILTER (WHERE r.beneficios = 'Sim') / count(*), 1) AS pct_beneficios_sim,
        round(100.0 * count(*) FILTER (WHERE r.tratamento) / count(*), 1)      AS pct_tratamento
    FROM refined.respostas AS r
    LEFT JOIN refined.paises AS p ON p.nome = r.pais
    GROUP BY r.pais, p.continente, p.regiao_onu
    HAVING count(*) >= 20
)
SELECT
    pais,
    continente,
    regiao_onu,
    respondentes,
    pct_beneficios_sim,
    pct_tratamento,
    rank() OVER (ORDER BY pct_beneficios_sim DESC) AS posicao
FROM por_pais
ORDER BY posicao, pais;
