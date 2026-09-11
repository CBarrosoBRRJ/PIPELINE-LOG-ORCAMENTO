# Manutenção deste projeto

Leia `PRD.md`, `docs/ARQUITETURA_E_GOVERNANCA.md` e o contrato executável antes de alterar regras, modelo ou publicação. O objetivo é medir permanência por etapa para estudar padrões; metas de prazo ainda não foram definidas.

- Preserve a Bronze original e os IDs/SKs. Não preencha NULL desconhecido com zero, data fictícia ou evento inventado. SLA total começa apenas na Entrada comprovada.
- Mudanças em dados devem declarar origem, grão, tipos, chaves, nulabilidade, tratamento, consumidores e ação em falha. Contratos portáteis e constraints do banco se complementam.
- Atualize documentação e evidências junto com código. Modelo/contrato: execute `scripts/generate_ddl.py` e `scripts/generate_contract_docs.py`. Semântica: atualize PRD, dicionário e KPIs afetados. Operação: atualize o guia de implantação/recuperação.
- Teste comportamentos e casos de falha relevantes, não só a implementação. Testes de integração usam PostgreSQL local e schemas isolados; não executar testes com dados fictícios no banco da VPS.
- PostgreSQL atual tem SOMENTE gold_projeto_status e pendencias_projeto. A segunda tabela foi explicitamente autorizada pelo usuário para consumir a lista de erros/dúvidas, substituindo a decisão anterior de CSV. As 19 tabelas técnicas foram excluídas após migrar o estado para runtime; não recriá-las. Novas remoções precisam de escopo explícito, backup e reconciliação. Não remover o volume/checkpoint ou alterar identidade silenciosamente.
- Segredos, `.env`, backups e dados brutos ficam fora do Git e dos logs. Não exibir valores rejeitados em mensagens de contrato.
- Descreva o que está implementado e o que é evolução futura. Executor/cron na VPS, D+1 fechado, BigQuery real, alertas externos e processamento distribuído só podem ser declarados prontos com evidência de implantação e validação.
- Para novas fontes/áreas, use o padrão de governança, namespace de identidade e correspondências explícitas; não presumir que IDs iguais de sistemas diferentes representam a mesma entidade.
