# Contrato físico sla_orcamento — versão 5

Origem: Monday; tratamento e joins em Python. Grão: uma passagem de projeto por status.
Chave: interval_id; unicidade também em board_id + item_id + ordem_etapa.
Consumidores: BigQuery/Power BI. Falha de contrato bloqueia carga inteira; preserva publicação anterior.
Horas desconhecidas ficam NULL. Horas úteis: seg-sex 10–13h / 14–19h, America/Sao_Paulo;
feriados BR PUBLIC automáticos e BUSINESS_HOLIDAYS adicionais. Sem metas de prazo.

| Campo | Tipo lógico | Obrigatório |
|---|---|---|
| `ordem_etapa` | int | Sim |
| `projeto_nome` | text | Sim |
| `status_nome` | text | Sim |
| `entrada_status_local` | localtime | Não |
| `saida_status_local` | localtime | Não |
| `duracao_horas` | num | Não |
| `marca_nome` | text | Não |
| `talento_nome` | text | Não |
| `responsavel_orcamento` | text | Não |
| `eh_retorno` | bool | Sim |
| `item_id` | id | Sim |
| `board_id` | id | Sim |
| `interval_id` | text | Sim |
| `qualidade_historico` | text | Sim |
| `intervalo_aberto` | bool | Sim |
| `status_final` | bool | Sim |
| `corte_local` | localtime | Sim |
| `elegivel_comparacao` | bool | Sim |
| `horas_observadas_encerradas` | num | Não |
| `status_atual_nome` | text | Sim |
| `projeto_na_fila` | bool | Sim |
| `tempo_desde_entrada_horas` | num | Não |
| `tempo_status_atual_horas` | num | Não |
| `responsavel_situacao` | text | Sim |
| `cadastro_referencia_utc` | time | Não |
| `versao_regras` | text | Sim |
| `item_sk` | text | Sim |
| `board_sk` | text | Sim |
| `status_id` | text | Sim |
| `status_sk` | text | Sim |
| `entrada_status_utc` | time | Não |
| `saida_status_utc` | time | Não |
| `corte_utc` | time | Sim |
| `duracao_horas_uteis` | num | Não |
| `horas_uteis_observadas_encerradas` | num | Não |
| `tempo_status_atual_horas_uteis` | num | Não |
| `tempo_desde_entrada_horas_uteis` | num | Não |
| `expediente` | text | Sim |
| `versao_calendario` | text | Sim |
