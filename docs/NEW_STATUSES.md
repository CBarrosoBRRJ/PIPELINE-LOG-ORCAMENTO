# Criar um status novo, como Negócio Fechado

1. No Monday, abra a coluna **Status (`status_19`)** do quadro e adicione o rótulo. Não exclua/recrie a coluna.
2. O próximo `daily` lê os rótulos atuais, cria o status na dimensão e captura suas transições. Não exige alteração de código ou novo backfill.
3. Se o status encerra o SLA total, acrescente o nome exato à lista no único `.env`:

```dotenv
FINAL_STATUS_LABELS='["Encerrado","Declinado pelo Mercado","Declinado Internamente","Negócio Fechado"]'
```

4. Execute `daily` para captar os eventos novos. Atualize o dataset do Power BI e confira `gold_status_metrics`.

Sem configurar a lista de finais, o status continua sendo medido normalmente e participa da fila de trabalho. A configuração de final encerra o lead time do resumo e exclui a etapa da fila; a permanência no próprio status continua registrada. `replay` aplica mudanças da classificação de final aos dados já carregados sem reler a API.

Um status novo, sem nenhum item, aparece em `dim_status`/`gold_status_metrics` com fila zero. Renomear o rótulo mantendo o índice conserva a chave técnica; o nome atual aparece na dimensão, e os textos originais dos eventos ficam em Bronze/Silver. Se renomear um final, atualize também `FINAL_STATUS_LABELS`, pois essa configuração usa nomes.

Não reutilize um status antigo com significado diferente: isso mistura conceitos sob a mesma chave. Prefira adicionar uma nova opção. `STATUS_COLUMN_LABELS_OVERRIDE` pode fixar um rótulo e, portanto, mascarar renomeações; deixe vazio salvo necessidade explícita.

O teste `test_new_status_automatically_discovered_and_measured` simula a inclusão de Negócio Fechado, uma transição para ele e o fechamento do resumo. Nenhuma alteração de quadro é realizada por esse teste ou pelo pipeline.

## Marco inicial obrigatório

O marco inicial do SLA é **Entrada** (`INITIAL_STATUS_LABEL=Entrada`). O cálculo usa a primeira transição disponível para Entrada; retornar a essa etapa não reinicia o total. Ausência desse evento é informada como início não comprovado, e `lead_time_total_min` fica nulo. Criar Negócio Fechado não muda essa regra. Configure no Monday o processo/automação de criação de itens para iniciar em Entrada; o pipeline é somente leitura e não altera o status dos projetos.
