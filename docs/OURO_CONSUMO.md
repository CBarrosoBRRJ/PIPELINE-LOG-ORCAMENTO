# Dicionário de sla_orcamento — contrato GCP 5

BigQuery publica somente `gglobo-viu-dados-hdg-prd.viu_agenciamento.sla_orcamento`. Todos os joins, cadastros, regras e cálculos são feitos em Python. Uma linha = uma passagem de projeto por status; projetos que retornam a um status possuem outra linha com eh_retorno=true. Não é uma linha por projeto nem por dia. Ordene por item_id, ordem_etapa. Contrato gerado: [CONTRATO_SLA_ORCAMENTO.md](CONTRATO_SLA_ORCAMENTO.md).

O histórico de passagens é preservado na tabela atualizada, mas ela não armazena cópias diárias da publicação. Corte D+1 vale para tempos; cadastro_referencia_utc pode ser posterior ao corte. As durações não comprovadas são NULL (não zero). Intervalo fora do expediente pode ter zero hora útil e duração corrida positiva.

## Campos de horas úteis adicionados em GCP

| Campo | Unidade/nulabilidade | Significado |
|---|---|---|
| duracao_horas_uteis | horas, nullable | Permanência desta passagem dentro do expediente até saída ou corte |
| horas_uteis_observadas_encerradas | horas, nullable | Horas úteis somente em passagem elegível para comparação; média/mediana de encerradas |
| tempo_status_atual_horas_uteis | horas, nullable | Tempo útil na última etapa comprovada; repetido nas linhas do projeto, consumir MAX por projeto |
| tempo_desde_entrada_horas_uteis | horas, nullable | Tempo útil desde Entrada comprovada até finalização/corte; repetido, consumir MAX por projeto |
| expediente | STRING, obrigatório | seg-sex 10:00-13:00 / 14:00-19:00 |
| versao_calendario | STRING, obrigatório | Identifica política, fuso, versão holidays e feriados adicionais |

Calendário: America/Sao_Paulo, 8h/dia de trabalho, sábados/domingos excluídos. Nacionais gerados automaticamente por ano (`holidays`, BR PUBLIC), incluindo Sexta-feira da Paixão e 20/11 a partir de 2024 conforme a biblioteca. Carnaval e Corpus Christi ficam fora da exclusão automática. `BUSINESS_HOLIDAYS` adiciona locais/recessos. Datas efetivas usadas ficam em calendario.json da publicação. Atualizações legais futuras exigem atualização testada da biblioteca e replay; não há consulta anual a uma API externa.

Exemplos: 12h30–14h30 de dia útil = 1h útil; sexta 18h até segunda 11h = 2h úteis se segunda não for feriado. Nenhuma meta de prazo está definida.

Os 33 campos abaixo permanecem no consumo e seis campos úteis são acrescentados: total 39. Datas UTC são TIMESTAMP, datas locais DATETIME, IDs INT64, números FLOAT64, flags BOOL e textos STRING no BigQuery.

## Campos base de sla_orcamento

| Campo | Tipo | Aceita NULL | Descrição |
|---|---|---|---|
| `ordem_etapa` | int | Não | Sequência temporal dentro do projeto, iniciando em 1. |
| `projeto_nome` | text | Não | Nome cadastral do projeto na coleta. |
| `status_nome` | text | Não | Status deste trecho, não necessariamente o status atual. |
| `entrada_status_local` | localtime | Sim | Início comprovado, em São Paulo; NULL se não comprovado. |
| `saida_status_local` | localtime | Sim | Transição de saída conhecida; NULL na última passagem. |
| `duracao_horas` | num | Sim | Horas corridas comprovadas; NULL para trecho inferido. |
| `marca_nome` | text | Sim | Marca normalizada ou aprovada no catálogo; não se deduplica por similaridade. |
| `talento_nome` | text | Sim | Pessoa individual elegível conforme cadastro/revisão. |
| `responsavel_orcamento` | text | Sim | Pessoa(s) na coluna Orçamento; nomes técnicos inválidos não são publicados. |
| `eh_retorno` | bool | Não | True na segunda ou posterior passagem pelo mesmo status. |
| `item_id` | id | Não | ID original do item/projeto Monday, repetido entre suas passagens. |
| `board_id` | id | Não | ID original do quadro Monday. |
| `interval_id` | text | Não | Chave única da passagem. |
| `qualidade_historico` | text | Não | observed, initial_inferred ou no_history_inferred. |
| `intervalo_aberto` | bool | Não | Última passagem, ainda sem evento de saída no corte; não significa necessariamente projeto aberto. |
| `status_final` | bool | Não | Se este status é terminal conforme configuração. |
| `corte_local` | localtime | Não | Meia-noite que fecha o período, em São Paulo. |
| `elegivel_comparacao` | bool | Não | Trecho observado, encerrado e consistente para comparação de tempos. |
| `horas_observadas_encerradas` | num | Sim | Duração somente quando elegivel_comparacao=true; campo recomendado para mediana/média. |
| `status_atual_nome` | text | Não | Último status reconstruído no corte, repetido no projeto. |
| `projeto_na_fila` | bool | Não | Projeto ativo no cadastro e em etapa não terminal no corte. |
| `tempo_desde_entrada_horas` | num | Sim | Total desde Entrada comprovada; NULL quando desconhecido. Usar MAX por projeto, nunca SUM das linhas. |
| `tempo_status_atual_horas` | num | Sim | Horas na última etapa quando seu início foi comprovado; repetidas no projeto, usar MAX. |
| `responsavel_situacao` | text | Não | identificado, ausente, nome_indisponivel, equipe ou texto_snapshot_sem_correspondencia_individual. |
| `cadastro_referencia_utc` | time | Sim | Instante da observação dos atributos, em UTC. |
| `versao_regras` | text | Não | Versão semântica e assinatura da configuração/catálogo. |
| `item_sk` | text | Não | Chave substituta estável do projeto. |
| `board_sk` | text | Não | Chave substituta estável do quadro. |
| `status_id` | text | Não | Identidade original composta do status (quadro/coluna/rótulo). |
| `status_sk` | text | Não | Chave substituta estável do status. |
| `entrada_status_utc` | time | Sim | Início comprovado em UTC; NULL para inferência. |
| `saida_status_utc` | time | Sim | Saída em UTC, se observada. |
| `corte_utc` | time | Não | Mesmo fechamento de corte_local em UTC. |
## Artefato privado pendencias_projeto.json — não é tabela BigQuery

| Campo | Tipo | Aceita NULL | Descrição |
|---|---|---|---|
| `item_id` | id | Não | ID original do item/projeto Monday, repetido entre suas passagens. |
| `board_id` | id | Não | ID original do quadro Monday. |
| `projeto_nome` | text | Não | Nome cadastral do projeto na coleta. |
| `excluido_da_analise` | bool | Não | True: projeto ausente da Gold por regra de exclusão. False: aviso sobre projeto mantido. |
| `motivos` | text | Não | Descrição legível dos motivos atuais, separados por |. |
| `como_corrigir` | text | Não | Orientação de ação no Monday/revisão/histórico. |
| `marca_original` | text | Sim | Valor recebido na coluna Marca. |
| `talento_original` | text | Sim | Valor recebido na coluna Talento. |
| `interveniencia_original` | text | Sim | Valor recebido na coluna Interveniência. |
| `responsavel_orcamento_original` | text | Sim | Texto original da coluna Orçamento, inclusive referência inválida para diagnóstico. |
| `codigos` | text | Não | Códigos estáveis dos motivos atuais, separados por |. |
| `cadastro_referencia_utc` | time | Sim | Instante da observação dos atributos, em UTC. |
| `corte_local` | localtime | Não | Meia-noite que fecha o período, em São Paulo. |
| `versao_regras` | text | Não | Versão semântica e assinatura da configuração/catálogo. |
| `item_sk` | text | Não | Chave substituta estável do projeto. |
Tipos lógicos: id=int64, int=inteiro, text=texto, num=número finito não negativo, bool=booleano, localtime=data/hora local sem fuso, time=instante com fuso. O artefato de pendências contém informações operacionais para revisão e acesso restrito. Projetos excluídos não entram em sla_orcamento.

## Precisão das horas publicadas

Todos os campos numéricos de horas em `sla_orcamento` são arredondados em Python a no máximo três casas decimais na projeção final (round, empate para o par). Cálculos, evidências e estado interno preservam precisão completa; desconhecidos continuam NULL. Origem, grão, chaves e tipos FLOAT64 permanecem iguais. BI recebe valores já arredondados; somas podem apresentar pequenas diferenças de arredondamento. A validação ocorre antes e depois da projeção; falha bloqueia a publicação.
