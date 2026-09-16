# PRD — histórico por status pronto para consumo

Aplicação **4.0.0**, regras de evidência **2.2.1**, contrato físico GCP **5**. Decisão de 16/09/2026: destino definitivo é **somente `gglobo-viu-dados-hdg-prd.viu_agenciamento.sla_orcamento` no BigQuery**. Nenhuma tabela técnica, de pendências, staging ou por data é criada. As duas tabelas PostgreSQL anteriores são fonte legada de migração e não são excluídas por este código.

Uma linha da principal representa uma passagem do projeto por um status. Os primeiros campos são Ordem, Projeto, Status, Entrada, Saída, Duração, Marca, Talento, Responsável Orçamento e Retorno. `item_id` original e chaves de integração são preservados. A numeração `ordem_etapa` segue a sequência temporal por projeto; consumir com `ORDER BY item_id, ordem_etapa`.

## Regras essenciais

- O processo começa em Entrada, mas a primeira evidência disponível pode ser posterior. Não inventar eventos, datas nem tempos.
- **Entrada/duração inferidas ficam NULL no consumo.** Estimativas antigas ficam somente no checkpoint privado. Qualidade acompanha cada registro e a pendência explica a lacuna.
- Saída nula identifica a última passagem até o corte. Um status terminal sem saída não significa projeto ainda em andamento.
- Retorno é a segunda ou posterior passagem pelo mesmo status; não é duplicidade.
- Excluir o projeto inteiro por múltiplos talentos, Squad, Talento e Interveniência preenchidos, coletivo/não pessoa, Interveniência sem identidade revisada ou quarentena manual de Marca/Talento. Ausência isolada de Marca/Talento não exclui.
- Aliases dependem de revisão. Não unir pessoas/marcas automaticamente por similaridade de texto.
- Orçamento vem da coluna people de mesmo nome, atualmente `person`. Não usar mensagens de usuário excluído como nome. Atributos são do cadastro na coleta, não prova de autoria histórica.
- Tempo tem duas medidas: `duracao_horas` corridas e `duracao_horas_uteis` dentro do expediente seg-sex, 10h–13h e 14h–19h, America/Sao_Paulo. Descontar feriados brasileiros da categoria PUBLIC da biblioteca holidays, calculados para todos os anos do intervalo; `BUSINESS_HOLIDAYS` acrescenta dias locais/recessos. Carnaval e Corpus Christi não são excluídos automaticamente. Calendário e versão ficam registrados junto da publicação. Rankings usam passagens observadas, encerradas e consistentes (`elegivel_comparacao`). Ainda não há metas de SLA: estamos estudando tempos.
- Terminais atuais: Encerrado, Declinado pelo Mercado, Declinado Internamente. Novos rótulos são descobertos; terminal depende de configuração.

## Publicação e atualização

Python extrai, normaliza, realiza todos os joins, reconstrói eventos, aplica regras e calcula horas úteis antes de carregar a tabela pronta no BigQuery. Estado e evidências ficam em gerações imutáveis JSON gzip no Cloud Storage. A publicação inteira usa um load job atômico WRITE_TRUNCATE com schema explícito; não há tabelas auxiliares. Validação Python substitui PK/FK/CHECK não impostos pelo BigQuery. Uma tabela inteira é dedicada a um único pipeline/quadro.

Antes da carga, o checkpoint candidato e o artefato NDJSON são persistidos e um journal GCS registra job ID determinístico. O ponteiro ativo só avança após sucesso e fingerprint completo da tabela real. Em falha de comunicação, a retomada resolve o mesmo job antes de permitir outra carga; falha terminal preserva a publicação anterior. A trava GCS por geração não expira automaticamente: morte abrupta exige confirmar que o executor parou e liberar a geração exata.

Uma tentativa automática diária às **06:00 America/Sao_Paulo**, via Cloud Scheduler → Cloud Run Job. Publicar a imagem não executa coleta; executar o Job inicia daily e ele termina ao concluir. Reserva persistente por data impede duplicar a tentativa. **D+1**, cortando à meia-noite do dia de execução: 12/09 às 06h fecha até o fim de 11/09. Eventos exatamente no corte entram no próximo fechamento. Retries de lote ficam desativados; requisições Monday têm retries próprios. Finais de semana também executam: capturam mudanças, mas não acumulam horas úteis. A agenda não garante disponibilidade externa.

`pendencias_projeto` é um artefato JSON privado no GCS: uma linha por projeto, com IDs, valores originais, motivos, orientação e `excluido_da_analise`. Correções no Monday são reavaliadas na próxima carga; a pendência resolvida desaparece e o projeto elegível volta à Gold. Históricos antigos ausentes não são recuperados por simples alteração do status atual. Catálogo revisado pode ser reaplicado com replay.

## Documentação e manutenção

- [Perguntas de negócio e KPIs](docs/KPIS_GCP.md).
- [Dicionário de todos os campos públicos](docs/OURO_CONSUMO.md).
- [Implantação GCP e GitHub](docs/DEPLOY_GCP.md).
- [Arquitetura e contratos operacionais](docs/ARQUITETURA_GCP.md).
- [Operação, migração e recuperação](OPERATIONS.md).
- [Evidências de validação GCP](docs/VALIDACAO_GCP.md).

Código GCP implementado; implantação corporativa ainda não executada. IDs/SKs preservados, pendências fora do BQ, horas úteis adicionadas ao contrato. Consulte [DEPLOY_GCP.md](docs/DEPLOY_GCP.md). A VPS permanece apenas como fonte do par PostgreSQL/checkpoint até migração validada. Nenhum recurso GCP foi provisionado nesta alteração.
