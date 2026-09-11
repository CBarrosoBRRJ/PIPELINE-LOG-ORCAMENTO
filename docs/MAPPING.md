# Mapeamento do quadro real

Quadro: **Backlog 2026 | Agenciamento**. Board ID: `18429499488`. Descoberto pela API em 10/09/2026, horário de São Paulo.

| Atributo | Coluna Monday | Tipo |
|---|---|---|
| status | `status_19` | status |
| Pessoa — Orçamento | `person` | people |
| Pessoa — Talent Manager | `pessoas9__1` | people |
| Pessoa — GP | `dup__of_dup__of_squad__1` | people |
| Pessoa — Audiência | `dup__of_conte_do__1` | people |
| Pessoa — Conteúdo | `dup__of_planejamento__1` | people |
| Pessoa — Produção | `multiple_person__1` | people |
| marca | `text_mkr0g3zy` | text |
| cliente | Não encontrada; NULL | — |
| talento | `dropdown_mkvdz0zv` | dropdown |
| intervenciencia | `text_mkvcwrrb` | text |

A chave `intervenciencia` mantém a grafia do contrato de dados solicitado; o título de origem é Interveniência. Talentos Exclusivos é dropdown; Talent Manager é uma coluna de pessoas, não o atributo Talento. Cliente não é inferido de Marca ou Contato.

## Status atuais

| Índice | Status | Ordem | Final no resumo |
|---|---|---|---|
| 7 | Entrada | 0 | Não |
| 0 | Em Elaboração - Orçamentos | 1 | Não |
| 11 | Em elaboração - Retorno Marca/Executivo | 2 | Não |
| 12 | Em elaboração - Validação Gestão Esporte | 3 | Não |
| 10 | Em elaboração (Produção) | 4 | Não |
| 13 | Em elaboração - Cotação Gestão de Elenco | 5 | Não |
| 14 | Em elaboração - Cotação Externa | 6 | Não |
| 17 | Em elaboração - Conteúdo | 7 | Não |
| 18 | Em elaboração - Audiência | 8 | Não |
| 3 | Em revisão | 9 | Não |
| 1 | Em revisão (Planejamento) | 10 | Não |
| 15 | Em revisão - Validação Talent Manager | 11 | Não |
| 16 | Em revisão - Validação Talento | 12 | Não |
| 4 | Aguardando Feedback | 13 | Não |
| 8 | Encerrado | 14 | Sim |
| 9 | Declinado Internamente | 15 | Sim |
| 6 | Standby | 16 | Não |
| 2 | Declinado pelo Mercado | 17 | Sim |
| 5 | Sem status | 18 | Não |
| 19 | Em elaboração GP | 19 | Não |

Novos rótulos são descobertos automaticamente a cada execução. Veja [NEW_STATUSES.md](NEW_STATUSES.md).

O JSON original de todas as colunas fica na Bronze, mesmo quando a coluna não é um atributo analítico mapeado. IDs não são fixados na lógica Python; este documento registra a descoberta atual.
