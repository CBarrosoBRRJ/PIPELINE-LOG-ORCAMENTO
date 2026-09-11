# BigQuery e Databricks

Contrato atual 2.2.0: inclui Gold de passagens e quarentena. O agendamento com reserva diária foi homologado no PostgreSQL; planejar o equivalente corporativo na migração. Não houve implantação BigQuery real nesta etapa.

## Migrar PostgreSQL → BigQuery

O adapter `db/bq.py` implementa o mesmo contrato do PostgreSQL. A lógica de extração e transformação não muda. Preencha `BQ_PROJECT`, `BQ_DATASET=sla_orcamento_pdd`, `BQ_LOCATION` e `BQ_KEYFILE` no mesmo `.env`. Sem keyfile, usa Application Default Credentials.

```bash
python -m pip install -e '.[bigquery]'
sla-pipeline export-bq
```

O comando cria o dataset/tabelas, lê PostgreSQL sob lock, carrega staging com TTL de 24h, executa MERGE por chave natural e confere contagens. Views legadas não são criadas. Publica o watermark junto aos dados. Ele nunca apaga tabelas de destino; remove apenas staging com UUID criado pela própria execução. O processo não constitui espelhamento contínuo de exclusões em Bronze. Para migração inicial, use um dataset novo e reconciliar também Gold/quarentena/corte/horas.

Depois da conferência, pare o cron PostgreSQL, configure `TARGET_DB=bigquery` e rode `daily`/`validate`. A Bronze migrada permite continuar do watermark sem novo backfill. Para retornar ao PostgreSQL, restaure o backup e reexecute o histórico necessário; não aponte duas agendas para destinos distintos esperando sincronização automática.

## Controle de execução e IAM

O adapter BQ publica todas as alterações em uma transação de múltiplas instruções. A carga de arquivos acontece em tabelas staging antes da transação. Use **um único scheduler/worker por board**: o lock BQ do MVP é local ao host e não é uma trava distribuída. Uma implantação com múltiplos workers exige adicionar um lease distribuído antes de habilitar concorrência.

Conceda à conta de serviço permissão de jobs e escrita no dataset de destino. O Docker padrão instala somente o MVP PostgreSQL; para BQ, crie uma imagem com o extra `[bigquery]` e monte o keyfile fora da imagem. Não copie credenciais para o repositório.

## Modelagem

[sql/bq/001_schema.sql](../sql/bq/001_schema.sql) é o DDL equivalente com placeholders de projeto, dataset e região. O CLI cria os objetos automaticamente pelo mesmo metadata. Eventos particionam por `DATE(event_at_utc)`, snapshots por `snapshot_date`, intervalos por início, fatos diários por `dt`; clustering por board/item/status quando presentes. PKs e FKs no BQ são `NOT ENFORCED`. O adapter executa ASSERT de unicidade, não nulidade de chaves e ausência de órfãos na mesma transação, antes do commit. Um único escritor continua obrigatório. Essas verificações leem as tabelas publicadas do board e têm custo de consulta.

`gold_status_metrics` usa PERCENTILE_CONT exato, com o mesmo grão das views PostgreSQL. O JSON bruto é persistido em colunas JSON; datas UTC em TIMESTAMP e datas locais em DATE.

## Consumo no Databricks

Sem BQ: use o conector JDBC PostgreSQL, credenciais em secret scope e usuário somente de leitura. Leia fatos e dimensões num corte consistente depois do sucesso do pipeline. Exemplo de notebook em [scripts/databricks_consume.py](../scripts/databricks_consume.py), sem credenciais embutidas.

Com BQ: use o Spark BigQuery connector compatível com o runtime do cluster e autenticação da conta de serviço/identidade de trabalho. Leia as tabelas pelo nome totalmente qualificado, mantendo `bronze_*_raw`, `silver_*_stg` e `fct_*`. Use `dt`/datas de partição para cargas incrementais no Delta; intervalos abertos e eventos atrasados precisam de MERGE, não apenas append.

Valide por board: contagem de eventos, chaves distintas, soma de minutos por item, contagens por status atual e intervalo temporal. BQ e Databricks não foram provisionados no ambiente local; a validação real do MVP usa PostgreSQL.
