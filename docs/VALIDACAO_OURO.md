# Validação 3.1.0 — consumo direto e pendências

Ensaio concluído em 11/09/2026, 22:09 UTC, antes da publicação da nova versão na VPS. **112 testes passaram** (incluindo PostgreSQL local), Ruff e verificação de diff passaram. Imagem Docker 3.1.0 construída.

Backup PostgreSQL `runtime/backups/before_people_fix_20260911T215010Z.dump`, 490.052 bytes, restaurado em PostgreSQL 17 isolado: 3.330 linhas, 2.822 projetos, 3.330 IDs únicos. Checkpoint copiado do ensaio anterior, reconciliado com a Gold atual, e pareado ao recibo do banco restaurado. Backup adicional do estado real observado na VPS: `/app/runtime/backups/state_20260911T221143Z.sqlite3`.

No restore, migrate-consumption, replay, validate, validate-gold, quality-profile e health concluíram com sucesso. Inventário: gold_projeto_status e pendencias_projeto. Gold preservou 3.330 passagens/2.822 projetos; 511 trechos têm início comprovado e duração publicada. As 2.819 estimativas tiveram entrada/duração mascaradas como NULL no contrato público. Nenhuma mensagem de usuário excluído foi mantida como nome de responsável.

Pendências: 4.560 projetos únicos, sendo 1.738 excluídos da Gold e 2.822 com avisos não bloqueantes, principalmente história inicial incompleta. Isso não significa 4.560 projetos inválidos. Ambos os conjuntos usam o corte 11/09/2026 00:00 São Paulo; regra 2.2.1:88ed5c2b27f7f472. Replay não consultou Monday nem avançou watermark.

Hashes esperados no mesmo corte após implantação:
- Gold pública: `334e346b66936b923dc6fcda4777f22f4933d3ed888d0459b4540f6595a2d939`.
- Pendências: `acedaa3c45ef61129a5c3da6bc030a9fdc36cecad042139b0f5279f9cae9a171`.

Evidências privadas: runtime/v31_rehearsal_verified.json, runtime/people_fix_backup_verified.json. A publicação real na VPS está registrada na seção seguinte. PBIX/HTML não foram editados; documentação e SQL prontos para importar os campos atualizados.

## Publicação 3.1.0 confirmada na VPS

Código implantado: `5a7afe5` (main), versão 3.1.0 observada no container. Migração concluída em **11/09/2026 22:17:24 UTC**; replay concluído às **22:18:24 UTC**. check-db, validate, validate-gold, quality-profile e health passaram; `FINAL_VALIDATION_31 True` observado. Backup de estado após publicação: `/app/runtime/backups/state_20260911T221854Z.sqlite3`.

Consulta independente ao PostgreSQL às **22:19:34 UTC** confirmou exatamente duas tabelas no banco de usuário: `orcamento.gold_projeto_status` e `orcamento.pendencias_projeto`. As primeiras dez colunas são as do exemplo; a principal possui 33 campos e nenhuma coluna JSON. Os hashes das duas tabelas coincidiram com os do ensaio acima.

- 3.330 passagens, 2.822 projetos na principal; 23 retornos.
- Zero IDs de passagem duplicados; zero projeto/ordem duplicados; sequência contínua por projeto e exatamente uma última passagem.
- 4.560 linhas únicas de pendências; 1.738 exclusões sem interseção com a Gold.
- Quatro CHECKs, PK e UNIQUE da Gold validados; PK quadro/projeto das pendências validada.
- 511 durações com início comprovado; 2.819 estimativas ficam NULL no consumo, sem perda da evidência interna.
- IDs, SKs, status, sequência, retornos e tempos observados reconciliados com a publicação anterior.
- Fonte continua sendo a coleta das 19:51 UTC; corte **11/09 00:00 São Paulo**, sem nova coleta ou avanço de watermark.

Serviço ativo. Logs do processo iniciado às 22:14:44 UTC mostram `loop_started` e `loop_sleeping`, próxima execução **12/09/2026 06:00 -03:00**. A execução futura está agendada, ainda não observada. O único aviso de health é o registro antigo `concurrent_attempt_rejected`, preservado da versão anterior; não é falha desta publicação.

Evidência privada: `runtime/v31_vps_verified.json`. O teste de restauração não foi feito na VPS e nenhuma fixture fictícia foi inserida nela. Ao consumir, atualizar o inventário do DBeaver/reabrir a tabela e substituir as antigas consultas do Power BI pelos contratos atuais.

---

## Registros anteriores — inventários e regras históricos

# Validação — tabela única 3.0

## Preparação observada em 11/09/2026

- Backup `runtime/backups/before_gold_20260911T210739Z.dump` (6.834.280 bytes), fora do Git. Restore em PostgreSQL 17 isolado: 4.580 itens, 5.396 intervalos, 819 eventos brutos.
- Imagem 3.0 construída. Ensaio da migração com dados reais restaurados, sem API Monday: **19 tabelas removidas**, inventário final **somente gold_projeto_status**, todas as coleções reconciliadas com o checkpoint antes da exclusão.
- Gold preservada: **3.330 passagens / 2.822 projetos**. Fingerprint antes/depois `8d8ba8e5c6c126594a8a175253a07d7cb85d7f7e1a4a6caf453df23d9a3f9857`.
- Na cópia: check-db, validate, validate-gold, quality-profile (zero falhas críticas), preview-gold, replay, nova validate-gold e export-review passaram. Quarentena interna: 1.738 projetos; catálogo: 1.983 entradas.
- Corte preservado: 11/09 00:00 São Paulo; coleta 11/09 19:51:44.677066 UTC. Regra `2.2.0:88ed5c2b27f7f472`.
- VPS antes da migração: volume `/app/runtime` montado e gravável, UID 10001. Health antigo sinalizava tentativa concorrente não agendada de 20:05 UTC; não foi feita extração extra para apagar esse alerta.

Testes de integração usam somente PostgreSQL local e schemas isolados. Cobrem migração, rollback por dependência externa, preservação de registros, não recriação de auxiliares, unicidade, reserva diária entre processos, falha sem avanço do watermark, checkpoint ausente, recuperação após commit interrompido, revisão de catálogo e alteração externa da Gold.

Suíte final: **104 testes passaram**; Ruff e `git diff --check` passaram. Conexões SQLite são fechadas explicitamente, inclusive nos caminhos de falha; o teste de perda de volume foi executado no Windows.

## Aplicação 3.0 na VPS

Migração executada no container remoto em **11/09/2026 21:29:14 UTC (18:29 São Paulo)**, código `03e6119`, pacote 3.0.0. Resultado observado: `removed_tables=19`, `rows=3330`, `checkpoint_verified=true`. Gold preservada integralmente. `validate-gold` remoto passou às 21:29:58 UTC.

Consulta independente ao banco inteiro pela conexão externa confirmou: somente `orcamento.gold_projeto_status` (BASE TABLE), 3.330 passagens, 2.822 projetos, **zero duplicatas**, **zero sequências inválidas**, 23 retornos. PK, UNIQUE e quatro CHECKs validados; não há FKs para objetos removidos.

A versão **3.0.1** torna o fingerprint independente do cabeçalho gzip de Windows/Linux: calcula SHA-256 sobre JSON canônico descompactado. Comparação independente entre cópia restaurada Linux e VPS lida pelo Windows passou: `648685e885b08c38553f077ec5ba1254b173da180131054906e8e642bd5590d8`. O fingerprint anterior registrado acima era do envelope compactado em Linux; a alteração não modifica registros nem o formato de recuperação do checkpoint. Há teste específico de portabilidade.

O dump pré-migração com restore testado está guardado localmente. O executor mantém o checkpoint ativo e cópia antes da migração no volume persistente. Nenhuma tabela técnica foi movida para outro schema PostgreSQL.

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
