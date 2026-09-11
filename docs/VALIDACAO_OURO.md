# Validação e publicação da Gold 2.0

Esta página registra evidências observadas, não garantias de futuras execuções. Publicação inicial em 11/09/2026, preservando o corte **11/09/2026 17:13:16.749793 UTC** (14:13:16 em São Paulo).

## Banco e resultado inicial

PostgreSQL da VPS, banco `dados_globo`, schema `orcamento`. Tabela **`gold_projeto_status`** publicada. Migração aditiva: nenhuma tabela técnica, evento, snapshot ou watermark removido/avançado pela publicação manual.

| Verificação | Resultado observado |
|---|---:|
| Projetos técnicos | 4.569 |
| Passagens técnicas | 5.355 |
| Projetos incluídos na Gold | 4.441 |
| Passagens publicadas | 5.222 |
| Projetos excluídos integralmente | 128 |
| Retornos no histórico elegível | 39 |
| Passagens elegíveis à comparação observada/encerrada | 349 |

Motivos de exclusão: ambas as colunas 16; Squad 107; não individual identificado 4; múltiplos talentos 4. Há sobreposição: a soma dos motivos não representa projetos distintos.

Talento nos projetos incluídos: 2.708 com cadastro exclusivo; 1.603 com texto de Interveniência pendente de revisão de identidade; 130 ausentes. Os 1.603 permanecem nas análises de projeto/status, mas sem atribuição a uma pessoa no ranking. Essa pendência não significa que todos os textos sejam inválidos; significa que a classificação individual ainda não foi confirmada. Grafias de Marca foram normalizadas, não automaticamente fundidas por similaridade.

Responsáveis de Orçamento: 3.778 projetos com nome/ID identificado; 55 com texto original disponível, mas sem correspondência individual segura entre todos os nomes/IDs; 608 sem responsável informado. Não inventamos pessoa para preencher ausência.

Versão de regras inicial: `2.0.0:09dc31b7b1a1f630`.

## Proteção e reconciliação

- Backup anterior à mudança: `runtime/backups/before_gold_20260911T193243Z.dump`, 6.119.565 bytes, fora do Git.
- Restauração concluída em PostgreSQL 17 isolado localmente, conferindo 4.569 projetos, 5.355 intervalos e 789 eventos brutos.
- Hashes dos itens, status, eventos Silver, intervalos, fatos diários e resumos reconstruídos iguais aos existentes antes da publicação.
- Publicação de Gold, catálogo, snapshot de regras e apontamentos de qualidade sob lock por quadro e transação PostgreSQL.
- Verificação após publicação confirmou que todas as tabelas técnicas anteriores, exceto o acréscimo dos apontamentos de qualidade, ficaram iguais, incluindo Bronze e watermark.
- Segunda preparação/publicação produziu hashes iguais em todas as 19 tabelas: reexecução sem duplicação ou alteração de conteúdo.
- Chaves únicas e FKs fazem parte do modelo; testes PostgreSQL rejeitam inserção duplicada e verificam exclusão/reinclusão após correção.

Evidências detalhadas locais: `runtime/gold_backup_verified.json` e `runtime/gold_publication_report.json`. Não contêm credenciais; dumps e dados de revisão não são enviados ao GitHub.

## Testes e limites de aceite

**86 testes passaram**, incluindo integração PostgreSQL local. Cobrem retornos, ordem nativa com empate, fim aberto, nulos, exclusão integral sem perda técnica, reinclusão, catálogo revisado, responsáveis e bloqueio de chaves duplicadas. Ruff passou. Imagem Docker construída; `validate-gold` executado nessa imagem contra a VPS retornou `gold_validation_success`, 5.222 linhas. `quality-profile` conferiu as 19 tabelas com zero falhas críticas de contrato. Isso não elimina as pendências semânticas de identidade e histórico descritas acima.

PBIX/HTML não foram editados. As medidas DAX são arquivos para importar; não foram executadas em um motor Power BI nesta validação.

Publicação no banco foi observada. Publicação no GitHub e versão efetiva do executor devem ser conferidas separadamente ao final deste trabalho. O agendamento das 06h não é execução observada. D+1 fechado, BigQuery real e HTML Content/PBIX não foram implantados nesta mudança. Pendências de segurança, backup recorrente e alertas continuam conforme o aceite provisório.
