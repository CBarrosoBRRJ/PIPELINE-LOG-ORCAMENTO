# Migrar evidências sem alterar a origem

O executor antigo foi informado como desligado pelo usuário. Não religar o deploy da VPS ao atualizar main. O repositório atual não contém escritores PostgreSQL nem scripts de exclusão/migração do banco antigo.

## Antes de importar

1. Confirme que cron, aplicação e qualquer execução manual antiga estão parados.
2. Identifique o PostgreSQL com somente gold_projeto_status e pendencias_projeto e o runtime SQLite da mesma instalação. Não imprimir credenciais.
3. Peça ao responsável pela origem um pg_dump privado e uma cópia consistente do SQLite usando a API backup do SQLite, incluindo a geração confirmada no recibo da Gold. Copiar apenas o arquivo principal enquanto há escritor/WAL ativo não garante consistência.
4. Restaure o par em ambiente isolado e confira a reconciliação. A versão histórica fd8226e no Git contém os procedimentos anteriores; consultar sem executar exclusões antigas em produção.
5. Guarde cópia protegida antes de importar. Não mover o único original, não subir checkpoint no GitHub nem embuti-lo na imagem.

## Caminho recomendado: origem disponível

Na máquina autorizada a ler a origem, instale `python -m pip install -e '.[migration]'`. Configure `.env.gcp` usando `.env.example` + campos de `migration.env.example`. Autentique Google por ADC/impersonação aprovada. Use RUNTIME_DIR da cópia correspondente e PG_SCHEMA correto.

```bash
sla-pipeline --env-file .env.gcp export-bq
sla-pipeline --env-file .env.gcp validate
sla-pipeline --env-file .env.gcp validate-gold
```

O importador abre transação REPEATABLE READ READ ONLY e adquire a mesma chave advisory lock da instalação antiga. Confere inventário, recibo storage=4, identidade do pipeline, geração exata e checksum SQLite. Compara as duas tabelas de consumo com a projeção do checkpoint antes de gravar no GCP. Não executa CREATE, UPDATE, INSERT, DELETE, DROP ou COMMENT na origem. Driver psycopg é opcional e não é instalado na imagem diária.

Destino precisa estar vazio de estado de negócio. Uma tabela BQ sem recibo GCS bloqueia; não apagar para contornar o bloqueio. Resolver a origem do conflito.

## Alternativa offline

Com uma cópia consistente e a geração confirmada do recibo:

```bash
sla-pipeline --env-file .env.gcp import-state --checkpoint-file /CAMINHO/backup.sqlite3 --generation GERACAO_CONFIRMADA
sla-pipeline --env-file .env.gcp validate-gold
```

Este caminho verifica geração, checksum, contratos e identidade, mas não pode comparar o arquivo com PostgreSQL ausente. Exige que a origem tenha sido reconciliada antes de gerar/entregar o par. Não escolher geração pelo horário ou pelo nome do slot pending.

## Aceite

Comparar IDs e quantidades, passagens e retornos, unknown NULL, última data publicada e amostra de horas úteis. Guardar recibos e backup. Só depois executar daily e ligar a agenda. Aposentadoria/exclusão da VPS, banco ou backups é decisão separada, fora desta limpeza de código.
