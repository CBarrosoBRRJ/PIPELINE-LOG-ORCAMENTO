# Mapeamento Monday

Origem configurada: quadro 18429499488, coluna de status status_19. O código descobre os IDs das colunas de negócio pelos títulos/tipos; não presume que IDs de outro quadro serão iguais.

`sla-pipeline discover` inspeciona o quadro. A execução grava o mapeamento completo em relatório privado GCS. Não colar esse relatório público se contiver nomes de negócio.

`BUSINESS_COLUMNS_OVERRIDE` permite correspondências explícitas para títulos ambíguos. `STATUS_COLUMN_LABELS_OVERRIDE` permite rótulos conhecidos quando necessário; ambos são JSON de configuração, nunca mudanças silenciosas de identidade.

Campos de consumo: Projeto = nome do item; Marca e Talento = cadastro normalizado/revisado; Responsável = coluna people de Orçamento; Status/entradas/saídas = transições comprovadas. Campos cadastrais têm referência de coleta e não comprovam autoria histórica.

A descoberta, ausência/ambiguidade de colunas e envelopes de eventos são testados em `tests/test_extract.py`. Regras de exclusão e identidade estão no [PRD](../PRD.md).
