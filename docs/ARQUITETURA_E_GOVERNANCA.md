> **Referência histórica anterior à arquitetura 3.0.** PostgreSQL agora contém somente `orcamento.gold_projeto_status`; tabelas auxiliares/relações SQL descritas abaixo foram retiradas. Não executar instruções antigas de criação/consulta dessas tabelas. Consulte o [PRD atual](../PRD.md) e a operação 3.0. Conceitos de identidade, nulabilidade e qualidade permanecem aplicáveis.

# Padrão de arquitetura, qualidade e manutenção da equipe

Versão 2.2.0 — 11/09/2026. Contrato executável: `models/contracts.py`, versão 2.2.0. Regras atuais e inventário: [PRD_ELT_REGRAS.md](PRD_ELT_REGRAS.md); saneamento: [QUARENTENA_E_IDENTIDADES.md](QUARENTENA_E_IDENTIDADES.md). Este padrão complementa o [PRD](../PRD.md), o [dicionário analítico](PRD_ANALITICO.md) e o [contrato de campos](CONTRATOS_DE_DADOS.md).

## Princípios adotados

Dados confiáveis são dados interpretáveis, com origem e limitações conhecidas. Não são dados sem nenhum NULL. Preservar evidência, separar ausência de erro, declarar o grão de cada tabela e impedir publicação inconsistente são requisitos permanentes.

O projeto atual é um pipeline analítico de permanência por status, em fase de estudo dos tempos reais, sem metas máximas por etapa. A organização permite evolução, mas ainda não é uma plataforma distribuída para N projetos. O MVP processa um quadro por configuração e reconstrói seus derivados em memória. Essa limitação precisa acompanhar qualquer plano de expansão.

## Contrato de passagem entre camadas

| Etapa | Responsabilidade | O que não fazer |
|---|---|---|
| Extração/Bronze | Capturar IDs, envelopes originais, timestamps e snapshots da fonte; manter JSON bruto | Sobrescrever o JSON para fazer a fonte parecer correta |
| Validação de entrada | Validar identidade, tipo, fuso, escopo do quadro e unicidade dos eventos antes da transformação | Ignorar registro crítico e continuar como se a carga estivesse completa |
| Tratamento para Prata/Ouro | Normalizar Unicode NFC, espaços nas bordas e sequências de espaços em campos textuais analíticos; converter texto vazio em NULL em atributos opcionais | Transformar nome/rótulo em chave; remover acentos dos nomes de apresentação; inventar preenchimentos |
| Prata | Representar transições tipadas e deduplicadas; preservar status anterior desconhecido como NULL | Criar uma transição para Entrada quando não existe evidência |
| Ouro | Calcular passagens, tempos, resumos e qualidade; validar unidades, datas e relações | Misturar estimativas com observações sem indicar qualidade |
| Publicação | Contrato portátil antes de gravar; transação com FK/PK/UNIQUE e NOT NULL no PostgreSQL; watermark no mesmo commit | Avançar o corte antes da publicação completa |
| Consumo | Usar cadastros/chaves e grão adequado, exibir cobertura e corte | Somar medidas após join que multiplica linhas |

O tratamento trabalha em cópias dos registros. `raw_data` e os envelopes Bronze persistidos não são alterados pelo replay. Nomes de apresentação mantêm acentos e caixa; normalização para comparação de status continua em `status_label_norm`. Códigos e IDs nunca recebem limpeza textual que possa mudar sua identidade. Valores como `N/A`, `0` e `-` não são convertidos automaticamente para NULL: dependem de regra semântica da fonte.

**Limite atual:** a extração faz parsing antes da publicação atômica. Se um evento não puder ser interpretado, o lote falha e não publica nem a nova Bronze nem os derivados. Não existe ainda landing durável independente ou tabela de quarentena. Logs informam erro sem expor o payload. Uma futura quarentena precisa preservar envelope original, origem, execução, código de rejeição e replay, sem fazer registros desaparecerem silenciosamente.

## Política de NULL

| Situação | Representação | Exemplo / ação |
|---|---|---|
| Coluna não disponível na fonte | NULL no atributo + catálogo/mapeamento da origem | `cliente` sem coluna mapeada; obter fonte antes de materializar valor |
| Coluna existe, mas não foi preenchida | NULL; contagem no perfil de qualidade | Marca ou Talento ausentes; corrigir no Monday quando aplicável |
| Dado não disponível por permissão | NULL ou identidade sem detalhes, conforme campo | E-mail da pessoa indisponível; não inventar |
| Evento histórico não existe na extração | NULL na informação não comprovada + diagnóstico | Entrada inicial ou finalização desconhecida |
| Informação ainda não aconteceu | NULL legítimo | Evento de saída da passagem ainda aberta |
| Chave, duração ou campo contratualmente obrigatório inválido | Falha bloqueante antes da publicação | `item_id` ausente, duração negativa/NaN, timestamp sem fuso |
| Status vazio | Membro explícito `Sem status` e diagnóstico | Mantém a FK de status e evidencia ausência na fonte |

Não usar zero para duração desconhecida nem datas artificiais para fechar lacunas. `finalizado_em=NULL` pode indicar projeto aberto ou finalização não comprovada; consultar status, qualidade e diagnósticos para distinguir. O perfil mostra a incidência do NULL, mas não atribui sozinho uma causa por linha.

Campos opcionais, PKs e tipos estão no contrato gerado. SKs identificam entidades e continuam consistentes com os IDs naturais. Colunas não nulas no banco não dispensam regras de domínio da aplicação.

## Regras que bloqueiam a publicação

- Tabela/campo não cadastrado, chave obrigatória ausente/vazia, PK duplicada no lote.
- ID Monday fora do domínio inteiro positivo, booleano onde é esperado ID, campo com tipo incompatível, timestamp sem timezone.
- Registro de outro quadro dentro do lote, SK incompatível com o ID de origem.
- Duração negativa, infinita ou NaN; divergência entre minutos, horas e diferença de timestamps.
- Visita marcada como observada sem evento de início; passagem aberta com evento final.
- Qualidade de Entrada incompatível com sua data, ou lead time preenchido sem Entrada comprovada.
- Referência órfã no PostgreSQL (FK), além das validações de sanidade já existentes.

Mensagens de contrato exibem versão, tabela, coluna e regra; nunca o valor rejeitado. A primeira violação interrompe a validação: não é um inventário exaustivo de todos os erros. Corrigir a causa e reexecutar. Não aumentar tolerâncias nem remover constraints para fazer uma carga passar sem análise.

O `init-db` aplica NOT NULL aos campos obrigatórios em migração transacional, apenas quando ainda estão nullable. Se houver linha antiga incompatível, a migração falha sem preenchimento automático. Execute perfil e backup antes. O DDL BigQuery de instalações novas acompanha obrigatoriedade; datasets existentes precisarão de migração própria. BQ ainda não foi homologado com credenciais reais.

## Perfil de qualidade e acompanhamento

```bash
sla-pipeline quality-profile
# ou, na imagem atualizada:
docker compose run --rm pipeline quality-profile
```

Gera `runtime/quality_<board_id>.json` (ou `/app/runtime` no volume Docker) com versão do contrato, instante, volume por tabela, tipo, obrigatoriedade, quantidade/percentual de NULL e textos vazios por campo. Retorna falha se alguma tabela não passar pelo contrato. Não inclui nomes de projetos, e-mails ou JSON de negócio. O comando não altera o banco.

Medição inicial em 11/09/2026, antes do tratamento: 769 eventos na Prata, dos quais 138 sem rótulo anterior; 5.329 intervalos, todos sem Cliente e 740 sem Marca; 4.415 resumos sem Entrada comprovada; três itens sem datas/observação por ausência de snapshot. As 16 tabelas passaram no contrato proposto. São medidas de um corte, não metas permanentes ou garantia de completude da fonte.

Perfil é distinto de sanidade de durações (`validate`), integridade do banco (constraints) e saúde de execução (`health`). Usar os quatro. Definir limites de cobertura por atributo com o dono do negócio antes de tratá-los como bloqueantes. Alertas automáticos externos e histórico persistente de perfis ainda não estão implantados.

## Organização para outras áreas e pipelines

Manter o schema atual `orcamento`. Em 11/09/2026 o usuário solicitou consolidar os nomes anteriores; houve reconciliação, backup com restore testado e atualização das consultas deste repositório. Consumidores externos precisam atualizar o schema. Não renomear tabelas, IDs ou SKs silenciosamente. Para domínios novos, adotar schema por domínio, por exemplo `comercial` e `financeiro`, com Bronze/Prata/Ouro identificadas por prefixos e catálogo comum. É um padrão para novos projetos, não schemas já provisionados.

Cada pipeline novo deve ter configuração, identidade, watermark, execução, contrato e responsável próprios. Compartilhar bibliotecas de armazenamento, logs e validação quando suas interfaces estiverem estáveis; não duplicar o projeto trocando nomes indiscriminadamente. O pacote atual ainda contém regras específicas do Monday/SLA e não deve ser anunciado como framework universal.

Para comunicação entre áreas:

1. Preservar `source_system`, conta/tenant quando aplicável e ID original na integração nova. `123` do Monday não é automaticamente `123` do CRM.
2. Reutilizar a identidade Monday existente quando a nova base realmente identifica o mesmo item; usar um mapeamento explícito para identidades de outras origens.
3. Compartilhar entidades de projeto, cliente e pessoa apenas com dono e semântica acordados. Não fazer deduplicação de pessoas/clientes somente por nome.
4. Declarar grão e cardinalidade. Agregar fatos antes de joins que multiplicariam medidas.
5. Preservar o algoritmo atual de UUIDv5; ele tem namespace fixo. Nova origem exige namespace próprio e mapa de correspondência. SCD2 exige chave de versão adicional.
6. Publicar views/contratos de consumo estáveis; evoluções incompatíveis exigem versão paralela e prazo de migração dos consumidores.

**Limite importante:** dimensões de item/status e suas chaves atuais foram desenhadas para a origem Monday. A PK de item usa o ID original global; a identidade do status incorpora quadro/coluna. Para múltiplas contas/fontes com IDs que possam colidir, será necessária evolução explícita do namespace/chave e da interface; não basta trocar o `.env`.

## Escala e operação

Antes de aumentar quadros/áreas, medir eventos, snapshots, memória máxima, tempo por fase, consultas e custo. O perfil atual lê uma tabela por vez, mas materializa suas linhas em memória; para grandes volumes, substituir por agregações no banco e validações por lote/partição. O rebuild atual dos derivados também precisa evoluir para itens/partições afetados, incluindo intervalos abertos.

PostgreSQL usa lock por quadro; repassagemr o escopo ao admitir múltiplas colunas/pipelines no mesmo quadro. BQ usa lock local, insuficiente para múltiplos hosts. Agendador distribuído, leases, landing durável, quarentena, retenção e alertas são etapas futuras com testes e documentação próprios.

Separar permissões de escrita do pipeline e leitura de consumidores; proteger segredos fora do Git; definir backup, restore e retenção. Banco remoto preenchido não significa executor/cron implantados na VPS. O fechamento D+1 dos tempos está implementado na Gold; o cadastro mantém sua data real de coleta. O disparo diário só é declarado observado após sua execução.

## Documentação obrigatória de todo projeto

Todo pipeline deve entregar, no mesmo PR da mudança:

| Artefato | Conteúdo mínimo |
|---|---|
| PRD | Objetivo, decisões, usuários, perguntas de negócio, escopo e limitações |
| Contrato executável versionado | Tipos, obrigatoriedade, grão, chaves, domínios, tratamento de nulos e ação em falha |
| Dicionário | Significado de tabelas/campos, unidades, fuso, origem e exemplos de uso |
| Catálogo/mapeamento | Campo de origem → campo analítico, transformações e versões |
| Arquitetura | Fluxo, componentes, dependências, identidade e interfaces de integração |
| Catálogo de KPIs | Fórmula, população, período, exclusões, qualidade, denominador e limite interpretativo |
| Operação | Execução, agendamento, segredos, monitoramento, recuperação, backup e restore |
| Evidências | Testes, reconciliação, migrações, corte e ambientes realmente homologados |
| Registro de decisões | Motivo, impacto, compatibilidade e estratégia de evolução |

Definir responsáveis de negócio e técnicos antes da operação regular; nomes ainda não foram acordados. Código versionado no GitHub, alterações revisáveis, DDL gerado a partir do metadata e contrato atualizado junto da mudança. Não declarar uma melhoria como implantada apenas porque existe no plano.
