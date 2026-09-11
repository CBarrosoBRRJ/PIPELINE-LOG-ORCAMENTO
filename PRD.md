# PRD — permanência de projetos por status

Versão 2.2.0 · atualizado em 11/09/2026 · pipeline `sls_orcamento_pdd`.

## Objetivo e entrega

Selecionar um projeto e conhecer, linha a linha, por quais status passou, quando entrou e saiu, quanto tempo permaneceu e se retornou à etapa. O Python faz extração, tratamento, regras e publicação; o Power BI consome `dados_globo.orcamento.gold_projeto_status`.

O quadro atual é **Backlog 2026 | Agenciamento**, ID `18429499488`, coluna principal `status_19`. O banco é `dados_globo`; `orcamento` é o schema da equipe. Futuras áreas podem ter outros schemas no mesmo banco. Os nomes `rede_globo` e `orcamentos` foram aposentados.

## Documentação que orienta a manutenção

- [PRD da ELT e regras](docs/PRD_ELT_REGRAS.md): passo a passo, arquivos, testes, tabelas e procedimento para novas regras.
- [Guia de consumo](docs/OURO_CONSUMO.md): significado dos campos e cuidados nas agregações.
- [Quarentena e identidades](docs/QUARENTENA_E_IDENTIDADES.md): classificar nomes, corrigir e reincluir projetos.
- [Power BI](docs/POWER_BI_PRD.md): importação, indicadores e páginas.
- [Operação](OPERATIONS.md): agendamento, deploy, validação e recuperação.
- [Contrato executável](docs/CONTRATOS_DE_DADOS.md): campos, tipos, chaves e referências, versão 2.2.0.
- [Validação observada](docs/VALIDACAO_OURO.md): evidências; distingue banco publicado de executor implantado.
- [BigQuery/Databricks](docs/BIGQUERY_DATABRICKS.md): mapa para a migração corporativa futura.

## Regras confirmadas

1. **Grão:** uma linha por passagem do projeto pelo status. Retorno a um status gera outra passagem; evento sem mudança real não reinicia o relógio.
2. **Sequência:** `ordem_etapa` é cronológica; primeira/última linha referem-se ao histórico disponível. O banco não garante ordem física: o consumidor ordena pela coluna.
3. **Início:** sempre Entrada para medir tempo total. Sem evento comprovado, o total fica nulo. Não fabricar uma linha Entrada para completar histórico.
4. **Duração:** tempo corrido em minutos/horas. Saída nula significa última passagem aberta no corte. Permanência no status final também é armazenada; tempo total encerra apenas em finalização comprovada.
5. **Finais atuais:** Encerrado, Declinado pelo Mercado, Declinado Internamente, configurados em `FINAL_STATUS_LABELS`. Status novos são descobertos automaticamente; uma nova classificação final precisa de configuração explícita.
6. **Qualidade:** trechos observados, iniciais inferidos e sem histórico são identificados. Rankings de tempo usam apenas passagens observadas encerradas sem divergência detectada.
7. **Atributos:** Marca, Talento e pessoas vêm do cadastro observado, com `cadastro_referencia_utc`. Orçamento é o responsável cadastral, não prova de quem respondeu por cada etapa antiga.
8. **Elegibilidade:** excluir o projeto inteiro da Gold se houver ambas as colunas de talento, vários talentos, Squad ou coletivo identificado. Interveniência com identidade individual ainda não revisada e nomes explicitamente classificados como suspeitos vão também para quarentena.
9. **Nomes:** limpar Unicode/espaços/vazios. Correspondência canônica exige revisão; não unir grafias por similaridade nem adivinhar identidade por IA. Marca/exclusivo pendente de catálogo não significa automaticamente erro.
10. **Reinclusão:** ao corrigir a origem ou aprovar a identidade, o próximo processamento retira o projeto da quarentena se todos os motivos cessarem e republica seu histórico elegível com as mesmas chaves.

Ainda não existem metas máximas por status. O objetivo é estudar os tempos e gargalos para defini-las. Não classificar dentro/fora do SLA sem metas aprovadas. Marca: medir separadamente Em elaboração - Retorno Marca/Executivo e Aguardando Feedback. Talento: Em revisão - Validação Talento.

## Agendamento e corte

Uma tentativa automática diária às **06h America/Sao_Paulo**. O loop espera o próximo horário ao iniciar; deploy e reinício não fazem carga imediata. A reserva diária em `etl_run`, com ID determinístico e PK, impede repetição da mesma data. Advisory lock por quadro impede concorrência.

**D+1 para tempos:** carga de 12/09 às 06h fecha os tempos até 12/09 00:00, isto é, o fim de 11/09. Eventos exatamente à meia-noite entram no próximo fechamento. A Gold mostra `corte_local`. O watermark continua marcando a coleta, separado do corte analítico.

Marca, Talento, responsável e atividade são o cadastro observado na coleta, não uma reconstrução desses atributos à meia-noite. Isso fica explícito na data de referência. O status/tempo no corte vem da sequência de intervalos disponível; lacunas continuam sinalizadas.

Se a VPS cair ou a carga falhar, não existe garantia física de execução naquele horário. Não há repetição automática do lote no mesmo dia. O monitoramento e a recuperação manual estão no guia operacional; não ocultar atraso como carga bem-sucedida.

## Modelo, integridade e simplificação

Há uma Gold de indicadores e uma quarentena de saneamento. As quatro views analíticas antigas foram substituídas; a remoção explícita usa `sql/010_retire_legacy_views.sql`, sem CASCADE. Não são recriadas pelo código atual.

O inventário de **20 tabelas** está no PRD da ELT. As demais têm função de origem, reconstrução dos tempos, deduplicação, catálogo, relações ou controle. Não são necessárias no modelo Power BI de indicadores. Mantê-las evita depender da retenção do Monday para recuperar passagens antigas.

- IDs originais: `board_id`, `item_id`, `event_id`, `person_id`. Conservar para integrar novas bases.
- SKs UUIDv5 determinísticas: identidade estável entre ambientes. Não renumerar em PostgreSQL ou BigQuery; não confundir chave de entidade com versão SCD2.
- `interval_id`: chave determinística da passagem; reprocessamento não acrescenta cópia.
- Gold: PK por intervalo e UNIQUE `(board_id,item_id,ordem_etapa)`.
- FKs/NOT NULL/contrato e reconciliação validam escopo, chaves, duração e sequência.
- Uma transação publica derivados, Gold, quarentena e watermark; falha mantém a publicação anterior. A reserva de execução é operacional e persiste separadamente.
- Catálogo humano não é sobrescrito pelo pipeline; a versão aplicada fica registrada em `meta_gold_rule_snapshot`.

## Escala e evolução

O MVP processa um quadro por configuração e reconstrói derivados em memória. Não é uma plataforma distribuída. Para novas fontes, definir domínio, origem, grão, PK/FKs, política de NULL, regras, dono e consumidor antes de adicionar tabelas. Números iguais de sistemas diferentes não representam automaticamente a mesma entidade.

O PostgreSQL da VPS é provisório. BigQuery compartilha contrato, IDs/SKs, UTC e tipos locais DATETIME. A migração exigirá acesso corporativo, reconciliação de contagens/chaves/horas, orquestração própria, permissões e testes reais antes de trocar o Power BI. Não foi implantada nem homologada em conta BigQuery real.

HTML Content será a camada de apresentação futura. A estrutura de consumo e as regras ficam no pipeline. Não há serviço de IA/NLP contratado, criação de metas, horas úteis, reconstrução histórica dos responsáveis ou alerta externo implantado nesta entrega.
