# Validação da implementação

Verificação em 10/09/2026 (São Paulo), com Monday real, PostgreSQL 16 em Docker e aplicação Python 3.11 no container.

| Verificação | Resultado |
|---|---|
| Testes automatizados | 39 passaram, incluindo PostgreSQL real |
| Backfill real | Sucesso; 707 eventos iniciais |
| Diário real | Sucesso; 1 novo evento e 385 já existentes relidos sem duplicação |
| Itens ativos | 4.541 |
| Itens na dimensão | 4.544; três conhecidos somente pelo histórico |
| Eventos distintos | 708 de 708 |
| Intervalos | 5.249 |
| Registros diários | 36.296 |
| Pessoas | 49 |
| Catálogo de colunas | 51 colunas; 11 atributos/colunas modelados |
| SKs dos itens | 4.544 distintas; nenhuma nula |
| Constraints PostgreSQL | 16 PKs, 49 FKs e 8 constraints UNIQUE |
| Status atual vazio na extração | Zero |
| Reprocessamento e reconciliação | `replay` e `validate` passaram |

Os testes verificam idempotência, rollback, lock de execução, paginação e borda incremental, timestamps, meia-noite local/horário de verão, reentradas, evento sem mudança, novo status, início exclusivo em Entrada, chaves substitutas, inconsistência ID/SK, referência órfã e migração aditiva de view existente. BQ possui testes de contrato/DDL/assertions; não foi homologado contra um projeto real.

## Limitações observadas na origem

A API informa criação do board em 03/09/2026. Há 4.153 itens sem transições disponíveis e 4.406 itens sem evento de início em Entrada. O pipeline preserva essas lacunas: não apresenta um SLA total comprovado para esses itens. As permanências inferidas têm flags de qualidade; não equivalem ao histórico integral anterior à criação/cópia do quadro.

O primeiro evento disponível na carga é de 03/09/2026 14:55:29 UTC. Os dados continuavam mudando durante a implementação; as contagens acima representam o corte da execução diária de 11/09/2026 00:29:55 UTC (10/09/2026 21:29:55 em São Paulo).

Este quadro registra a validação local anterior à transferência. Em 11/09/2026, o PostgreSQL remoto foi configurado e as 16 tabelas foram transferidas com igualdade integral de conteúdo, registrada em `runtime/vps_migration.json`. O executor/cron na VPS ainda não foi instalado. Janela D+1 ainda é uma proposta no PRD; os dados aqui foram calculados até o instante da execução. Nenhuma alteração foi feita no quadro Monday.


## Configuração e migração para a VPS — 11/09/2026

- PostgreSQL remoto 17.11, banco `dados_globo`, schema `rede_globo`.
- 16 tabelas reconciliadas com a origem local por contagem e hash do conteúdo de todas as linhas; chaves naturais e SKs preservadas.
- 44 testes automatizados passaram. A integração foi executada no PostgreSQL local com schemas de teste, sem inserir dados fictícios no banco remoto.
- Docker remoto construído e `check-db` executado com sucesso. O container recebe variáveis de ambiente; não contém o `.env` na imagem.
- Configurações duplicadas, prefixo `DB_*` e sintaxe inválida recebem diagnóstico sem exibir segredos. Testado também o carregamento somente por variáveis de ambiente no container.
- Conexão externa testada sem TLS; rede interna/túnel ou TLS precisam ser configurados na implantação definitiva, conforme `OPERATIONS.md`.

### Primeiro diário gravando na VPS

Execução Docker nesta máquina, corte em 11/09/2026 às 15:17:14 UTC (12:17:14 São Paulo), concluída às 15:19:56 UTC. Sucesso: 4.559 itens ativos, 4.563 itens na dimensão, 769 eventos totais (61 novos), 5.329 intervalos, 40.924 registros diários. `validate` e `health` passaram contra esse destino. Origem Monday permaneceu somente leitura.

Constraints verificadas no destino: {'f': 49, 'u': 8, 'p': 16}. SKs dos itens: {'items': 4563, 'distinct_sks': 4563, 'null_sks': 0}.

Backup remoto `runtime/backups/vps_rede_globo_validated.dump` (6.099.439 bytes) restaurado com sucesso em PostgreSQL 17 temporário isolado, sem portas publicadas. Conferidos 4.563 itens e 40.924 registros diários; container de teste removido.

## Consultas analíticas — 11/09/2026

As oito consultas de `sql/006_analise_projeto.sql` foram executadas em transação somente leitura na VPS: localização, trajetória, horas por status com qualidade, resumo, diagnósticos, estatísticas de visitas encerradas, fila atual e corte. Validado projeto com múltiplas visitas à mesma etapa. Nenhuma nova tabela ou regra de duração foi criada para essas consultas.

Os exemplos SQL executáveis do guia `RELACIONAMENTOS_E_KPIS.md` também foram validados. O join dos intervalos com dimensões pelas SKs preservou a contagem de visitas e a soma de minutos. O exemplo com a futura base de orçamentos é ilustrativo e não foi executado.
