-- Grão: um tipo de saúde (mental ou física).
-- Pergunta: as pessoas temem mais as consequências de falar de saúde mental do que de saúde física?
-- Duas perguntas diferentes, em colunas separadas de propósito, porque o "Sim" NÃO significa a mesma coisa:
--   receio_*    = "acha que discutir o assunto com o empregador teria consequências NEGATIVAS?" (Sim = receio)
--   entrevista_* = "levaria o assunto a um empregador em potencial, numa entrevista?"   (Sim = disposição)
-- Misturar as duas numa coluna só faria "Sim" querer dizer coisas opostas. Denominador: todas as respostas.
WITH longo AS (  -- grão da CTE: uma pessoa × um tipo de saúde
    SELECT 'Saúde mental' AS saude, 1 AS ordem,
           consequencia_saude_mental AS receio, falaria_entrevista_mental AS entrevista
    FROM refined.respostas
    UNION ALL
    SELECT 'Saúde física', 2, consequencia_saude_fisica, falaria_entrevista_fisica
    FROM refined.respostas
)
SELECT
    saude,
    ordem,
    count(*)                                                                    AS respondentes,
    round(100.0 * count(*) FILTER (WHERE receio = 'Sim') / count(*), 1)         AS pct_receio_sim,
    round(100.0 * count(*) FILTER (WHERE receio = 'Talvez') / count(*), 1)      AS pct_receio_talvez,
    round(100.0 * count(*) FILTER (WHERE receio = 'Não') / count(*), 1)         AS pct_receio_nao,
    round(100.0 * count(*) FILTER (WHERE entrevista = 'Sim') / count(*), 1)     AS pct_entrevista_sim,
    round(100.0 * count(*) FILTER (WHERE entrevista = 'Talvez') / count(*), 1)  AS pct_entrevista_talvez,
    round(100.0 * count(*) FILTER (WHERE entrevista = 'Não') / count(*), 1)     AS pct_entrevista_nao
FROM longo
GROUP BY saude, ordem
ORDER BY ordem;
