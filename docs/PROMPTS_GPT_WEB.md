# Prompts para aprender e implantar com o GPT Web

Copie primeiro o **prompt inicial**. Depois envie um prompt de etapa por vez, na mesma conversa. Não envie todas as etapas de uma vez: a ideia é aprender, executar e validar antes de avançar.

Se o GPT Web não conseguir ler o repositório privado, anexe somente os arquivos de código/documentação indicados. Nunca anexe .env, dumps, SQLite, arquivos de credenciais, tfstate, tfvars ou dados brutos. Não presuma que ele viu os arquivos só porque você enviou um link.

## Prompt inicial — contexto e método

```text
Quero que você seja meu tutor de Google Cloud e me ajude a colocar um pipeline Python no ar, seguindo boas práticas e me ensinando. Sou iniciante: não presuma que conheço terminal, Docker, IAM ou Terraform.

Repositório: https://github.com/CBarrosoBRRJ/PIPELINE-LOG-ORCAMENTO
Projeto GCP confirmado: gglobo-viu-dados-hdg-prd
Dataset existente: viu_agenciamento, localização US
Única tabela de saída: sla_orcamento
Job proposto: pipeline-orcamento, us-central1
Agenda proposta: diariamente às 06h, America/Sao_Paulo

O código extrai Monday, faz todos os joins/tratamentos em Python e publica uma linha por passagem do projeto em um status. Horas úteis: seg-sex 10–13h e 14–19h, feriados BR PUBLIC e extras configuráveis. Não existe meta de SLA. Início não comprovado permanece NULL.

O BigQuery recebe uma única tabela por carga atômica, não tabelas por dia. Cloud Storage guarda histórico, checkpoint, pendências, calendário, journal e trava. A tabela mantém passagens históricas, não snapshots diários. Precisamos preservar o histórico da instalação anterior. PostgreSQL/SQLite só são origem de migração de leitura; não há escritor PostgreSQL nesta versão.

O deploy automático antigo da VPS foi informado como desligado. Isso não autoriza apagar VPS, banco, backups ou checkpoint. Projeto/dataset existem, mas bucket, service accounts, segredo, Job e Scheduler ainda não estão comprovados como criados. Não confunda infraestrutura declarada em arquivos com implantação real.

Leia README.md, docs/APRENDER_GCP.md, docs/DEPLOY_GCP.md, docs/MIGRACAO_HISTORICO.md, OPERATIONS.md, infra/main.tf, deploy/deploy.sh, deploy/schedule.sh e os workflows. Se não conseguir acessar o repositório privado, diga exatamente quais arquivos preciso anexar. Não invente o conteúdo deles.

Método obrigatório:
1. Trabalhe em uma etapa por vez e espere minha confirmação/evidência antes de avançar.
2. Explique objetivo, conceito em linguagem simples, por que precisamos dele, ação e resultado esperado.
3. Indique onde cada comando roda: Cloud Shell, terminal local ou GitHub. Diferencie comandos Bash de PowerShell. Explique placeholders antes de executar.
4. Dê poucos comandos por rodada; explique flags importantes e como conferir sucesso. Se houver erro, diagnostique antes de repetir ou aumentar permissões.
5. Consulte documentação oficial atual do Google/GitHub e cite a fonte de instruções que dependem de versão. Não prometa custo zero.
6. Nunca peça tokens, senhas, chave JSON, .env ou conteúdo de dados privados no chat. Use Secret Manager e identidades sem chave.
7. Prefira menor privilégio. Não resolver problemas concedendo Owner/Editor amplo, tornando bucket público ou desativando políticas corporativas.
8. Antes de criar/alterar recursos, confirme projeto, nomes, região, ambiente, permissões e impacto/custo. Não excluir dados nem recriar recurso existente sem revisão explícita e backup.
9. Infraestrutura está descrita em Terraform: inspecione o que existe, configure state protegido e revise plan antes de apply. Evite criar por clique e depois tentar recriar pelo Terraform.
10. Mantenha uma ficha de progresso: confirmado, pendente, recursos, comandos executados e como pausar/recuperar. Não marque concluído sem evidência.

Comece SOMENTE pelo inventário de acesso e pela diferença entre projeto GCP, dataset, bucket, service account, Cloud Run Job e Scheduler. Faça as poucas perguntas necessárias para saber o que já existe. Ainda não mande criar recursos nem executar o pipeline.
```

## Etapa 1 — inventário e permissões

```text
Vamos fazer somente o inventário. Ensine a conferir no Console o projeto correto, faturamento, dataset US, buckets, service accounts, Artifact Registry, Jobs e Scheduler existentes. Comece por verificações de leitura, sem criar nem alterar recursos. Explique a diferença entre minha conta pessoal e identidade do programa. Se faltar permissão, escreva um pedido específico para o administrador, sem pedir acesso Owner por conveniência. Ao final monte uma ficha do que existe e do que falta, usando somente nomes/e-mails não secretos, e pare.
```

## Etapa 2 — desenho, organização e custos

```text
Com o inventário confirmado, explique a arquitetura deste pipeline com linguagem simples. Compare bucket compartilhado versus bucket por aplicação/ambiente e proponha uma decisão justificada para este caso. Não confunda prefixo/pasta com isolamento IAM. Explique por que o checkpoint precisa sobreviver ao Job, por que não criar bucket/tabela por dia e por que runtime, scheduler e deploy usam identidades distintas. Valide a compatibilidade de região com o dataset US e políticas corporativas. Mostre categorias de custo, retenção e orçamento/alertas; ressalte que orçamento somente de alertas não é bloqueio automático de gasto. Não crie recursos ainda; entregue o desenho e decisões para eu aprovar.
```

## Etapa 3 — Terraform e infraestrutura

```text
Ensine a preparar a infraestrutura definida em infra/main.tf. Explique Cloud Shell, clone privado sem expor token, Terraform init/validate/plan/apply e state. Antes de apply, defina com o administrador backend protegido e recuperação do state; existe infra/backend.tf.example como modelo, não como recurso já criado. Peça bucket_name e IDs numéricos do repositório/owner pelo método seguro. Inspecione recursos já existentes e trate importação em vez de recriação. Faça comigo somente init, validate e plan primeiro. Explique cada criação/grant planejado e pare para revisão. Não execute destroy, não altere o dataset existente como se fosse novo e não crie versão de segredo em Terraform.
```

## Etapa 4 — identidade e segredo

```text
Depois de eu confirmar o apply e seus outputs, ensine a conferir as três service accounts e seus papéis por recurso. A runtime precisa BigQuery Job User no projeto, Data Editor no dataset, Object Admin no bucket, storage.buckets.get no bucket e Secret Accessor apenas no segredo. Explique o papel personalizado de metadados e por que Object Admin sozinho não basta para a carga. Ensine a inserir o token Monday diretamente no Secret Manager e a anotar apenas o número da versão. Não peça o token e não gere chave JSON de service account. Pare após validarmos as identidades e a versão habilitada do segredo.
```

## Etapa 5 — GitHub e primeira publicação

```text
Ensine a configurar o ambiente production e as variables GCS_BUCKET, GCP_WORKLOAD_IDENTITY_PROVIDER, GCP_DEPLOY_SERVICE_ACCOUNT e MONDAY_SECRET_VERSION. Explique Workload Identity Federation, branch main e a diferença entre CI (testes) e deploy. Leia o workflow real e as restrições do provider. Ajude a configurar proteção/revisão de main e production conforme disponibilidade da conta e regras corporativas. Execute comigo o workflow manual e interprete cada etapa: teste, build, autenticação, push da imagem, configuração do Job. Confira imagem/commit, runtime service account, envs não secretos, segredo por versão, uma tarefa, retries zero e timeout. Não executar carga nem ligar Scheduler ainda.
```

## Etapa 6 — preservar e migrar o histórico

```text
Vamos seguir docs/MIGRACAO_HISTORICO.md. Primeiro confirme se existe histórico anterior, quem tem a cópia consistente do PostgreSQL/SQLite, backup testado e geração confirmada do recibo. Não me peça para anexar esses dados no chat. Explique export-bq com o extra migration versus import-state offline, incluindo a diferença de reconciliação possível em cada caminho. Confirme o destino e bloqueie sobreposição com dados existentes. Não substitua histórico antigo por backfill da API. Oriente a importação na máquina autorizada, preserve IDs e guarde evidências de reconciliação sem dados sensíveis. Não apagar a origem depois dessa etapa.
```

## Etapa 7 — validar uma execução manual

```text
Com a migração confirmada, ensine a executar validate-gold, daily e health no Cloud Run Job conforme docs/DEPLOY_GCP.md. Explique substituição de argumentos e como acompanhar a execução até terminar. Confira somente sla_orcamento como tabela criada pelo pipeline, chaves únicas, retorno de status, início desconhecido NULL, horas úteis com almoço/feriados e corte D+1. Use consultas de sql/bq/002_validar_consumo.sql. Não criar dados fictícios na produção; cenários artificiais devem usar ambiente isolado. Explique por que repetir daily no mesmo dia pode retornar skipped e não apague a reserva para contornar isso. Pare quando tivermos evidências de sucesso ou um diagnóstico claro da falha.
```

## Etapa 8 — agenda, alertas e custos

```text
Somente após eu confirmar a validação manual, ensine a configurar o Scheduler diário às 06h America/Sao_Paulo com a conta scheduler e OAuth, seguindo deploy/schedule.sh. Verifique se a agenda já existe antes de tentar criá-la. Mostre como pausar a agenda, ver a execução do Job e distinguir disparo aceito de processamento concluído. Oriente alertas de falha e ausência de atualização, com responsável/canal e teste real do recebimento. Ensine a acompanhar custos e a observar a primeira execução agendada. Não declare concluído só porque salvamos a configuração.
```

## Etapa 9 — manutenção e próximos projetos

```text
Ensine a operar este projeto e transformar o aprendizado em padrão para outros. Cubra atualização de imagem por commit, rotação de segredo, mudança controlada de calendário, replay, pausa de agenda, lock abandonado, pending job, backup completo e teste de restore isolado. Use OPERATIONS.md: não liberar trava por idade nem restaurar ponteiro antigo sem reconciliar a tabela. Explique que rollback de imagem não desfaz automaticamente dados. Faça uma checklist reutilizável para novos pipelines: origem, contrato, identidades, bucket/prefixo, destino, região, segredos, CI/deploy, agenda, observabilidade, orçamento e responsáveis. Não copie os nomes/acessos deste ambiente de produção para o próximo projeto automaticamente.
```
