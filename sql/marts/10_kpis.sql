-- Grão: a pesquisa inteira (uma linha), os seis cartões do painel.
-- pct_falaria_supervisor = "falaria de um problema de saúde mental com o supervisor direto?" = Sim.
-- Pergunta: qual é o retrato geral das pessoas que responderam?
-- Todos os percentuais são "% das pessoas que responderam", nunca "% dos profissionais de tecnologia".
SELECT
    count(*)                                                                         AS respondentes,
    round(100.0 * count(*) FILTER (WHERE tratamento) / count(*), 1)                  AS pct_tratamento,
    round(100.0 * count(*) FILTER (WHERE historico_familiar) / count(*), 1)          AS pct_historico_familiar,
    round(100.0 * count(*) FILTER (WHERE beneficios = 'Sim') / count(*), 1)          AS pct_beneficios_sim,
    round(100.0 * count(*) FILTER (WHERE consequencia_saude_mental = 'Sim') / count(*), 1)
                                                                                     AS pct_receio_consequencia,
    round(100.0 * count(*) FILTER (WHERE falaria_supervisor = 'Sim') / count(*), 1) AS pct_falaria_supervisor
FROM refined.respostas;
