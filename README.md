# Monday → Python → tabela pronta para Power BI

Aplicação **3.0.0**: o PostgreSQL publica **somente `orcamento.gold_projeto_status`**, uma linha por projeto/status/passagem, com ordem, datas, duração, Marca, Talento, responsável e retorno.

O tratamento acontece em Python. Histórico bruto, controle incremental e quarentena ficam no arquivo privado do executor em `/app/runtime`; não existem tabelas auxiliares PostgreSQL após a migração. Importar uma única tabela no Power BI, sem relacionamentos internos.

## Guias

- [PRD e regras aprovadas](PRD.md)
- [ELT passo a passo e como acrescentar regras](docs/PRD_ELT_REGRAS.md)
- [Dicionário da Gold](docs/OURO_CONSUMO.md)
- [Power BI e medidas](docs/POWER_BI_PRD.md)
- [Revisão de nomes/quarentena](docs/QUARENTENA_E_IDENTIDADES.md)
- [Operação, backup e recuperação](OPERATIONS.md)
- [Validação da entrega](docs/VALIDACAO_OURO.md)

## Operação atual

Uma tentativa diária às **06h São Paulo**, corte dos tempos à meia-noite (D+1). Reiniciar o container não dispara coleta. Rodar comandos de manutenção no executor que possui o volume runtime correspondente ao banco.

```bash
sla-pipeline check-db
sla-pipeline validate
sla-pipeline validate-gold
sla-pipeline quality-profile
sla-pipeline health
```

Para migrar a instalação legada com 20 tabelas, após backup PostgreSQL com restauração testada e volume persistente validado:

```bash
sla-pipeline migrate-single-table
```

O comando verifica e guarda o histórico no volume, reconcilia os registros e remove explicitamente as 19 tabelas, sem CASCADE. Não executa backfill nem muda os dados da Gold. Instalação nova usa `backfill` antes de ativar `loop`. Não executar carga local contra a VPS sem seu checkpoint: isso falha deliberadamente para proteger o histórico.

Python 3.11+, PostgreSQL 16/17, Docker opcional para desenvolvimento. `.env`, runtime, dumps e catálogos de negócio nunca entram no Git. Testes usam PostgreSQL LOCAL em schemas isolados, nunca a VPS.
