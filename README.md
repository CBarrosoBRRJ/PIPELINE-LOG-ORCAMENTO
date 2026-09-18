# Pipeline de permanência por status — PPD — 4.0.0

Monday → joins, regras e horas úteis em Python → **BigQuery `viu_agenciamento.sla_orcamento`**.

**Continuidade (18/09/2026):** para atualizar a cópia do VS Code a partir da `main`
e preparar a evolução para múltiplas tabelas, siga
[Continuar no VS Code](docs/CONTINUAR_NO_VSCODE.md). Essa evolução ainda não foi
implementada; o contrato abaixo descreve a versão atual de uma tabela.

- Uma única tabela BigQuery, reutilizada em todas as cargas; uma linha por passagem do projeto em um status.
- `duracao_horas_uteis`: segunda a sexta, 10h–13h e 14h–19h, fuso São Paulo, feriados nacionais automáticos.
- Horas corridas preservadas em `duracao_horas`; histórico desconhecido continua NULL.
- Cloud Run Job executa `daily`, Cloud Scheduler dispara 06h São Paulo; fechamento D+1.
- Evidências, checkpoint, pendências, calendário e controle ficam privados no Cloud Storage.
- Carga atômica, exclusão/reinclusão, reserva diária, trava distribuída e recuperação por job ID.

Comece pelo [roteiro para iniciantes](docs/APRENDER_GCP.md) e pelos [prompts por etapa para o GPT Web](docs/PROMPTS_GPT_WEB.md). Referência técnica: [deploy GCP/GitHub](docs/DEPLOY_GCP.md), [PRD](PRD.md), [dicionário](docs/OURO_CONSUMO.md), [contrato](docs/CONTRATO_SLA_ORCAMENTO.md) e [operação](OPERATIONS.md).

Instalação local opcional: `python -m pip install -e '.[dev]'`. Prepare `.env.gcp` a partir de `.env.example`, preservando qualquer `.env` antigo, e use ADC. Testes: `python -m pytest -q`. Calendário: `sla-pipeline --env-file .env.gcp calendar --year 2026`. O Cloud Run usa variáveis e Secret Manager, não o `.env` do computador.

**Roteiro escolhido: instalação nova, sem importar o banco/checkpoint anteriores.** Depois de provisionar GCP e publicar o Job pelo GitHub, execute `init-db`, `backfill` e as validações descritas no [guia de deploy](docs/DEPLOY_GCP.md). Só então teste `daily` e ative a agenda das 06h. A primeira carga recupera apenas o histórico ainda disponível no Monday; tempos sem evidência permanecem NULL. Não crie a tabela manualmente e não exclua dados antigos.

Importação legada é alternativa opcional, fora desse roteiro: exige extra `.[migration]` e par consistente PostgreSQL/checkpoint. Consulte [migração do histórico](docs/MIGRACAO_HISTORICO.md) apenas se a decisão mudar antes de inicializar o destino; não combinar importação com uma base nova já populada.

Implementação e testes locais não equivalem a implantação: GCP real depende de provisionar bucket/IAM/segredo e validar o primeiro job. Não há escritor PostgreSQL, cron interno, Compose ou Databricks. O importador de origem é somente leitura, isolado em migration/. Veja [limpeza e evidências](docs/VALIDACAO_GCP.md).

O projeto é da área **PPD**; pacote Python `sls_orcamento_ppd` (distribuição `sls-orcamento-ppd`). Após atualizar uma instalação local existente, execute novamente `python -m pip install -e ".[dev]"`. Os namespaces históricos com `pdd` usados em IDs/SKs, identificação do pipeline e leitura de migração são preservados por compatibilidade dos dados; não representam a área atual.
