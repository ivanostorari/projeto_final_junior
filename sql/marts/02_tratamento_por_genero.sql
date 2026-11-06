-- Grão: um grupo de gênero (Homem, Mulher, Outras identidades, Não informado).
-- Pergunta: a proporção de quem buscou tratamento muda com o gênero?
-- Cuidado: 'Outras identidades' e 'Não informado' têm menos de 20 respostas; o percentual
-- está aqui, mas o painel mostra o n ao lado e avisa.
SELECT
    genero,
    CASE genero WHEN 'Homem' THEN 1 WHEN 'Mulher' THEN 2 WHEN 'Outras identidades' THEN 3 ELSE 4 END AS ordem,
    count(*)                                                                   AS respondentes,
    round(100.0 * count(*) FILTER (WHERE tratamento) / count(*), 1)            AS pct_tratamento,
    round(100.0 * count(*) FILTER (WHERE historico_familiar) / count(*), 1)    AS pct_historico_familiar
FROM refined.respostas
GROUP BY genero
ORDER BY ordem;
