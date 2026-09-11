# PRD — Histórico de projetos por status

Versão de aplicação **3.0.0**. Regras e contrato de campos **2.2.0** (a migração de armazenamento não altera tempos nem identidades).

## Resultado aprovado

O banco PostgreSQL `dados_globo` tem uma única tabela deste projeto: **`orcamento.gold_projeto_status`**. Uma linha representa uma passagem de um projeto por um status. As outras 19 tabelas são removidas pela migração explícita; não são transferidas para outro schema PostgreSQL nem recriadas na carga seguinte.

| Apresentação | Coluna |
|---|---|
| Ordem | `ordem_etapa` |
| Projeto | `projeto_nome` e `item_id` original Monday |
| Status | `status_nome` |
| Entrada / Saída | `entrada_status_local` / `saida_status_local` |
| Duração | `duracao_horas` e `duracao_minutos` |
| Marca / Talento | `marca_nome` / `talento_nome` |
| Responsável Orçamento | `responsavel_orcamento` |
| Retorno | `eh_retorno` (booleano) |

A tabela também guarda UTC, IDs/SKs, qualidade, corte, versão e indicadores por projeto. O consumidor ordena por `item_id, ordem_etapa`; não existe ordem física garantida em SQL. Detalhes: [dicionário](docs/OURO_CONSUMO.md) e [Power BI](docs/POWER_BI_PRD.md).

## Regras de negócio

1. Primeira/última linha são o primeiro/último trecho **disponível**. A primeira etapa do processo é Entrada, mas não inventar eventos para preencher lacunas. Tempo total desde Entrada só existe quando comprovado.
2. Retorno é a segunda ou posterior passagem pelo mesmo status; não é duplicidade. Evento sem mudança real não reinicia o relógio.
3. Duração corrida, incluindo noites/fins de semana. Saída nula indica última passagem aberta **no corte**. Status final pode continuar sem saída, embora o projeto esteja encerrado.
4. Terminais configurados: Encerrado, Declinado pelo Mercado, Declinado Internamente. Status novos são descobertos; classificá-los como terminais exige configuração explícita.
5. Históricos `observed`, `initial_inferred`, `no_history_inferred` permanecem distintos. Comparações usam `elegivel_comparacao`/`horas_observadas_encerradas`, sem misturar estimativas.
6. Excluir o **projeto inteiro** da análise quando houver múltiplos talentos, Squad, ambas as colunas Talento/Interveniência, coletivo conhecido, identidade Interveniência pendente ou talento/marca manualmente em quarentena. Ausência de Marca/Talento isoladamente não exclui.
7. Limpar Unicode/espaços/vazios. Similaridade de grafia não comprova identidade. Correspondências canônicas precisam de revisão humana; nenhum envio a IA externa.
8. Responsável vem da coluna people Orçamento (ID atual `person`). Pessoas adicionais ficam agregadas, sem multiplicar linhas. Atributos são do cadastro observado, não prova de responsabilidade histórica.
9. Corrigida a origem, a próxima coleta reavalia o projeto. Corrigido o catálogo, replay ou próxima carga reavalia. Reinclusão preserva IDs e histórico disponível.

Não existem metas máximas de SLA: o objetivo é medir tempos para definir padrões. Espera de Marca: analisar separadamente Retorno Marca/Executivo e Aguardando Feedback; Talento: Validação Talento. Rankings mostram associação, não causalidade.

## Código, estado e publicação

Python extrai, trata, aplica regras e calcula a Gold. Bronze, derivados, catálogo, quarentena, watermark e reservas diárias passam a ser **coleções internas em um arquivo SQLite no volume `/app/runtime` do executor**. Não são tabelas no PostgreSQL de consumo. O arquivo não é outro servidor/banco a administrar no DBeaver.

Esse estado preserva a evidência que pode sair da retenção da API Monday. A quarentena é exportável em CSV e o catálogo revisável em JSON. O consumidor só acessa a Gold. O volume runtime agora precisa de backup junto do PostgreSQL.

PK `interval_id`, UNIQUE quadro/projeto/ordem, índice único para última passagem, CHECKs de datas/duração/marcadores e NOT NULL protegem a Gold. Contratos Python validam as referências internas, IDs/SKs, datas, exclusões e sequência antes de publicar. Sem checkpoint compatível, o executor bloqueia a carga.

Publicação: grava checkpoint candidato durável, substitui a Gold e seu recibo em uma transação PostgreSQL, promove o checkpoint. O recibo fica no comentário da tabela, sem criar tabela de controle. Reinício recupera a versão confirmada; falha não avança o watermark. Detalhes e extensão de regras: [PRD da ELT](docs/PRD_ELT_REGRAS.md).

## Agenda e corte

Uma tentativa automática diária às **06:00 America/Sao_Paulo** (`0 6 * * *`). Deploy/reinício apenas espera o próximo horário. Uma reserva determinística por data, persistida no checkpoint sob lock PostgreSQL, impede repetir a tentativa após reinício, inclusive após falha. Não executar dois agendadores. Backfill/replay são operações manuais de manutenção, não uma segunda agenda.

**D+1:** a carga de 12/09 às 06h mede até 12/09 00:00, cobrindo o fim de 11/09. Eventos exatamente no corte entram no fechamento seguinte. `corte_local` informa o fechamento; `cadastro_referencia_utc` informa quando atributos foram observados. Nenhuma promessa de execução se VPS/API estiver indisponível; atraso deve aparecer no monitoramento.

## Operação e evolução

[OPERATIONS.md](OPERATIONS.md): deploy, migração, validação, recuperação. [QUARENTENA_E_IDENTIDADES.md](docs/QUARENTENA_E_IDENTIDADES.md): revisão sem tabela adicional. [VALIDACAO_OURO.md](docs/VALIDACAO_OURO.md): evidência observada.

Escopo atual: um quadro, um executor, transformação em memória, VPS provisória. Novas áreas devem declarar origem/grão/chaves/regras e não cruzar sistemas apenas por nome. IDs/SKs e contrato facilitam migração futura para BigQuery; acesso corporativo, orquestração e reconciliação real serão necessários. BigQuery não foi implantado. Backups/alertas externos e infraestrutura definitiva continuam conforme aceite provisório, sem contratação nova.
