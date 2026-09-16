# Novos status

Rótulos são descobertos no quadro Monday. Criar um novo rótulo não exige criar coluna ou tabela no BigQuery.

1. Confirme se a nova etapa é intermediária ou terminal com o responsável do processo.
2. Se terminal, acrescente o rótulo exato a FINAL_STATUS_LABELS em deploy/gcp.env.yaml; publique nova imagem/configuração pelo workflow.
3. Não alterar INITIAL_STATUS_LABEL=Entrada sem decisão de negócio e testes.
4. Execute replay se a regra precisar ser reaplicada à evidência já guardada; confirme IDs, corte e medidas.
5. Confira qualidade e próxima execução diária.

Não inferir que “Negócio Fechado” ou qualquer outro nome é terminal só pela grafia. Duração desconhecida continua NULL.
