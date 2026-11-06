-- Grão: um continente (o continente do país informado pela pessoa, via refined.paises).
-- Pergunta: de onde vêm as respostas, e o quanto o perfil muda de um continente para outro?
-- Contexto, não conclusão: quase tudo vem de um lugar só, e é isso que o indicador deixa visível.
-- LEFT JOIN: país sem cadastro continua contando (como 'sem_cadastro'); a chave de paises é única,
-- então o JOIN não multiplica linhas (conferido no teste e na spec).
SELECT
    coalesce(p.continente, 'sem_cadastro')                                     AS continente,
    count(*)                                                                   AS respondentes,
    round(100.0 * count(*) / sum(count(*)) OVER (), 1)                         AS pct_das_respostas,
    round(100.0 * count(*) FILTER (WHERE r.tratamento) / count(*), 1)          AS pct_tratamento,
    round(100.0 * count(*) FILTER (WHERE r.historico_familiar) / count(*), 1)  AS pct_historico_familiar
FROM refined.respostas AS r
LEFT JOIN refined.paises AS p ON p.nome = r.pais
GROUP BY 1
ORDER BY respondentes DESC, continente;
