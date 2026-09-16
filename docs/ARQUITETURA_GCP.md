# Arquitetura GCP — única tabela de consumo

Aplicação 4.0.0, contrato físico 5. Origem Monday; uma passagem por projeto/status; todos os joins e cálculos em Python. A identidade e as regras de evidência permanecem as da versão anterior. Cloud Run executa uma vez e termina; Cloud Scheduler fornece o horário diário. Não há Cloud SQL, Spark, Dataflow ou serviço HTTP.

## Contratos entre componentes

| Componente | Origem/grão/chave | Persistência e tratamento | Consumidor / ação em falha |
|---|---|---|---|
| Bronze e coleções internas | Monday; chaves e tipos de models/schemas.py | JSON gzip imutável por geração no GCS; envelopes preservados | Transformação/replay; contrato inválido bloqueia |
| sla_orcamento | Projeção Python; uma passagem; interval_id | INT64, STRING, BOOL, TIMESTAMP UTC, DATETIME local, FLOAT64; unknown NULL; schema em models/bq_consumption.py | BigQuery/BI; batch inteiro atômico |
| pendências | Uma linha por projeto, board_id/item_id | JSON privado associado à geração; originais, motivos e correção | Equipe de revisão; não publicado no BQ |
| calendário | Política de expediente e feriados por versão | JSON privado: datas efetivas, versão da biblioteca, adicionais | Auditoria de horas úteis; replay aplica revisão |
| control.json | Um pipeline/tabela dedicado | Ponteiro active + pending, identidade, checksum; CAS por geração GCS | Executor/recuperação; conflito bloqueia |
| writer.lock | Um escritor para o destino/prefixo | Criação condicional if_generation_match=0; sem expiração | CLI/Job; concorrência falha antes da extração |
| etl_run / watermark | Coleções privadas do checkpoint | Reserva determinística por pipeline+dia; marco avança com publicação | Agenda/health; falha não avança watermark |

## Protocolo de publicação e falha

1. Adquirir lock e resolver pending anterior; conferir identidade do destino e estado.
2. Reservar tentativa diária no estado durável antes de Monday.
3. Capturar cadastro/atividades, juntar ao histórico, deduplicar por chaves, reconstruir intervalos, aplicar elegibilidade e corte D+1.
4. Projetar campos públicos, calcular horas úteis e validar tipos, evidência, chaves, sequência e horas.
5. Gravar state.json.gz e verificar leitura/checksum; gravar NDJSON, pendências e calendário em generations/UUID/.
6. Gravar pending com candidate, URI, hash e job ID conhecido, condicional à geração atual de control.json.
7. Executar load job WRITE_TRUNCATE para a única tabela; sem staging. Até completar, leitores continuam vendo a carga anterior.
8. Ler schema e todas as linhas do destino com TableData API; verificar fingerprint. Só então promover active e limpar pending via CAS.

GCS e BigQuery não possuem transação distribuída. Pode existir uma curta janela em que a nova tabela BQ já está visível e o ponteiro GCS ainda é pending. A retomada consulta o mesmo job ID, confirma resultado e termina a promoção. Resultado desconhecido preserva pending; falha terminal comprovada descarta apenas pending (arquivos são mantidos) e conserva active. Nenhum novo load é permitido antes da resolução. Sem autorização de cleanup, não apagar gerações.

Lock não é lease com timeout: o escritor pode continuar vivo depois de uma pausa. Expirar automaticamente permitiria sobrescrita por escritor antigo. Se o processo morrer, o operador cancela/confirma término no Cloud Run, identifica geração da trava e libera exatamente essa geração. O BQ job eventualmente ainda rodando é reconciliado pelo journal na recuperação.

Não há histórico de snapshots diários duplicados na tabela pública. Ela guarda passagens históricas atualizadas até o corte mais recente. Substituição integral é adequada ao processamento atual que reconstrói tudo; reduz complexidade e mantém exclusões/correções. Clustering por board_id/item_id/status_id; sem partição artificial por data de carga. Escalar para deltas por projeto somente após medir histórico, memória e duração.

## Limites operacionais

- Um quadro/coluna por destino; todas as execuções devem usar o mesmo bucket/prefixo. IAM deve restringir outros escritores.
- Snapshot/checkpoint ainda cresce e é processado em memória; cache evita baixar repetidamente dentro do mesmo lock. Não é processamento distribuído.
- Dados inválidos da API ainda podem falhar no parsing antes da persistência; landing independente de envelopes rejeitados é evolução futura.
- Unknown continua NULL. A Gold não prova existência de eventos que a fonte não disponibilizou.
- Python valida integridade; BigQuery não impõe PK/UNIQUE/FK/CHECK como PostgreSQL. Schema REQUIRED e validações do load complementam Python.
- Alterações legais futuras no calendário exigem atualizar a dependência, revisar calendário gerado e executar replay. Anos futuros são calculados automaticamente pelas regras conhecidas.
- Código e infraestrutura estão preparados, mas a primeira execução corporativa e alertas externos ainda precisam de homologação.
