# Validação — tabela única 3.0

## Preparação observada em 11/09/2026

- Backup `runtime/backups/before_gold_20260911T210739Z.dump` (6.834.280 bytes), fora do Git. Restore em PostgreSQL 17 isolado: 4.580 itens, 5.396 intervalos, 819 eventos brutos.
- Imagem 3.0 construída. Ensaio da migração com dados reais restaurados, sem API Monday: **19 tabelas removidas**, inventário final **somente gold_projeto_status**, todas as coleções reconciliadas com o checkpoint antes da exclusão.
- Gold preservada: **3.330 passagens / 2.822 projetos**. Fingerprint antes/depois `8d8ba8e5c6c126594a8a175253a07d7cb85d7f7e1a4a6caf453df23d9a3f9857`.
- Na cópia: check-db, validate, validate-gold, quality-profile (zero falhas críticas), preview-gold, replay, nova validate-gold e export-review passaram. Quarentena interna: 1.738 projetos; catálogo: 1.983 entradas.
- Corte preservado: 11/09 00:00 São Paulo; coleta 11/09 19:51:44.677066 UTC. Regra `2.2.0:88ed5c2b27f7f472`.
- VPS antes da migração: volume `/app/runtime` montado e gravável, UID 10001. Health antigo sinalizava tentativa concorrente não agendada de 20:05 UTC; não foi feita extração extra para apagar esse alerta.

Testes de integração usam somente PostgreSQL local e schemas isolados. Cobrem migração, rollback por dependência externa, preservação de registros, não recriação de auxiliares, unicidade, reserva diária entre processos, falha sem avanço do watermark, checkpoint ausente, recuperação após commit interrompido, revisão de catálogo e alteração externa da Gold.

Suíte final: **103 testes passaram**; Ruff e `git diff --check` passaram. Conexões SQLite são fechadas explicitamente, inclusive nos caminhos de falha; o teste de perda de volume foi executado no Windows.

## Aplicação 3.0 na VPS

Pendente de registrar a execução remota após o push desta versão. O ensaio acima não é alegação de migração já concluída na VPS.

## Registro histórico da publicação 2.2 (anterior à remoção das tabelas)

Evidências observadas em 11/09/2026. Estes resultados validam o corte publicado; não são garantia de completude do histórico do Monday ou de execução futura.

## Publicação no PostgreSQL da VPS

Banco `dados_globo`, schema `orcamento`. Regra **`2.2.0:88ed5c2b27f7f472`**. Publicação manual a partir da coleta de **11/09 19:51:44.677066 UTC** (16:51 São Paulo), sem nova chamada ao Monday e sem avançar o watermark.

Corte Gold: **11/09/2026 00:00 São Paulo (03:00 UTC)**, fechando os tempos até o fim de 10/09. A execução de 12/09 às 06h deverá fechar o fim de 11/09.

| Verificação | Resultado |
|---|---:|
| Projetos técnicos da coleta | 4.580 |
| Passagens técnicas completas | 5.396 |
| Projetos elegíveis anteriores ao corte | 2.822 |
| Passagens da Gold | 3.330 |
| Projetos na quarentena | 1.738 |
| Projetos elegíveis cuja primeira passagem é posterior/igual ao corte | 20 |
| Retornos na Gold | 23 |
| Passagens observadas encerradas elegíveis à comparação | 247 |

Os motivos de quarentena se sobrepõem: identidade de Interveniência pendente 1.653; ambas as colunas 16; Squad 107; não individual identificado 4; múltiplos talentos 4. Não somar motivos como projetos distintos.

Na Gold, 2.707 projetos têm talento proveniente do cadastro de exclusivos e 115 não têm talento informado. Isso não representa aprovação humana de toda grafia. Responsável de Orçamento: 2.372 identificados, 31 com texto cadastral sem correspondência individual segura entre todos os nomes/IDs, 419 ausentes. Ausência é explicitada, não preenchida artificialmente.

## Integridade e recuperação

- Backup prévio: `runtime/backups/before_gold_20260911T202758Z.dump`, 7.013.809 bytes, fora do Git.
- Restore concluído em PostgreSQL 17 isolado, conferindo 4.580 itens, 5.396 intervalos e 819 eventos brutos.
- Reconstituição dos itens, status, Prata, intervalos, fatos diários e resumos produziu hashes iguais aos existentes.
- Gold, quarentena, catálogo/versão e diagnósticos publicados sob lock e transação.
- Bronze e watermark permaneceram iguais.
- Segunda preparação/publicação produziu hashes iguais nas 20 tabelas: nenhuma cópia ou alteração de conteúdo no mesmo corte.
- PK de intervalo, UNIQUE de projeto/ordem e FKs fazem parte do schema. Testes reais rejeitam duplicidade e referência inválida, verificando rollback.
- Saídas antigas substituídas: `gold_intervals_local`, `gold_project_status`, `gold_status_metrics`, `gold_status_bottlenecks`. Remoção explícita sem CASCADE; o código atual não as recria.

Evidências locais: `runtime/gold_publication_report.json`, `runtime/gold_final_verification.json` e `runtime/gold_backup_verified.json`. Dumps, segredos e cadastros não vão para o GitHub.

## Testes e operação

Após publicação, `validate` confirmou 4.580 itens técnicos; `validate-gold` executado na imagem Docker confirmou 3.330 linhas; `quality-profile` conferiu as 20 tabelas com **zero falhas críticas**. Consulta de integridade confirmou zero IDs duplicados, zero interseção Gold/quarentena, UNIQUE de ordem presente e **zero views remanescentes** no schema. Verificações concluídas em 11/09/2026 às 20:48 UTC.

**96 testes passaram**, incluindo PostgreSQL local isolado, corte à meia-noite, transição exatamente no limite, retornos, reserva diária após sucesso/falha, reinício sem carga imediata, catálogo, quarentena e reinclusão com os mesmos IDs. Ruff e verificação de diff passaram. Imagem Docker `sla-orcamento:2.2.0` construída com sucesso.

Duas execuções da versão anterior na VPS foram observadas com sucesso, às 19:47 e 19:51 UTC; isso comprova conectividade/coleta, mas não o novo agendamento. O loop novo espera o próximo horário e usa reserva diária durável. O disparo futuro das 06h só poderá ser declarado observado depois que acontecer. O estado efetivo do deploy é conferido separadamente no EasyPanel ao final da atualização.

A validação do banco não prova que todos os nomes estejam corretos ou que a origem tenha todo o histórico. Pendências classificadas saem dos KPIs e ficam na quarentena. Trechos inferidos continuam identificados. Cadastro e responsáveis são observados na coleta, não historicamente comprovados por passagem.

PBIX/HTML não foram editados. DAX fornecido como arquivo; não executado em motor Power BI nesta validação. BigQuery corporativo, alerta externo e backup recorrente continuam fora desta implantação provisória.
