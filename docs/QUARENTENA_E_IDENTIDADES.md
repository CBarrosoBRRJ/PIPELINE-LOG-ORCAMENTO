# Quarentena de projetos e revisão de nomes

Versão 2.2.0. A quarentena fica no mesmo banco, em `orcamento.quarentena_projeto`. Ela é uma fila de saneamento, separada da tabela `orcamento.gold_projeto_status`, que alimenta os indicadores. Não é necessário contratar outro serviço ou criar outro projeto.

## O que sai das análises

O projeto inteiro sai da Gold quando tiver atribuição inválida de talento (ambas as colunas, vários talentos, Squad ou coletivo identificado), talento da Interveniência ainda sem identidade individual revisada, ou grafia de Marca/Talento colocada manualmente em quarentena. A ausência de Marca ou Talento, por si só, continua representada por NULL e não é uma suspeita automática.

`quarentena_projeto` tem **uma linha por projeto**, mesmo quando existem vários motivos. Campos:

| Campo | Informação |
|---|---|
| `board_id`, `item_id`, `item_sk` | Identificadores estáveis para localizar o projeto e relacionar bases |
| `projeto_nome` | Nome cadastral disponível |
| `marca_original` | Marca antes da resolução canônica |
| `talento_original` | Valor da coluna de exclusivos |
| `interveniencia_original` | Valor da coluna Interveniência |
| `motivos` | Lista de códigos de classificação; pode haver mais de um |
| `cadastro_referencia_utc` | Data do cadastro avaliado |
| `corte_utc` | Corte da publicação analítica associada |
| `versao_regras` | Código/configuração/catálogo usados na decisão |
| `atualizado_em` | Referência da coleta usada no processamento |

A fila descreve o cadastro atual avaliado, inclusive projetos posteriores ao corte dos tempos. Por isso, não somar simplesmente Gold + quarentena para comparar com todos os itens da fonte: também há itens cuja primeira passagem é posterior ao corte.

## Classificações

| Código em `motivos` | Tratamento recomendado |
|---|---|
| `talento_ambas_colunas` | Conferir o cadastro e manter somente a coluna aplicável |
| `talento_multiplo` | Corrigir a origem para um talento individual por projeto, conforme regra acordada |
| `talento_squad` | Não consumir como pessoa individual; corrigir a origem quando aplicável |
| `talento_nao_individual` | Coletivo/organização não participa deste escopo de análise |
| `talento_identidade_pendente` | Identificar/revisar o nome de Interveniência; aprovar a pessoa no catálogo |
| `talento_revisao_manual` | Resolver a grafia/identidade suspeita de talento |
| `marca_revisao_manual` | Resolver a grafia/identidade suspeita de Marca |

## Fluxo diário de tratamento no DBeaver

1. Abrir `orcamento.quarentena_projeto` e filtrar `motivos`. Usar `item_id` para encontrar o item original no Monday.
2. Corrigir no Monday quando o preenchimento estiver errado: duas colunas, seleção múltipla, nome digitado ou entidade indevida. O pipeline é somente leitura no Monday; ele não faz essa edição por conta própria.
3. Quando a dúvida for equivalência ou identificação, revisar `orcamento.meta_entity_mapping`. Há um candidato por quadro, tipo de entidade e grafia normalizada. Não editar manualmente a Gold ou a quarentena: ambas são recalculadas.
4. Aguardar a próxima carga das 06h. Ela coleta a correção, reavalia as regras e remove o projeto da quarentena se **todos** os motivos tiverem sido resolvidos. Suas passagens elegíveis anteriores ao corte voltam à Gold com os mesmos IDs. Corrigir só um motivo não libera um projeto que ainda possui outro.
5. Se a alteração foi apenas no catálogo local, `sla-pipeline replay` aplica a revisão sobre a coleta já existente. Replay não enxerga correções recém-feitas no Monday; para elas, aguardar a coleta ou executar recuperação manual justificada.

## Catálogo: pendente, aprovado ou em quarentena

| `review_status` | Significado e efeito |
|---|---|
| `pending` | Descoberto e ainda não revisado. Não significa automaticamente erro. Interveniência pendente bloqueia o projeto; Marca e exclusivos sem suspeita usam grafia normalizada |
| `approved` | Correspondência revisada; exige ID/nome canônicos, tipo e revisor. Talento deve ser `person` |
| `quarantined` | Suspeita explícita em qualquer das duas entidades; exige `reviewed_by` e `review_reason`. Bloqueia todos os projetos que usam essa grafia |

Para separar um nome suspeito, localizar a linha pelo tipo (`marca`/`talento`) e `source_text`, preencher `reviewed_by`, `review_reason` (por exemplo, “confirmar se as duas grafias são a mesma pessoa”), `updated_at` e `review_status=quarantined`. Salvar. Na próxima publicação, os projetos associados saem da Gold e aparecem na fila.

Para aprovar, preencher `canonical_id` estável, `canonical_name`, `entity_kind` e revisor, mudando para `approved`. Duas grafias da mesma entidade reutilizam o mesmo ID, nome e tipo canônicos. Confirmação humana é necessária: sem ela, não unir automaticamente “Ludi Cianci” e “Ludimilla Ciani”, por exemplo. Se forem pessoas diferentes, devem continuar com IDs diferentes.

Se corrigir a grafia no Monday para outra já aprovada, a próxima coleta resolverá a identidade automaticamente. Se o novo texto de Interveniência ainda não estiver aprovado, o projeto continua na fila, pois corrigir a escrita não comprova sozinho a identidade. `pending` em Marca não bloqueia tudo: caso contrário, todo nome recém-descoberto seria tratado como erro.

## Integridade e limites

A publicação da Gold e da quarentena é atômica. Um projeto não pode estar nas duas saídas. Há PK na fila e reconciliação com `data_quality_issue` antes de gravar. O histórico técnico continua disponível para reincluir as passagens após a correção; não há cópia física de linhas entre duas bases independentes.

A fila é o estado **atual** das pendências, não uma contagem acumulada de erros. O histórico das entradas e das configurações permanece na Bronze, em `etl_run` e em `meta_gold_rule_snapshot`. Um log específico de cada decisão/revisor ao longo do tempo seria evolução futura; não está implementado como trilha completa de edição do catálogo.

Não existe detector universal de erro de digitação. Esta versão separa padrões objetivos, Interveniência não revisada e suspeitas classificadas manualmente. Sugestões por similaridade/NLP podem ser acrescentadas no futuro para priorizar a revisão, sem unir identidades ou liberar projetos automaticamente. A manutenção está em [PRD_ELT_REGRAS.md](PRD_ELT_REGRAS.md).

No Power BI de indicadores, importar somente a Gold. Para uma página independente de saneamento, a quarentena pode ser importada opcionalmente; não somar suas linhas como projetos elegíveis nem relacioná-la diretamente às passagens para multiplicar resultados.
