# Revisão de nomes e projetos fora da análise

Na versão 3.0, PostgreSQL contém apenas `orcamento.gold_projeto_status`. **Não existe tabela de quarentena ou catálogo no banco de consumo.** Esses dados ficam no checkpoint privado do executor e podem ser exportados sem entrar nos KPIs.

## Consultar pendências

No executor que possui o volume runtime:

```bash
sla-pipeline export-review
```

Arquivos gerados em `/app/runtime/review/`:

- `projetos_quarentena.csv`: uma linha por projeto, ID/nome, valores originais, motivos, corte e versão.
- `catalogo_identidades.json`: candidatos e revisões de Marca/Talento, chave original, identidade canônica e revisor.

São artefatos privados de negócio; não comitar no Git. Exportar novamente depois de uma carga/replay para atualizar a lista. Os motivos podem se sobrepor; contar projetos distintos.

## O que corrigir

1. Múltiplos talentos, Squad ou ambas as colunas preenchidas: corrigir o cadastro no Monday. O projeto inteiro fica fora da Gold enquanto persistir qualquer motivo.
2. Interveniência desconhecida: conferir se é pessoa individual. Não aprovar empresa/evento/coletivo como pessoa para fazer entrar no ranking.
3. Grafias equivalentes comprovadas: atribuir o mesmo ID/nome/tipo canônicos. Similaridade textual sozinha não é prova.
4. Nome suspeito confirmado: revisão `quarantined`, com `reviewed_by` e `review_reason`. O projeto inteiro sai após replay/próxima carga.
5. Ausência de Marca/Talento isoladamente permanece nula, sem exclusão automática.

## Aplicar revisão pelo código

Copiar do JSON exportado **somente as linhas revisadas** para um arquivo JSON (lista). Preservar `board_id`, `entity_type`, `source_key` e `source_text`. Para aprovar: preencher `canonical_id` estável, `canonical_name`, `entity_kind` (`person`, `organization`, `collective`), `reviewed_by`, `updated_at` ISO com fuso e `review_status=approved`. Para suspender: `review_status=quarantined`, revisor e motivo obrigatórios. Não usar `pending` no arquivo de importação.

```bash
sla-pipeline import-review --review-file /app/runtime/review/revisados.json
sla-pipeline replay
sla-pipeline validate-gold
sla-pipeline export-review
```

O importador valida contrato e conflitos antes de guardar as revisões. Descoberta automática não sobrescreve revisão humana. A importação não altera a Gold sozinha; replay ou próxima carga aplica o catálogo. Replay não busca correções novas do Monday: elas entram na próxima coleta diária. Versão/hash das regras e motivos permitem auditar a mudança.

Para trabalhar no VS Code local, usar uma cópia de checkpoint + PostgreSQL **de teste**, com agendador desativado, para revisar/testar regras. Aplicar os arquivos revisados no executor principal por canal privado. DBeaver/Power BI continuam consultando diretamente a única Gold, sem precisar conhecer o arquivo interno.
