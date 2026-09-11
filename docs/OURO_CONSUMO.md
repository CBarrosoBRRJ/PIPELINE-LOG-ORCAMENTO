# Gold para consumo — guia da versão 2

Contrato executável 2.0.0. Tabela principal: **`dados_globo.orcamento.gold_projeto_status`**. Código: `services/gold.py`, chamado tanto por `daily/backfill` como por `replay`. Consulte [VALIDACAO_OURO.md](VALIDACAO_OURO.md) para evidências de publicação. A [prévia](PREVIA_OURO_CONSUMO.md) registra as decisões anteriores; este guia descreve a implementação.

## O que importar no Power BI

1. Salvar uma cópia do PBIX atual.
2. Obter Dados → PostgreSQL → conexão existente → modo Importar.
3. Marcar **somente `orcamento.gold_projeto_status`** para o novo modelo. Não acrescentar as tabelas antigas de intervalos: são outra representação das mesmas passagens.
4. O nome normalmente aparece como **`orcamento gold_projeto_status`** no Power BI. Os exemplos DAX usam esse nome com espaço e argumentos separados por vírgula.
5. Usar campos da própria Gold para filtrar projeto, status, Marca, Talento e responsável. Não são necessários os relacionamentos anteriores entre sete tabelas para esse relatório.
6. IDs/SKs, ordem e totais repetidos: configurar como Não resumir. Entrada/saída local: Data/Hora. Retorno: Verdadeiro/Falso. Durações: Número decimal.
7. Criar as medidas de [power_bi_gold.dax](../powerbi/power_bi_gold.dax), uma por vez. Criar primeiro Projeto 360°; HTML Content consumirá essas medidas e linhas posteriormente.

No PostgreSQL: `SELECT ... ORDER BY item_id, ordem_etapa`. No relatório: filtrar um projeto e ordenar por `ordem_etapa`. A ordem física de uma tabela não garante ordem visual.

## Uma linha por passagem

| Campo para exibir | Significado |
|---|---|
| `item_id`, `projeto_nome` | ID original Monday e nome do projeto |
| `ordem_etapa` | 1, 2, 3… em ordem cronológica por projeto |
| `status_nome` | Etapa dessa passagem; não confundir com status atual |
| `entrada_status_local` | Data e hora do início disponível, horário de São Paulo |
| `saida_status_local` | Data e hora de saída; nula na passagem aberta |
| `duracao_horas` | Duração corrida, até saída ou corte |
| `marca_nome`, `talento_nome` | Atributos tratados do cadastro de referência |
| `responsavel_orcamento` | Pessoas da coluna Orçamento; não é responsabilidade comprovada por cada etapa antiga |
| `eh_retorno` | True se o projeto já passou pelo mesmo status no histórico disponível |
| `qualidade_historico` | `observed`, `initial_inferred` ou `no_history_inferred` |
| `corte_local` | Até quando os dados foram medidos |

`eh_primeiro_registro` e `eh_ultimo_registro` identificam as extremidades disponíveis. Eventos sem mudança real de status não reiniciam o relógio. Empates de horário preservam a ordem nativa reconstruída pelo transformador. Uma segunda passagem pelo mesmo status é um retorno legítimo, com outra chave de intervalo.

A primeira etapa de negócio é Entrada. Quando não há evento que comprove o início, `entrada_comprovada_utc` e `tempo_desde_entrada_horas` ficam nulos. A Gold não inventa uma Entrada para preencher a primeira linha. Qualidade inferida sempre acompanha estimativas de permanência antiga.

A última passagem fica com saída nula. Um status final pode continuar sem saída, embora o projeto esteja encerrado. O tempo total desde Entrada termina na finalização comprovada; a permanência na etapa final continua registrada. Se cadastro atual e histórico divergirem, `status_atual_divergente=true`; não inventar a hora da transição faltante.

Todos os horários locais estão em America/Sao_Paulo, sem fuso embutido para apresentação. Os campos UTC são a referência inequívoca. Duração é corrida, incluindo noites/fins de semana. O corte é o início da carga; **D+1 fechado ainda não foi implementado**.

## Regras de elegibilidade do projeto

Aplicadas ao último snapshot disponível até o corte, para **o projeto inteiro**:

- Talento e Interveniência preenchidos, mesmo se iguais: excluir.
- Múltipla seleção de IDs no dropdown: excluir.
- Lista textual explícita com vírgula, ponto e vírgula, quebra de linha, `+`, ou `&`/`/` entre espaços: excluir. Identidade individual aprovada no catálogo pode esclarecer pontuação de um nome; seleção múltipla e ambas as colunas continuam excluídas.
- Squad de Talentos, com normalização de espaços/caixa: excluir.
- Coletivos confirmados Bruno e Marrone, Manual do Mundo, PodPah, ou qualquer entidade de talento aprovada como organização/coletivo: excluir.

A detecção textual não reconhece automaticamente todas as combinações possíveis. Texto livre desconhecido não é presumido pessoa nem unido por similaridade. O cadastro de revisão resolve casos novos sem inventar identidades.

Marca/Talento vazio não exclui automaticamente um projeto. Campo desconhecido permanece nulo. Sem histórico completo, as passagens ficam identificadas como inferidas e não entram na comparação de tempos observados.

Todos os indicadores da Gold abrangem **somente os projetos elegíveis**, incluindo fila, totais e indicadores de Marca. Projetos excluídos continuam nas camadas técnicas. Uma correção no Monday ou nas regras pode reincluir seu histórico na próxima carga. Assim, números históricos podem mudar com correções; corte e versão tornam essa mudança auditável.

`data_quality_issue`, código `gold_projeto_excluido`, registra um apontamento por projeto, com os motivos e a versão no JSON textual `detail`. Os motivos podem se sobrepor; não somar contagens por motivo como se fossem projetos diferentes.

## Marca e Talento: normalização e revisão

Limpeza: Unicode NFC, espaços repetidos, vazios → nulo. A chave de comparação usa caixa uniforme, mantendo acentos/pontuação. Não remover automaticamente acentos para juntar identidades nem alterar maiúsculas de exibição indiscriminadamente.

| Situação | Interpretação |
|---|---|
| Marca `texto_normalizado` | Grafia limpa; ainda não há equivalência canônica aprovada |
| Talento `cadastro_exclusivo` | Nome único informado na coluna de talentos exclusivos, sem exclusões detectadas; identidade baseada no cadastro, sem dedução por IA |
| `aprovado` | Correspondência explícita revisada no catálogo |
| Talento `pendente_revisao` | Texto de Interveniência ainda sem identidade individual aprovada; projeto permanece para análise de status, nome/chave de talento ficam nulos para impedir atribuição indevida |
| `ausente` | Campo não informado |

`meta_entity_mapping` é a tabela técnica de revisão, no grão quadro + tipo de entidade + chave do texto original. O pipeline descobre candidatos pendentes, mas **não sobrescreve aprovações humanas**. Fonte e nome original permanecem disponíveis. `canonical_id` é um identificador estável escolhido uma vez, por exemplo UUID; não deve depender de futuras alterações no nome.

Para corrigir um nome no DBeaver:

1. Abrir `orcamento.meta_entity_mapping`, filtrar `entity_type` (`marca` ou `talento`) e localizar `source_text`.
2. Conferir com o cadastro/equipe se representa a mesma identidade. Não aprovar nomes parecidos sem confirmação.
3. Definir `canonical_id`, `canonical_name`, `entity_kind` (`person`, `organization` ou `collective`), `reviewed_by`, `updated_at` e `review_status=approved`. Para várias grafias da mesma entidade, reutilizar exatamente o mesmo ID, nome e tipo canônicos. Não alterar PK/source_key para corrigir a exibição.
4. Salvar a revisão fora de uma carga em andamento e rodar `sla-pipeline replay` pelo VS Code ou aguardar a próxima carga. `replay` não consulta Monday nem avança o corte.
5. Executar `validate-gold`, conferir a nova versão e atualizar o Power BI.

Aprovação incompleta ou definições conflitantes para o mesmo ID bloqueiam publicação. Para desfazer uma aprovação, mudar `review_status` para `pending` e reprocessar. Para corrigir ausência real, corrigir no Monday e executar a próxima carga; replay só conhece dados já coletados.

`meta_gold_rule_snapshot` guarda de forma imutável o conteúdo das aprovações, mapeamentos e configuração de cada versão usada. `versao_regras` contém versão do código de regras + hash do conteúdo. Reconstruir uma versão antiga exige também código/fontes/corte correspondentes; o comando replay normal usa o catálogo atual.

Não houve contratação de IA/NLP ou envio dos cadastros a terceiros. Grafias pendentes não são correções já realizadas.

## Responsáveis e demais pessoas

Orçamento é identificado pelo título normalizado da coluna people; no quadro atual o ID é `person`. Também são projetados `talent_manager`, `gp`, `audiencia`, `conteudo` e `producao`. Mapeamento ausente de Orçamento ou ambíguo bloqueia o lote.

IDs e nomes ficam em `responsaveis_orcamento_json` e `pessoas_referencia_json`. Duplicatas da mesma pessoa/coluna são removidas. Vários responsáveis aparecem juntos na apresentação, sem duplicar passagens nem horas; isso não aciona a regra de múltiplos **talentos**.

Nomes são recuperados do cadastro de pessoas ou do snapshot. Quando a API de usuários não identifica o nome, o texto original da coluna pode identificar um único responsável. Havendo vários IDs sem correspondência individual, preservamos o texto original para apresentação, mas não associamos nomes a IDs por posição. Essa situação fica explícita em `responsavel_situacao`; cada pessoa também informa `nome_origem` no JSON.

Campos são do cadastro de referência (`cadastro_referencia_utc`), não prova de responsabilidade histórica por cada etapa. Responsável vazio não exclui automaticamente o projeto. Para futuro ranking individual de vários responsáveis, definir atribuição e denominador antes de expandir pessoas; não somar horas de linhas multiplicadas.

## Medidas: o que somar e o que não somar

- `duracao_horas`: somar para tempo por etapa/projeto no histórico selecionado; contém estimativas, identificadas pela qualidade.
- `horas_observadas_encerradas`: só passagens observadas e encerradas de projetos sem divergência/cadeia inconsistente conhecida; demais linhas nulas. Usar para comparações de média/mediana/P95, sempre mostrando a amostra.
- `tempo_desde_entrada_horas` e `tempo_status_atual_horas`: **repetidos por projeto; nunca somar diretamente**. Para Projeto 360°, MAX com um único projeto; para fila, MAX por projeto dentro de uma média. O tempo atual pode ser inferido; não rotular como observado sem verificar a última passagem.
- Projetos: contagem distinta de `item_sk`. Passagens: contagem de `interval_id`. Retornos: contar linhas `eh_retorno=true`.
- Fila por status: usar `status_atual_nome` e `projeto_na_fila`, não `status_nome` histórico. Se filtrar etapas/período históricos, a fila representa a coorte selecionada, não necessariamente o quadro inteiro.

Mediana/P95 por passagem não são mediana/P95 do total acumulado por projeto. Médias/medianas respondem aos filtros no Power BI; não calcular média de medianas pré-agregadas. Filtros de início de passagem selecionam uma coorte; não recortam automaticamente horas na fronteira do período.

Marca: separar **Em elaboração - Retorno Marca/Executivo** e **Aguardando Feedback**. Talento: **Em revisão - Validação Talento**, sem misturar validação de Talent Manager/Gestão Esporte. Mostrar amostra e qualidade; não afirmar causalidade nem dentro/fora do SLA, pois ainda não existem metas.

## Publicação e manutenção

Há 19 tabelas técnicas/analíticas e as quatro views legadas; o consumidor novo importa apenas a Gold. As três adições são Gold, catálogo e snapshot de regras. Bronze, dimensões, fatos e views antigos permanecem para histórico e compatibilidade.

Publicação sob lock por quadro, com PK/FKs e contrato; substitui a Gold daquele quadro na mesma transação dos derivados/watermark. Uma falha reverte a transação. Reexecução não acrescenta cópias: preserva `interval_id`; novas passagens legítimas recebem suas próprias chaves. Exclusões retiram todas as linhas do projeto da Gold, preservando a origem. A ferramenta de validação reconcilia o conjunto exato de passagens elegíveis, horários/durações e sequência/retornos.

Comandos: `sla-pipeline replay`, `sla-pipeline validate`, `sla-pipeline validate-gold`, `sla-pipeline quality-profile`. `health` verifica o executor e não é substituído por replay. Logs da carga incluem quantidade de linhas, projetos incluídos/excluídos e versão Gold.

Contrato completo: [CONTRATOS_DE_DADOS.md](CONTRATOS_DE_DADOS.md). Consultas: [009_gold_consumo.sql](../sql/009_gold_consumo.sql). PostgreSQL e DDL/adaptador BigQuery compartilham o contrato, inclusive tipos DATETIME para apresentação local. BigQuery real permanece sem implantação/teste com conta corporativa.
