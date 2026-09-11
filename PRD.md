# PRD — histórico por status pronto para consumo

Aplicação **3.1.0**, regras **2.2.1**, contrato físico **4**. O usuário aprovou a tabela principal e, depois, uma única exceção: a tabela de erros/dúvidas. Resultado: **somente `orcamento.gold_projeto_status` e `orcamento.pendencias_projeto` no PostgreSQL `dados_globo`**. Não recriar dimensões, Bronze, fatos auxiliares ou controles nesse banco.

Uma linha da principal representa uma passagem do projeto por um status. Os primeiros campos são Ordem, Projeto, Status, Entrada, Saída, Duração, Marca, Talento, Responsável Orçamento e Retorno. `item_id` original e chaves de integração são preservados. A numeração `ordem_etapa` segue a sequência temporal por projeto; consumir com `ORDER BY item_id, ordem_etapa`.

## Regras essenciais

- O processo começa em Entrada, mas a primeira evidência disponível pode ser posterior. Não inventar eventos, datas nem tempos.
- **Entrada/duração inferidas ficam NULL no consumo.** Estimativas antigas ficam somente no checkpoint privado. Qualidade acompanha cada registro e a pendência explica a lacuna.
- Saída nula identifica a última passagem até o corte. Um status terminal sem saída não significa projeto ainda em andamento.
- Retorno é a segunda ou posterior passagem pelo mesmo status; não é duplicidade.
- Excluir o projeto inteiro por múltiplos talentos, Squad, Talento e Interveniência preenchidos, coletivo/não pessoa, Interveniência sem identidade revisada ou quarentena manual de Marca/Talento. Ausência isolada de Marca/Talento não exclui.
- Aliases dependem de revisão. Não unir pessoas/marcas automaticamente por similaridade de texto.
- Orçamento vem da coluna people de mesmo nome, atualmente `person`. Não usar mensagens de usuário excluído como nome. Atributos são do cadastro na coleta, não prova de autoria histórica.
- Tempo é corrido. Rankings usam passagens observadas, encerradas e consistentes (`elegivel_comparacao`). Ainda não há metas de SLA: estamos estudando tempos.
- Terminais atuais: Encerrado, Declinado pelo Mercado, Declinado Internamente. Novos rótulos são descobertos; terminal depende de configuração.

## Publicação e atualização

Python extrai, normaliza, reconstrói eventos, aplica regras e publica as duas tabelas na mesma transação. Estado e evidência internos ficam no arquivo SQLite do volume `/app/runtime`, não em outras tabelas PostgreSQL. Chaves/constraints, validação de sequência e referências, hash da publicação e checkpoint durável protegem a carga.

Uma tentativa automática diária às **06:00 America/Sao_Paulo**; deploy/reinício não extrai. Reserva persistente por data impede duplicar a tentativa. **D+1**, cortando à meia-noite do dia de execução: 12/09 às 06h fecha até o fim de 11/09. Eventos exatamente no corte entram no próximo fechamento. VPS/API indisponível impede execução; a agenda não garante disponibilidade externa.

`pendencias_projeto` reúne uma linha por projeto, com IDs, valores originais, motivos, orientação e `excluido_da_analise`. Correções no Monday são reavaliadas na próxima carga; a pendência resolvida desaparece e o projeto elegível volta à Gold. Históricos antigos ausentes não são recuperados por simples alteração do status atual. Catálogo revisado pode ser reaplicado com replay.

## Documentação e manutenção

- [Guia direto, sequência e regras de correção](docs/CONSUMO_DIRETO.md).
- [Dicionário de todos os campos públicos](docs/OURO_CONSUMO.md).
- [Power BI passo a passo](docs/POWER_BI_PRD.md).
- [ELT e pontos de extensão](docs/PRD_ELT_REGRAS.md).
- [Operação, migração e recuperação](OPERATIONS.md).
- [Evidências de validação](docs/VALIDACAO_OURO.md).

VPS provisória; BigQuery corporativo não implantado. IDs/SKs e contrato preservados ajudam na migração, que exigirá credenciais, adaptação de publicação e reconciliação próprias. Nenhum serviço pago novo foi contratado.
