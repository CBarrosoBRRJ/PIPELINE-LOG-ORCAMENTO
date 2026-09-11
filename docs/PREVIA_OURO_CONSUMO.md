> **Referência histórica anterior à arquitetura 3.0.** PostgreSQL agora contém somente `orcamento.gold_projeto_status`; tabelas auxiliares/relações SQL descritas abaixo foram retiradas. Não executar instruções antigas de criação/consulta dessas tabelas. Consulte o [PRD atual](../PRD.md) e a operação 3.0. Conceitos de identidade, nulabilidade e qualidade permanecem aplicáveis.

# Prévia — pipeline em código e uma tabela para consumo

Estado: prévia histórica aprovada pelo usuário e implementada na versão 2. Para o contrato final, os campos efetivos e as limitações, leia [OURO_CONSUMO.md](OURO_CONSUMO.md); para publicação e testes, [VALIDACAO_OURO.md](VALIDACAO_OURO.md). Nenhuma tabela técnica foi removida. O texto abaixo preserva a proposta anterior, inclusive itens cujo nome mudou ou que permaneceram futuros.

## Decisões confirmadas

- Prioridade: selecionar um projeto e conhecer cada passagem por status, seu tempo e seus retornos.
- Extração, limpeza, classificação, junções, reconstrução dos intervalos e validação ficam no código Python deste repositório.
- O resultado tratado será publicado no PostgreSQL e consumido pelo Power BI. O executor continua na VPS; desenvolver no VS Code não exige manter o computador pessoal ligado para a execução remota.
- O usuário confirmou excluir **o projeto inteiro das análises** quando houver múltiplos talentos, Squad de Talentos ou preenchimento simultâneo das duas colunas. A exclusão alcança também indicadores gerais e de Marca, não apenas o ranking de Talento.
- O ranking admite somente pessoas individuais. Duplas, coletivos e organizações identificados no catálogo ficam fora da população analítica.
- O responsável pelo orçamento vem da coluna **Orçamento**, ID `person`, tipo `people`, já mapeada na extração. Não representa automaticamente o responsável pela execução de cada status.
- A definição de responsáveis por status, metas de prazo e HTML Content fica para a etapa seguinte.

## Arquitetura proposta

Monday → histórico original persistido → tratamento e regras em Python → validação → tabela Ouro no PostgreSQL → Power BI/HTML Content.

Banco: `dados_globo`. Schema: `orcamento`. Tabela nova proposta: **`gold_projeto_status`**. Ela ainda não existe; não confundir com a view atual `gold_project_status`.

O Power BI importará apenas essa tabela para o primeiro relatório. A proposta é preservar as tabelas técnicas necessárias ao histórico, reconstrução e auditoria no mesmo banco/schema e conceder ao consumidor leitura da Gold. Não é necessário criar outro banco.

Não apagar todas as tabelas para simplificar o consumo. O código sozinho não conserva eventos passados, e uma nova extração pode não recuperar eventos já indisponíveis na origem. Eventual retirada de estruturas antigas exige preservar as dependências necessárias e conferir backup, restauração, reconciliação e migração dos consumidores. O usuário solicitou esta prévia antes das alterações; nenhuma exclusão será executada nesta etapa.

## Grão e exemplo

Uma linha representa **uma passagem de um projeto por um status**. O termo técnico anterior “visita” significa essa mesma passagem e será substituído na apresentação. A PK será o `interval_id` determinístico existente, preservando IDs/SKs. Agregar todas as passagens antes de armazenar perderia a sequência dos retornos.

Exemplo fictício, horários de São Paulo e corte em 11/09/2026 às 17:00. Entrada e saída terão data **e** hora, inclusive quando uma passagem atravessar vários dias:

| Ordem | Projeto | Status | Entrada | Saída | Duração h | Marca | Talento | Responsável Orçamento | Retorno |
|---:|---|---|---|---|---:|---|---|---|---|
| 1 | Projeto A | Entrada | 11/09/2026 09:00 | 11/09/2026 10:00 | 1 | Marca X | Talento Y | Pessoa Z | false |
| 2 | Projeto A | Em Elaboração - Orçamentos | 11/09/2026 10:00 | 11/09/2026 12:00 | 2 | Marca X | Talento Y | Pessoa Z | false |
| 3 | Projeto A | Validação Talento | 11/09/2026 12:00 | 11/09/2026 15:00 | 3 | Marca X | Talento Y | Pessoa Z | false |
| 4 | Projeto A | Em Elaboração - Orçamentos | 11/09/2026 15:00 | Em andamento | 2 | Marca X | Talento Y | Pessoa Z | true |

Em Elaboração - Orçamentos soma 4 horas em duas passagens. A última linha é um retorno porque esse projeto já passou pelo mesmo status na linha 2. “Em andamento” é apresentação: a saída real fica nula e a duração parcial usa o corte das 17:00. Contar projetos exige contagem distinta de `item_sk`, não contagem de linhas.

No relatório, o usuário verá os rótulos Projeto, Status, Entrada no status, Saída do status, Duração, Marca, Talento, Responsável Orçamento e Retorno. “Entrada no status” é o horário de começo de qualquer etapa; **Entrada** também é o nome do primeiro status de negócio, conceitos distintos. O campo Retorno será booleano, não o texto "true"/"false" armazenado como categoria.

### Ordem, primeira e última linha

- Ordenar por projeto e `ordem_etapa`, calculada cronologicamente a partir dos eventos; a ordem de armazenamento SQL não é uma garantia de apresentação.
- `eh_primeiro_registro=true` na primeira passagem do histórico disponível; `eh_ultimo_registro=true` na última. Projeto com uma única passagem tem ambas as flags verdadeiras.
- `eh_retorno=true` quando já existe passagem anterior pelo mesmo `status_id` no histórico disponível desse projeto. O primeiro registro de um status tem false. Não significa retorno comprovadamente inexistente no histórico indisponível.
- Eventos consecutivos repetindo o mesmo status não criam uma nova passagem nem um retorno.
- O início de negócio continua sendo Entrada. Se os eventos antigos não comprovarem esse começo, sinalizar histórico incompleto; não inserir Entrada com horário inventado nem descartar passagens conhecidas para forçar essa aparência.
- A última passagem apresenta o último status reconstruível e sua saída fica nula enquanto não houver saída comprovada. O status atual do cadastro é apresentado separadamente; divergência entre cadastro e eventos gera diagnóstico, sem inventar transição/data.
- Saída do status é a entrada no próximo status. Um status final de negócio pode ser a última passagem e continuar sem saída; não confundir conclusão do projeto com saída daquela etapa.

### Responsável pelo orçamento e outras pessoas

O mapeamento local `runtime/board_mapping.json`, documentado também em `docs/MAPPING.md`, identifica Orçamento como `person`. A extração existente preserva IDs e coluna de origem em `pessoas_json`; a nova Gold ainda precisa projetar essas informações em campos prontos.

Proposta inicial: usar responsáveis do cadastro de referência no corte, assim como Marca/Talento. Identificar essa referência explicitamente. Não atribuir retrospectivamente responsabilidade por uma etapa sem evidência histórica da designação.

Preservar ID/nome de cada pessoa. Se a coluna tiver várias pessoas, manter uma linha por passagem e apresentar os nomes juntos, com quantidade e IDs preservados; não escolher a primeira pessoa nem multiplicar linhas/horas. A regra de excluir múltiplos **talentos** não exclui automaticamente projetos com vários **responsáveis**. Campo vazio permanece desconhecido, não provoca exclusão automática. Equipes do Monday não são convertidas em pessoas individuais sem correspondência explícita.

Outras colunas de pessoas já mapeadas: Talent Manager (`pessoas9__1`), GP (`dup__of_dup__of_squad__1`), Audiência (`dup__of_conte_do__1`), Conteúdo (`dup__of_planejamento__1`) e Produção (`multiple_person__1`). Podem aparecer em campos separados, mantendo a mesma regra de não multiplicar passagens. Nome concatenado serve para apresentação; futuro ranking individual de múltiplos responsáveis exigirá regra explícita de atribuição.

## Dicionário de consumo proposto

Nomes em `snake_case`, sem acentos. Instantes de referência em UTC; datas locais explicitamente identificadas. IDs de origem inteiros, SKs em texto; IDs não devem ser somados no Power BI.

| Campos | Conteúdo e regra |
|---|---|
| `interval_id` | Texto obrigatório; PK única da visita, reutilizada dos intervalos existentes |
| `board_id`, `board_sk`, `item_id`, `item_sk` | Identificação original e técnica do quadro/projeto, obrigatória |
| `projeto_nome` | Nome tratado para apresentação; original preservado na camada técnica |
| `status_id`, `status_sk`, `status_nome`, `ordem_status_quadro`, `status_final` | Etapa da passagem; ordem no quadro não é a ordem cronológica do projeto |
| `ordem_etapa`, `passagem_numero_no_status`, `eh_retorno` | Sequência cronológica e retorno à mesma etapa; desempate determinístico sem mudar horários originais |
| `eh_primeiro_registro`, `eh_ultimo_registro` | Identificam as extremidades do histórico disponível, sem garantir cobertura desde a criação |
| `entrada_status_utc`, `saida_status_utc`, `entrada_status_local`, `saida_status_local` | Entrada/saída da etapa; saída real nula enquanto aberta. Apresentação local em America/Sao_Paulo |
| `corte_utc`, `corte_local` | Limite usado para calcular duração aberta; não representa uma saída real da etapa |
| `duracao_minutos`, `duracao_horas` | Tempo corrido até a saída ou o corte; sempre acompanhado da qualidade histórica |
| `intervalo_aberto`, `qualidade_historico` | Andamento e classificação observado/inferido, preservando categorias existentes |
| `elegivel_comparacao`, `horas_observadas_encerradas` | Comparações usam visitas observadas, encerradas e sem inconsistência temporal conhecida; valor nulo quando inelegível, nunca zero artificial |
| `status_atual_id`, `status_atual_nome`, `projeto_ativo`, `projeto_na_fila` | Situação do projeto no corte; atributos repetidos nas visitas, usados com contagem distinta de projetos |
| `entrada_comprovada_utc` | Primeiro evento disponível de entrada em Entrada; nulo quando não comprovado, nunca preenchido pela criação do item |
| `marca_chave`, `marca_nome`, `marca_situacao` | Marca canônica quando houver correspondência aprovada; ausência e identidade pendente explícitas |
| `talento_chave`, `talento_nome`, `talento_origem`, `talento_situacao` | Pessoa individual e origem quando válidas; conservar o mapeamento para a coluna legada `intervenciencia` |
| `responsavel_orcamento`, `responsaveis_orcamento_json`, `quantidade_responsaveis_orcamento` | Nome(s) para exibição e lista de IDs/nomes deduplicados da coluna `person`; quantidade não soma projetos ou horas |
| `talent_manager`, `gp`, `audiencia`, `conteudo`, `producao`, `pessoas_referencia_json` | Outros papéis em campos separados e lista estruturada com ID, nome, tipo e coluna; sem expandir passagens |
| `responsavel_referencia_utc`, `responsavel_situacao` | Momento do cadastro e qualidade da atribuição; desconhecido/equipe/sem nome identificados explicitamente |
| `cadastro_referencia_utc` | Snapshot usado nos atributos e na elegibilidade do projeto |
| `versao_regras`, `processado_em_utc` | Versão do tratamento e processamento; num replay, processamento e corte são momentos diferentes |

Não repetir totais por projeto/etapa como colunas somáveis em todas as visitas: isso multiplicaria as horas. Totais por etapa somam as durações das visitas selecionadas. Tempo total desde Entrada continua obedecendo ao marco comprovado e ao encerramento; não equivale a somar trechos anteriores à Entrada ou permanência posterior à finalização.

## População e exclusões

Proposta: avaliar o **último cadastro disponível até o corte**, aplicando a decisão ao projeto inteiro. Uma correção permitirá reincluir todo o histórico na próxima publicação. Indicadores passados poderão mudar com correções; registrar corte, versão e decisão. Marca/Talento serão atributos desse cadastro de referência, sem afirmar que eram os mesmos na época de todas as visitas.

| Condição | Resultado proposto |
|---|---|
| Talento e interveniência preenchidos após limpeza | Excluir todas as visitas do projeto da Gold, mesmo se os textos forem iguais |
| Múltipla seleção ou lista explícita de pessoas | Excluir o projeto; não expandir em pessoas |
| Squad de Talentos ou dupla/coletivo/organização identificados | Excluir o projeto, registrando motivo |
| Marca ou Talento ausente | Não excluir automaticamente; conservar os tempos e não atribuir identidade desconhecida |
| Grafia suspeita ou identidade não resolvida | Não unir automaticamente entidades; sinalizar e encaminhar ao catálogo de revisão |
| Histórico inicial ausente/inferido | Não fabricar eventos; manter qualidade e retirar esses trechos das comparações de tempo observado |

Detectar múltiplos talentos prioritariamente pela seleção estruturada do dropdown, quando disponível. Delimitadores no texto livre levantam casos, mas não reconhecem toda lista ou identidade. Não dividir qualquer ocorrência de “e” em um nome. Casos incertos precisam de revisão; não prometer classificação perfeita.

A auditoria técnica registrará projeto, códigos de exclusão, versão e corte. Projetos excluídos não serão apagados da Bronze/Silver. Eles estarão ausentes de todos os indicadores de negócio da Gold, conforme solicitado, e recuperáveis após correção.

Os indicadores representarão **projetos elegíveis pelas regras**, e não o quadro inteiro. O aceite deve informar lidos, incluídos e excluídos. Não somar contagens por motivo: um projeto pode ter vários motivos.

## Padronização e identidade

1. Normalização Unicode, espaços e texto vazio → nulo; originais preservados.
2. Chave de comparação separada do nome de apresentação.
3. Catálogo versionado de variantes aprovadas → identificador canônico. Somente correspondências aprovadas agrupam grafias diferentes como a mesma entidade.
4. PK única impede duplicação da visita; catálogo trata nomes divergentes. São problemas distintos.
5. Novas grafias e conflitos vão para revisão. Regras alteradas geram nova versão e reconciliação.

IA/NLP poderá sugerir correspondências futuramente. A primeira versão usará regras e catálogo revisado, sem serviço pago ou envio de cadastros a uma IA externa. Não inferir que nomes parecidos identificam a mesma pessoa nem classificar desconhecidos automaticamente como pessoas individuais.

## Responsabilidades e indicadores

**Python:** extrair, preservar fontes, limpar, aplicar catálogo/exclusões, reconstruir tempos e retornos, enriquecer linhas, validar e publicar atomicamente. Falha mantém a última carga válida.

**PostgreSQL:** persistir resultado, impor integridade e servir consultas. Reexecução com o mesmo corte, fontes e regras deve produzir o mesmo resultado. A publicação deve retirar da Gold projetos que se tornarem inelegíveis; somente upsert deixaria linhas indevidas.

**Power BI:** importar, filtrar, agregar e apresentar em HTML Content. Não limpará nomes, expandirá talentos ou reconstruirá eventos. Ainda haverá medidas para contagem distinta, soma, média, mediana e percentis dependentes dos filtros; não usar média de medianas pré-calculadas. [Microsoft: esquema e medidas](https://learn.microsoft.com/en-us/power-bi/guidance/star-schema).

Indicadores iniciais:

- Projeto: trajetória, horas por etapa, visitas e retornos.
- Etapa: projetos distintos, mediana/P95 por visita observada encerrada e amostra.
- Fila: projetos ativos em status não final, agrupados pelo **status atual**, não pelos status históricos.
- Marca: Em elaboração - Retorno Marca/Executivo e Aguardando Feedback separados; combinação explicitamente definida.
- Talento: Validação Talento separada das validações internas de gestores.

Declarar se o ranking é por visita ou total por projeto. Cinco projetos é um filtro exploratório, não garantia estatística. Permanência no status não prova responsabilidade da pessoa/marca pela espera.

Uma tabela atende ao relatório inicial; não substitui um modelo dimensional compartilhado para todos os futuros domínios. Preservar identidades facilita a evolução. Schemas são divisões internas do banco com permissões próprias. [PostgreSQL: schemas](https://www.postgresql.org/docs/17/ddl-schemas.html).

## Diagnóstico somente leitura desta prévia

Consulta às tabelas da VPS no corte persistido **2026-09-11 17:13:16.749793 UTC**:

| Verificação | Resultado |
|---|---:|
| Projetos cadastrados | 4.569 |
| Projetos ativos | 4.565 |
| Visitas a status | 5.355 |
| Repetições de `interval_id` | 0 |
| Projetos com ambas as colunas preenchidas | 16 |
| Projetos contendo Squad de Talentos | 107 |
| União dos dois motivos, contando cada projeto uma vez | 121 |
| Projetos sem snapshot disponível | 3 |

Perfil pelo último snapshot, com `btrim` para vazios e busca da expressão sem diferenciar maiúsculas/minúsculas. Não representa ainda o novo normalizador nem classifica múltiplos nomes, todos os coletivos e identidades ambíguas. **121 não é o total final de exclusões.** Não houve escrita, replay, migração ou alteração de watermark.

## Implementação e migração propostas

1. Revisar esta prévia antes de publicar, conforme solicitado.
2. Implementar normalizador, catálogo, elegibilidade, builder Gold e contrato executável; reutilizar a reconstrução de eventos.
3. Testar retorno legítimo, exclusão de todas as etapas do projeto, reinclusão após correção, nulos, múltiplos talentos, ambas as colunas, tempo aberto/encerrado e preservação de IDs/durações.
4. Conferir backup atualizado e restauração; gerar candidata isolada e reconciliar tempos dos projetos incluídos com o histórico existente.
5. Publicar Gold de forma aditiva e atômica, com auditoria e chaves únicas. Não apagar estruturas necessárias ao executor.
6. Atualizar documentação/código e conferir versão do executor remoto e geração da Gold na rotina agendada.
7. Salvar cópia do PBIX; importar apenas a nova tabela no modelo novo e adaptar medidas. No DAX: `'orcamento gold_projeto_status'`, com espaço; argumentos separados por vírgula.
8. Construir Projeto 360° e módulos HTML. Retirar objetos antigos de consumo somente após migrar dependências, preservando o armazenamento técnico necessário.

O corte atual continua no início da execução. D+1 fechado é uma decisão separada. Esta prévia não significa implementação, publicação no GitHub, deploy ou migração BigQuery concluídos.
