# Pipeline de histórico por status — 3.1.0

Monday → tratamento Python → PostgreSQL para Power BI.

- `orcamento.gold_projeto_status`: passagens em ordem temporal, tempos comprovados, Marca, Talento, responsável, retorno e IDs.
- `orcamento.pendencias_projeto`: projeto/ID, valores originais, motivos, orientação de correção e se foi excluído da análise.
- Uma tentativa diária às 06h São Paulo, corte D+1 à meia-noite. Deploy não inicia coleta.
- Estado técnico privado no volume runtime; publicação atômica, sem tabelas auxiliares PostgreSQL.

Comece pelo [guia direto](docs/CONSUMO_DIRETO.md), [PRD](PRD.md), [Power BI](docs/POWER_BI_PRD.md) e [operação](OPERATIONS.md).

Instalação nova: `sla-pipeline init-db` e carga inicial manual `sla-pipeline backfill`. Atualização de instalação anterior: backup PostgreSQL+runtime, restore verificado, `sla-pipeline migrate-consumption`, `replay`, `validate-gold`, `health`. Não apagar o checkpoint. O serviço usa `sla-pipeline loop`.

Testes usam somente PostgreSQL local; segredos e dados operacionais ficam fora do Git. BigQuery corporativo permanece evolução futura.
