# Manutenção deste projeto

Leia PRD.md, docs/ARQUITETURA_E_GOVERNANCA.md, docs/ARQUITETURA_GCP.md e os contratos executáveis antes de alterar regras, modelo ou publicação.

- Destino exclusivo: gglobo-viu-dados-hdg-prd.viu_agenciamento.sla_orcamento. Estado, Bronze, pendências e controle privados no GCS. Cloud Scheduler + Cloud Run Job daily.
- O objetivo é estudar permanência por etapa; não há metas de prazo. Todos os joins e horas úteis em Python: seg-sex 10–13h / 14–19h, feriados BR PUBLIC automáticos e extras configuráveis.
- Preserve Bronze e IDs/SKs. Não preencher desconhecido com zero ou evento/data inventados. Total começa apenas na Entrada comprovada.
- Mudanças declaram origem, grão, tipos, chaves, nulabilidade, tratamento, consumidores e ação em falha.
- Modelo/contrato: execute scripts/generate_ddl.py e scripts/generate_contract_docs.py; atualize dicionário, PRD, KPIs e testes. Operação: atualize implantação/recuperação.
- PostgreSQL/SQLite são apenas origem de migração. migration/readers.py é somente leitura; não reintroduzir escritor PostgreSQL, cron/VPS ou tabelas técnicas BQ.
- Não apagar .env, volumes/checkpoint, backups ou tabelas reais. Remoções de dados precisam de escopo explícito, backup e reconciliação. Testes reais somente em ambientes locais/isolados opt-in.
- Segredos, dumps, dados brutos, credenciais e tfstate ficam fora do Git/logs. Nunca exibir valores rejeitados ou pedir chaves no chat.
- Diferenciar implementado/testado localmente de implantado/homologado. Alertas, GCP real e agendamento observado exigem evidência.
- Outras fontes exigem namespace e correspondências explícitas; IDs iguais não provam identidade entre sistemas.
