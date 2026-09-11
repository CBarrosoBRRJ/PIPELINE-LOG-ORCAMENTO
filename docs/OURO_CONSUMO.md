# Dicionário das duas tabelas públicas — 3.1.0

Regras, exemplos e roteiro: [CONSUMO_DIRETO.md](CONSUMO_DIRETO.md). Campos internos anteriores não representam mais o contrato físico do PostgreSQL.

## gold_projeto_status

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
## pendencias_projeto

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
Tipos: id=int64, int=inteiro, text=texto, num=decimal, bool=booleano, localtime=data/hora local sem fuso, time=instante com fuso. JSON não é necessário nas duas tabelas de consumo. A tabela principal tem 33 campos; os dez do exemplo aparecem primeiro. As demais colunas suportam integração, filtros e qualidade.
