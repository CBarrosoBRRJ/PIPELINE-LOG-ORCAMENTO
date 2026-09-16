# Primeiro projeto no GCP — entender antes de executar

Este guia acompanha um pipeline que já está escrito. Você não precisa aprender todos os serviços do Google de uma vez. A meta é saber o que cada peça faz, quem pode acessá-la e como comprovar que funcionou.

O código pronto no GitHub não significa que os recursos existem no Google. Projeto e dataset foram confirmados; bucket, identidades, segredo, Job e agenda ainda precisam ser verificados/provisionados pela equipe autorizada.

Decisão atual: começar uma base nova no GCP, sem importar o banco/checkpoint anteriores. O responsável está aprendendo e será guiado em cada etapa. A agenda às 06h São Paulo está confirmada. Não apagar dados antigos; começar novo significa coletar o histórico que o Monday ainda disponibiliza, sem garantir recuperar eventos que já não estejam na fonte.

## 1. Vocabulário com exemplos deste projeto

| Nome | Explicação simples | Neste projeto |
|---|---|---|
| Projeto GCP | Agrupa recursos, permissões e cobrança; não é a pasta do código | gglobo-viu-dados-hdg-prd |
| Dataset BigQuery | Agrupa tabelas analíticas e tem localização/permissões | viu_agenciamento, em US |
| Tabela | Dados prontos para análise | sla_orcamento |
| Bucket Cloud Storage | Contêiner de arquivos/objetos; não é uma tabela nem um disco da VPS | Histórico, checkpoint, pendências e arquivos de carga |
| Imagem Docker | Pacote do programa e suas dependências | Construída a partir do Dockerfile |
| Artifact Registry | Guarda versões dessas imagens | Repositório viu-pipelines |
| Cloud Run Job | Executa o pacote, termina e registra o resultado | pipeline-orcamento, comando daily |
| Cloud Scheduler | Relógio que manda executar o Job | Diariamente às 06h São Paulo |
| Service account | Identidade técnica de um programa, sem login humano | Conta própria do executor |
| IAM/papel | Define quais ações uma identidade pode fazer e em qual recurso | Escrever neste dataset, acessar este bucket |
| Secret Manager | Guarda valores secretos fora do código | Token Monday |
| Terraform | Descreve recursos como código e apresenta um plano antes de criá-los | infra/main.tf |
| Workload Identity Federation | Permite que o GitHub receba acesso temporário sem uma chave permanente | Identidade de deploy limitada ao repositório/main |

Não vamos criar servidor web, domínio ou porta HTTP. Cloud Run **Job**, e não Cloud Run Service, é o executor escolhido para esta tarefa que começa e termina.

## 2. Preciso de um bucket para cada projeto?

Não é uma exigência técnica. Um projeto GCP pode ter vários buckets; um bucket pode ter arquivos de vários pipelines. Também é importante distinguir “projeto de código” de “projeto GCP”.

Minha recomendação para começar: **um bucket privado de dados/estado por aplicação e ambiente**, quando as permissões ou políticas forem próprias. Exemplo: este pipeline em produção tem seu bucket; um ambiente de testes usa outro destino isolado. Isso facilita entender quem acessa o quê e evita que uma política de retenção afete outros sistemas.

Pode fazer sentido compartilhar um bucket quando equipe, região, sensibilidade, retenção e permissões são iguais. Cada pipeline precisa de prefixo exclusivo. Porém `pasta-a/` e `pasta-b/` por si só **não são isolamento de segurança**: Object Admin no bucket alcança todos os objetos. Separação por permissões exige desenho IAM apropriado, não apenas trocar o prefixo.

Para este código, todas as execuções do mesmo pipeline devem usar o mesmo bucket/prefixo, pois ali ficam a trava e o histórico. Não criar um bucket por dia, por projeto Monday ou por execução. Não ativar expiração automática dos checkpoints.

O estado do Terraform também é sensível. Preferir o backend corporativo já existente, separado do estado do pipeline e sem acesso para a conta runtime. Um bucket central de Terraform com controles adequados pode servir vários projetos; não precisa criar um novo para cada repositório.

## 3. O que é service account? Já temos?

Pense nela como o “crachá do programa”. Seu usuário pessoal acessa o Console; a service account identifica o código quando ele pede para ler/escrever no Google. O e-mail terminado em iam.gserviceaccount.com não é uma caixa de e-mail para uso diário.

Ter um crachá não dá acesso a tudo. IAM concede papéis sobre recursos determinados. O Cloud Run fornece credenciais temporárias à identidade associada ao Job; você não precisa baixar chave JSON.

O repositório **define**, mas ainda não comprova a existência, de três identidades:

| Conta proposta | Pode fazer | Não deve fazer |
|---|---|---|
| pipeline-orcamento | Executar código, ler token, acessar estado e publicar BQ | Administrar o projeto inteiro |
| scheduler-sla-orcamento | Disparar o Job específico | Ler token ou dados da tabela |
| deploy-sla-orcamento | Publicar imagem e atualizar o Job | Usar uma chave permanente no GitHub |

A separação reduz a quantidade de acesso entregue a cada tarefa. A conta de deploy consegue executar código sob a identidade runtime, portanto o acesso ao GitHub/main e ao ambiente production também precisa de proteção e revisão.

Para conferir existência: selecione o projeto correto no Console, abra **IAM e administrador → Contas de serviço**, procure os nomes e anote apenas os e-mails. Se não conseguir listar/criar, peça apoio ao administrador. Não use Owner/Editor amplo para resolver qualquer erro.

## 4. Roteiro de implantação com pontos de parada

### Etapa 1 — inventário e autorização

Confirme o projeto selecionado, faturamento, dataset/localização US, acesso ao GitHub e quem pode criar recursos/IAM. Confira se já existem bucket ou contas com os nomes propostos. Anote o que existe e o que falta; não recrie recursos existentes.

Resultado esperado: inventário sem segredos e administrador responsável. Sem permissão? Pare e peça o acesso específico, não tente outro projeto por conta própria.

### Etapa 2 — desenho e custos

Leia a tabela de vocabulário; escolha com a equipe o bucket, us-central1 para Job/bucket e nomes. Valide regras corporativas de residência, rede e segurança; localização US do dataset não significa que qualquer região servirá. Este código propõe us-central1.

Estabeleça orçamento/alertas antes de agendar. Orçamentos somente de alertas **não desligam automaticamente** os recursos nem garantem limite de gasto. Custos envolvem execução, armazenamento, imagens, logs e consultas; não presumir gratuidade. Retenção e versionamento também acumulam armazenamento.

Resultado esperado: desenho aprovado e forma de acompanhar gastos.

### Etapa 3 — preparar infraestrutura

Abra Cloud Shell pelo Console: é um terminal administrado pelo Google, não a execução diária do pipeline. Clone o repositório privado pelo método corporativo; nunca coloque token no URL/comando. Leia DEPLOY_GCP.md e infra/main.tf antes de aplicar.

Terraform tem três passos importantes: init prepara ferramentas/backend; validate verifica a configuração; plan mostra ações previstas. Somente depois de revisar nomes, projeto, grants e ausência de remoções deve vir apply.

Combine onde ficará o state do Terraform **antes** do apply. Se houver backend corporativo, use-o; o exemplo infra/backend.tf.example precisa ser adaptado pela equipe. Não commitar tfstate/tfvars. Caso um recurso já exista, planeje importação para o Terraform em vez de apagá-lo.

Resultado esperado: APIs, bucket privado, Artifact Registry e identidades/permissões confirmados; guardar outputs não secretos.

### Etapa 4 — cadastrar o segredo

No Secret Manager, abra monday-api-token e crie a versão com o token. Nunca envie esse valor ao tutor ou GitHub. Anote somente o número da versão para a configuração do deploy. Defina quem pode ler/rotacionar.

Resultado esperado: versão habilitada, acessível somente às identidades necessárias.

### Etapa 5 — conectar GitHub e publicar o Job

Configure o ambiente production e as quatro variables descritas em DEPLOY_GCP.md. O provider de federação limita acesso ao repositório e main. Revise mudanças antes de publicá-las; branch protection/aprovação dependem das políticas e recursos disponíveis na conta GitHub.

Execute manualmente o workflow de deploy. Ele testa, constrói a imagem, envia ao Artifact Registry e configura o Job. Isso **não coleta dados nem cria agenda**. Confira a service account, uma tarefa, retries zero, comando daily e referência do segredo.

Resultado esperado: Job configurado com a imagem do commit escolhido, sem Scheduler ativo.

### Etapa 6 — primeira carga da base nova

Seguiremos a decisão de não importar a instalação anterior. Confira destino vazio e execute `init-db` e depois `backfill` no Job, um por vez, conforme DEPLOY_GCP.md. O primeiro prepara o controle no bucket; o segundo busca o histórico disponível no Monday, calcula os resultados e cria a tabela final. Não criar tabela manualmente nem executar `daily` antes disso. Uma substituição de argumentos na execução não muda o comando diário salvo no Job.

Resultado esperado: estado GCS reconciliado e uma tabela BQ, com IDs da fonte preservados. Eventos indisponíveis não são inventados: tempos sem início comprovado continuam NULL. Havendo estado/tabela já existentes ou falha na execução, pare e investigue, sem apagar para tentar de novo. MIGRACAO_HISTORICO.md é apenas uma alternativa se a decisão mudar antes da inicialização.

### Etapa 7 — executar manualmente e conferir

Execute validate-gold, daily e health no Job conforme guia. Leia resultado da execução, não apenas a mensagem de que ela começou. Compare amostra de passagens, NULL, horas úteis e corte D+1 com sql/bq/002_validar_consumo.sql. Use destino isolado para cenários fictícios/testes.

Resultado esperado: publicação íntegra e atual. Uma segunda tentativa daily no mesmo dia é ignorada por projeto; isso é proteção, não erro. Não apagar a reserva para repetir coleta sem diagnóstico.

### Etapa 8 — ligar agenda e observabilidade

Somente com a validação anterior aprovada, rode deploy/schedule.sh. Se a agenda já existe, inspecione-a e ajuste deliberadamente; o script de criação não deve ser repetido às cegas.

Observe a primeira execução às 06h São Paulo. Configure alerta de falha e de ausência de atualização, defina responsável/canal e teste o recebimento. Scheduler aceitar o disparo não prova que o Job concluiu.

Resultado esperado: execução diária comprovada, painel de custos e recuperação documentada.

### Etapa 9 — aprender manutenção e reaplicar o padrão

Pratique em ambiente isolado: publicar nova imagem, rotacionar segredo, pausar agenda, interpretar falha e restaurar backup. Uma troca de imagem não reverte automaticamente dados/calendário; rollback precisa considerar ambos. Não liberar lock sem confirmar que o escritor parou.

Para outro aplicativo, defina novamente origem, contrato, identidade, destino, permissões, calendário, região e retenção. Reutilize os conceitos, não copie os nomes e os acessos de produção indiscriminadamente.

## Referências oficiais

- [Buckets: organização e localização](https://docs.cloud.google.com/storage/docs/buckets).
- [Identidade usada pelo Cloud Run](https://docs.cloud.google.com/run/docs/securing/service-identity).
- [Boas práticas de service accounts](https://docs.cloud.google.com/iam/docs/best-practices-service-accounts).
- [Jobs agendados](https://docs.cloud.google.com/run/docs/execute/jobs-on-schedule).
- [Orçamentos e alertas](https://docs.cloud.google.com/billing/docs/how-to/budgets).
