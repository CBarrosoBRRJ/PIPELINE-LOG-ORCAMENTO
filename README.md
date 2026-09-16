# Pipeline de permanência por status — 4.0.0

Monday → joins, regras e horas úteis em Python → **BigQuery `viu_agenciamento.sla_orcamento`**.

- Uma única tabela BigQuery, reutilizada em todas as cargas; uma linha por passagem do projeto em um status.
- `duracao_horas_uteis`: segunda a sexta, 10h–13h e 14h–19h, fuso São Paulo, feriados nacionais automáticos.
- Horas corridas preservadas em `duracao_horas`; histórico desconhecido continua NULL.
- Cloud Run Job executa `daily`, Cloud Scheduler dispara 06h São Paulo; fechamento D+1.
- Evidências, checkpoint, pendências, calendário e controle ficam privados no Cloud Storage.
- Carga atômica, exclusão/reinclusão, reserva diária, trava distribuída e recuperação por job ID.

Comece pelo [roteiro para iniciantes](docs/APRENDER_GCP.md) e pelos [prompts por etapa para o GPT Web](docs/PROMPTS_GPT_WEB.md). Referência técnica: [deploy GCP/GitHub](docs/DEPLOY_GCP.md), [PRD](PRD.md), [dicionário](docs/OURO_CONSUMO.md), [contrato](docs/CONTRATO_SLA_ORCAMENTO.md) e [operação](OPERATIONS.md).

Instalação local: `python -m pip install -e '.[dev]'`. Copie `.env.example` e use ADC. Testes: `python -m pytest -q`. Calendário: `sla-pipeline calendar --year 2026`.

Migração: instale o extra `.[migration]` somente na máquina que lerá PostgreSQL. `export-bq` lê origem + checkpoint sob lock e importa tudo no GCS, publicando somente a projeção Gold. Alternativa offline: `import-state --checkpoint-file CAMINHO --generation GERACAO_DO_RECIBO`. Veja [migração do histórico](docs/MIGRACAO_HISTORICO.md). Não apagar origem/backup antes da reconciliação.

Implementação e testes locais não equivalem a implantação: GCP real depende de provisionar bucket/IAM/segredo e validar o primeiro job. Não há escritor PostgreSQL, cron interno, Compose ou Databricks. O importador de origem é somente leitura, isolado em migration/. Veja [limpeza e evidências](docs/VALIDACAO_GCP.md).
