# Consumo direto — projetos por status e pendências

Aplicação 3.1.0; regras de negócio 2.2.1; contrato físico de consumo/recibo 4. A pedido do usuário, o PostgreSQL contém **duas tabelas de negócio**. Nenhuma tabela técnica foi reintroduzida.

| Tabela | Uma linha representa | Para que usar |
|---|---|---|
| `orcamento.gold_projeto_status` | Uma passagem/registro de status de um projeto | Tempos comprovados, trajetória, Marca, Talento, responsável e retornos |
| `orcamento.pendencias_projeto` | Um projeto com um ou mais motivos pendentes | Identificar o que revisar, com valor original, ID e orientação |

## Ver o fluxo como no exemplo

No DBeaver: abra Editor SQL na conexão `dados_globo`, execute [006_analise_projeto.sql](../sql/006_analise_projeto.sql), uma consulta por vez. A consulta pronta usa um projeto real; substitua o `item_id` para consultar outro.

As primeiras dez colunas físicas da Gold são, nesta ordem: `ordem_etapa`, `projeto_nome`, `status_nome`, `entrada_status_local`, `saida_status_local`, `duracao_horas`, `marca_nome`, `talento_nome`, `responsavel_orcamento`, `eh_retorno`. Depois ficam os IDs e campos necessários aos indicadores e à qualidade. JSONs de pessoas, cadastros intermediários e estimativas não ficam na tabela pública.

**Sempre ordenar por `item_id, ordem_etapa`.** A numeração começa em 1 para cada projeto e acompanha os eventos no tempo; empates preservam a sequência reconstruída dos eventos. Ordem dos status no quadro não é ordem de passagem. Um status pode reaparecer: isso é retorno, não linha duplicada. SQL não garante ordenação sem `ORDER BY`, mesmo quando a carga insere em ordem.

O primeiro registro é o primeiro trecho disponível; o último é a última etapa disponível no corte. O processo de negócio começa em Entrada, mas um histórico incompleto não autoriza inventá-la. Pode existir um trecho Sem status anterior ao primeiro evento de Entrada. Filtrar esse trecho para apresentação não altera a evidência guardada.

## Datas e tempos desconhecidos

- `qualidade_historico=observed`: início comprovado por evento; entrada e duração ficam preenchidas. Última passagem mede até o corte e tem saída nula.
- `initial_inferred`: o rótulo anterior foi recuperado, mas sua data de início não foi comprovada. Entrada e duração ficam **NULL**; uma saída conhecida pode aparecer.
- `no_history_inferred`: só há um status de referência, sem transições comprovadas. Entrada e duração ficam **NULL**. Isso não prova que o projeto começou naquele status.

O material de 200 linhas enviado pelo usuário continha somente `no_history_inferred`. Os valores aproximados de 187 horas da versão anterior eram inferências desde a criação do item; **não eram tempos comprovados de permanência**. A versão 3.1 não os publica como duração. A evidência original continua no checkpoint privado, para auditoria/reprocessamento.

`intervalo_aberto=true` significa que não foi observada saída da última etapa até o corte. Se `status_final=true`, o projeto pode estar encerrado: não rotular toda saída nula como projeto em andamento. Não preencher desconhecidos com zero.

As horas são corridas, incluindo noites e fins de semana. Para comparar desempenho, usar `elegivel_comparacao=true` e `horas_observadas_encerradas`: somente trechos observados, encerrados e sem inconsistência impeditiva. Uma etapa aberta não é uma observação concluída.

## Pendências: o que corrigir

Consultar `pendencias_projeto`, ordenando `excluido_da_analise DESC, projeto_nome`.

- `excluido_da_analise=true`: o projeto inteiro saiu da Gold pelas regras de identidade (múltiplos talentos, duas colunas preenchidas, Squad, coletivo, identidade pendente ou quarentena manual).
- `false`: o projeto continua na Gold, mas há informação incompleta. Exemplo: história inicial desconhecida ou nome do responsável indisponível. Duração não comprovada fica vazia e não entra nos rankings de tempo.

`motivos` explica os problemas e `como_corrigir` orienta a ação. `codigos` permite filtros estáveis. Valores originais ficam disponíveis para localizar a divergência. A mesma linha reúne vários motivos: contar projetos, não somar motivos como se fossem projetos diferentes.

Corrigir **no Monday**. Após a próxima carga, o código reavalia o cadastro: motivos resolvidos desaparecem; se não sobrar nenhum motivo, o projeto sai da tabela de pendências. Se resolver todas as regras de exclusão, volta à Gold com os mesmos IDs. Grafias ambíguas podem requerer aprovação no catálogo via `import-review` e `replay`; nunca deduplicar pessoas só por semelhança.

Histórico ausente não pode ser fabricado alterando o status atual no Monday. Verificar histórico/exportação anterior disponível. Novos eventos serão capturados a partir da operação. Uma próxima carga não garante recuperar eventos antigos que a fonte não oferece.

Não editar pendências diretamente no PostgreSQL: a tabela é recalculada e pertence ao pipeline. A edição manual não corrige a origem e provoca divergência do recibo/checkpoint.

## Responsáveis e IDs

Orçamento vem da coluna people chamada Orçamento (atualmente `person`). Referências a pessoas excluídas, como `Deleted on invitation cancelation`, não são nomes de responsáveis: o consumo apresenta NULL e registra a pendência. IDs originais continuam no estado privado. Mais de um responsável fica agregado, sem multiplicar passagens; a lista é cadastral na coleta, não prova de responsabilidade histórica.

`item_id` é o ID original do projeto no Monday. Use-o para localizar o mesmo item em outras extrações da mesma origem, incluindo `board_id` quando aplicável. `interval_id` identifica a passagem e não deve ser confundido com o projeto. `item_sk`, `board_sk` e `status_sk` são chaves substitutas estáveis. Não relacionar duas origens diferentes apenas por nome ou coincidência de número.

## Atualização e integridade

Uma tentativa diária às **06:00 America/Sao_Paulo**, sem extração ao subir/reiniciar. Corte D+1 à meia-noite: a execução de 12/09 fecha os tempos até o fim de 11/09. Ver `corte_local`. Cadastro é o observado em `cadastro_referencia_utc` e pode ter mudado depois do corte.

Gold e pendências são substituídas **na mesma transação**, com checkpoint durável e recibo da publicação. PK de passagem, UNIQUE projeto/ordem, índice único de última passagem e CHECKs de evidência/tempos protegem a Gold. PK quadro/projeto impede duplicar pendências. Falha reverte ambas. Locks e reserva diária persistente evitam duas cargas automáticas na mesma data.

O PostgreSQL é o destino de consumo. Bronze, histórico técnico, catálogo e watermark continuam privados no volume runtime do executor. Não apagar o volume. Backup de recuperação exige PostgreSQL + checkpoint correspondente.

## Onde incluir novas regras

1. Exclusão do projeto por talento: `rules/eligibility.py`.
2. Identidade/alias revisado: `rules/identities.py` e catálogo importado.
3. Nome e origem dos responsáveis: `rules/people.py`.
4. Eventos, ordem e permanência: `services/transform.py`, `services/gold.py`, `rules/cutoff.py`.
5. Campos públicos, mascaramento de estimativas e motivos de pendência: `models/consumption.py`.
6. Transação, chaves físicas e migração: `db/consumer.py`; estado privado: `db/checkpoint.py`.

Declarar origem, grão, tipo, chave, nulabilidade, regra, efeito nos KPIs e comportamento em falha. Criar teste de caso válido, inválido e correção/reinclusão; atualizar a versão semântica e documentação; executar testes locais e ensaio de migração/restauração antes de publicar. Nunca executar testes com dados fictícios na VPS.
