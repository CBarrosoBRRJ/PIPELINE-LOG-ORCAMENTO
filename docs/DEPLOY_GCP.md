# Implantação GCP e GitHub — 4.0.0

Destino confirmado: `gglobo-viu-dados-hdg-prd.viu_agenciamento.sla_orcamento`, localização BigQuery `US`.
Cloud Run Job e bucket propostos em `us-central1`. O dataset já existe; o código não cria datasets.
Tudo neste guia é procedimento de implantação; a existência dos arquivos no Git não significa que os recursos já foram implantados.

Decisão confirmada em 16/09/2026: **instalação nova, sem importar PostgreSQL/SQLite anteriores**. A primeira carga busca o histórico ainda disponível no Monday. Não é garantia de recuperar todo o passado e não autoriza excluir dados antigos. Agenda confirmada: 06h America/Sao_Paulo.

Se estiver começando, leia primeiro [Aprender GCP](APRENDER_GCP.md). Para acompanhamento com um tutor, use os [prompts por etapa](PROMPTS_GPT_WEB.md).

### Configuração local não é a configuração do Cloud Run

O `.env` local pode continuar com as configurações da VPS. Ele é privado, ignorado no Git e excluído da imagem; **não será enviado nem usado pelo Cloud Run**. No GCP, `deploy/gcp.env.yaml` fornece os valores não secretos, o deploy injeta o nome do bucket e o token vem do Secret Manager. Não existe chave/senha BigQuery a colocar no código.

Se quiser executar localmente, preserve o `.env` antigo, crie um arquivo privado `.env.gcp` a partir de `.env.example`, preencha o bucket após criá-lo, configure autenticação Google e use `sla-pipeline --env-file .env.gcp COMANDO`. Nunca execute coleta local e Job ao mesmo tempo. Não é necessário preparar esse arquivo para implantar pelo GitHub.

## O que solicitar à equipe GCP

Não existe senha do BigQuery. Acesso é por IAM e identidade Google.

| Informação/recurso | Valor/proposta | Para quê |
|---|---|---|
| Projeto | gglobo-viu-dados-hdg-prd | Jobs e faturamento |
| Dataset | viu_agenciamento | Destino já criado |
| Tabela | sla_orcamento | Única tabela publicada |
| Localização BQ | US | Jobs de carga/consulta |
| Bucket privado novo | nome único, por exemplo gglobo-viu-sla-orcamento-state | Histórico, estado, arquivos de publicação, pendências |
| Service account runtime | pipeline-orcamento@gglobo-viu-dados-hdg-prd.iam.gserviceaccount.com | Identidade do Job |
| Service account agendador | scheduler-sla-orcamento@gglobo-viu-dados-hdg-prd.iam.gserviceaccount.com | Apenas invocar Job |
| Service account deploy | deploy-sla-orcamento@gglobo-viu-dados-hdg-prd.iam.gserviceaccount.com | Publicação via GitHub |
| Segredo | monday-api-token, versão 1 | Token Monday; inserir no Secret Manager, nunca no Git/chat |
| GitHub | CBarrosoBRRJ/PIPELINE-LOG-ORCAMENTO | Repositório; confirmar IDs numéricos de repo/owner |

O runtime recebe BigQuery Job User no projeto, BigQuery Data Editor no dataset, Storage Object Admin somente no bucket e Secret Accessor somente no segredo. O deployer recebe Run Developer, acesso ao Artifact Registry e actAs somente na identidade runtime. O Scheduler recebe Run Invoker somente no Job. Usuários do BI recebem Data Viewer no destino e Job User no projeto de consulta. Permissões corporativas para criar recursos devem ser tratadas com o administrador; ver o BQ na interface não prova acesso a Run/IAM/Storage.

Para a carga GCS → BigQuery, o runtime também recebe um papel personalizado com apenas `storage.buckets.get`, vinculado somente ao bucket. Object Admin sozinho não concede essa leitura de metadados. A equipe que provisiona precisa poder criar o papel personalizado; não é necessário conceder Storage Admin ao runtime. [Permissões oficiais da carga JSON](https://docs.cloud.google.com/bigquery/docs/loading-data-cloud-storage-json).

## 1. Preparar o repositório e provisionar a base

Versione esta alteração numa branch e revise o diff. Não publicar `.env`, `runtime`, dumps, token ou checkpoint. A CI testa PRs/pushes; deploy é manual. O workflow antigo da VPS precisa ficar desligado antes da troca; não conectar a imagem v4 à antiga agenda EasyPanel.

No Cloud Shell, clone o repositório (autenticação GitHub pelo fluxo corporativo) e abra a pasta:

```bash
git clone https://github.com/CBarrosoBRRJ/PIPELINE-LOG-ORCAMENTO.git
cd PIPELINE-LOG-ORCAMENTO
gcloud config set project gglobo-viu-dados-hdg-prd
```

Peça à equipe que aplique `infra/main.tf`. Ele cria APIs, bucket protegido, Artifact Registry, três identidades, o contêiner de segredo e Workload Identity Federation. Não altera tabelas existentes nem cria o Cloud Run Job antes da imagem. Não cria versão contendo o token. Instalar Terraform >=1.6 se ele não estiver disponível no Cloud Shell.

Configure variáveis por prompt ou arquivo `infra/terraform.tfvars` (ignorado no Git): `bucket_name`, `github_repository_id` e `github_owner_id`. Obtenha os IDs no endpoint GitHub `GET /repos/CBarrosoBRRJ/PIPELINE-LOG-ORCAMENTO`, campos `id` e `owner.id`, com autenticação se privado. Esses IDs vinculam a federação ao repositório correto e à branch main.

```bash
terraform -chdir=infra init
terraform -chdir=infra validate
terraform -chdir=infra plan -out=platform.tfplan
terraform -chdir=infra apply platform.tfplan
terraform -chdir=infra output
```

O state do Terraform é privado e precisa de armazenamento controlado pela equipe; não colocá-lo no Git. Em equipe, configurar backend remoto corporativo. Recursos existentes com os mesmos nomes precisam de import Terraform, sem recriação destrutiva. O dataset não é gerenciado como recurso novo por este Terraform; somente um grant aditivo ao runtime.

## 2. Cadastrar o token Monday

No Console GCP: **Secret Manager → monday-api-token → Nova versão**. Cole o token ali. O Job usa uma versão explícita, inicialmente `1`. Ao rotacionar, altere `MONDAY_SECRET_VERSION` no GitHub e publique de novo. Cloud Run usa a própria service account para BQ/GCS; não gerar JSON de chave.

## 3. Publicar pelo GitHub (caminho recomendado)

O GitHub guarda o código, executa testes e constrói a imagem; o processamento diário continua na GCP.

Em **Settings → Environments**, crie `production`. Em **Settings → Secrets and variables → Actions → Variables**, cadastre:

- `GCS_BUCKET`: bucket criado.
- `GCP_WORKLOAD_IDENTITY_PROVIDER`: output Terraform completo.
- `GCP_DEPLOY_SERVICE_ACCOUNT`: output Terraform da conta deploy.
- `MONDAY_SECRET_VERSION`: `1` ou versão aprovada.

Depois de a alteração chegar à branch main, abra **Actions → Deploy Cloud Run Job → Run workflow**. O workflow testa, constrói, autentica por federação de curta duração, envia imagem com tag do commit e executa `deploy/deploy.sh`. Não copia token Monday para o GitHub e não inicia carga.

Configuração inicial: uma tarefa, paralelismo 1, retries 0, CPU 1, memória 2 GiB, timeout 1h, comando `sla-pipeline daily`. É um ponto de partida: acompanhar memória/duração do histórico real e ajustar. A imagem termina ao concluir. Não há comando loop nem servidor HTTP.

Alternativa manual (Cloud Shell, após provisionar base):

```bash
export GCS_BUCKET=NOME_DO_BUCKET
export IMAGE=us-central1-docker.pkg.dev/gglobo-viu-dados-hdg-prd/viu-pipelines/pipeline-orcamento:VERSAO
gcloud builds submit --tag "$IMAGE" .
bash deploy/deploy.sh
```

Cloud Build manual precisa de uma identidade de build com acesso ao repositório Artifact Registry e logs conforme política corporativa; o workflow GitHub já usa a identidade deploy provisionada e dispensa Cloud Build. Deploy não cria agendamento automaticamente.

## 4. Inicializar a instalação nova (caminho escolhido)

Somente depois de provisionar os recursos, cadastrar o segredo e publicar o Job, confira o destino: `gglobo-viu-dados-hdg-prd.viu_agenciamento.sla_orcamento` e o bucket/prefixo configurados. Não crie a tabela manualmente: a primeira publicação cria o schema explícito. Se já houver tabela ou estado nesse destino, pare e investigue; não apague nem sobrescreva para "começar do zero".

No **Cloud Shell (Bash)**, execute **um comando por vez** e confira o sucesso antes do próximo:

```bash
gcloud run jobs execute pipeline-orcamento --project gglobo-viu-dados-hdg-prd --region us-central1 --args init-db --wait
gcloud run jobs execute pipeline-orcamento --project gglobo-viu-dados-hdg-prd --region us-central1 --args backfill --wait
```

`init-db` prepara o controle vazio no GCS, não uma tabela vazia no BQ. `backfill` consulta cadastro e histórico disponível no Monday, processa as regras em Python, grava a memória técnica no GCS e publica a tabela. Essas substituições de argumentos valem só para a execução: o Job continua configurado com `daily`. Executar com substituições requer permissões além de apenas Run Invoker; conferir o papel do operador conforme a [documentação oficial](https://docs.cloud.google.com/run/docs/execute/jobs).

Não execute o `daily` nem ative Scheduler antes de concluir a primeira carga. Se houver falha, examine execução/logs e siga OPERATIONS.md; não remova travas, reservas ou estado às cegas. A API pode não oferecer eventos antigos: início e duração sem evidência permanecem NULL. Uma base nova não significa descartar os eventos históricos que o Monday ainda oferece.

Após o backfill, siga a etapa 5. O aceite depende de dados reais: acesso ao quadro/coluna, permissões, tempo/memória da carga e reconciliação da tabela. Não declarar produção pronta só porque o build passou.

### Alternativa: importar instalação anterior (fora do roteiro escolhido)

Use esta alternativa somente se houver uma decisão posterior explícita de aproveitar o histórico antigo, **antes de inicializar a base nova**. Não combine os dois caminhos sobre um destino já populado.

Mantenha o executor antigo desligado. Preserve PostgreSQL + checkpoint correspondente; gere backup e teste restore isolado conforme [MIGRACAO_HISTORICO.md](MIGRACAO_HISTORICO.md). O PostgreSQL sozinho não contém Bronze. Não use backfill como substituto do checkpoint: a API pode não ter mais o histórico antigo.

Opção A: numa máquina que alcance PostgreSQL e tenha o checkpoint certo, instale `python -m pip install -e '.[migration]'`, autentique com `gcloud auth application-default login` (ou impersonação corporativa). Preserve o `.env` antigo e crie `.env.gcp` a partir de `.env.example`, acrescentando os campos de `migration.env.example`. Configure `TARGET_DB=bigquery`, BQ/GCS, `RUNTIME_DIR` apontando para o checkpoint da origem e PG_* da origem. Nunca imprima nem envie seu conteúdo. Execute:

```bash
sla-pipeline --env-file .env.gcp export-bq
sla-pipeline --env-file .env.gcp validate
sla-pipeline --env-file .env.gcp validate-gold
```

`export-bq` só lê PostgreSQL sob lock. Compara Gold pública legada com checkpoint, importa todas as coleções privadas para GCS, calcula a nova projeção em horas úteis e confirma identidade/fingerprint do estado e hash da tabela real. Destino precisa estar sem estado de negócio. Não exclui as tabelas antigas e não recria 20 tabelas no BQ.

Opção B, sem acesso PostgreSQL durante importação: exporte um checkpoint SQLite com backup API e anote a `generation` do recibo PostgreSQL (`obj_description` da Gold) na mesma janela sem escritor. Leve ambos por canal privado para máquina autenticada e execute:

```bash
sla-pipeline --env-file .env.gcp import-state --checkpoint-file /CAMINHO/backup.sqlite3 --generation GERACAO_DO_RECIBO
sla-pipeline --env-file .env.gcp validate-gold
```

Não adivinhar a geração escolhendo o slot pending. O comando lê exatamente a geração informada e verifica checksum. Não incluir o checkpoint na imagem ou no Git.

Uma tabela BQ existente sem recibo GCS bloqueia para impedir sobrescrita inadvertida.

## 5. Executar e conferir no Cloud Run

No Console: **Cloud Run → Jobs → pipeline-orcamento → Execute com substituições**, argumento `validate-gold`; confira a execução até o fim. Pela CLI:

```bash
gcloud run jobs execute pipeline-orcamento --project gglobo-viu-dados-hdg-prd --region us-central1 --args validate --wait
gcloud run jobs execute pipeline-orcamento --project gglobo-viu-dados-hdg-prd --region us-central1 --args validate-gold --wait
gcloud run jobs execute pipeline-orcamento --project gglobo-viu-dados-hdg-prd --region us-central1 --args daily --wait
gcloud run jobs execute pipeline-orcamento --project gglobo-viu-dados-hdg-prd --region us-central1 --args health --wait
```

`daily` usa reserva por data local; uma segunda execução na mesma data será ignorada. O comando `replay` reaplica regras/calendário sobre histórico já guardado, sem Monday e sem avançar watermark. Se a importação tiver uma reserva da data corrente, o daily não repete coleta nesse dia. A primeira carga após migração pode estar atrasada em relação a hoje; nesse caso health acusa atraso até a próxima coleta válida.

Consulte `sql/bq/002_validar_consumo.sql` e confira: somente sla_orcamento criada pelo pipeline, uma chave por passagem, horas úteis <= corridas, início/duração desconhecidos NULL, último corte e exclusões corretas. O dataset pode ter tabelas de outros projetos; o pipeline não toca nelas.

## 6. Ligar a agenda diária

Após validar e com VPS pausada:

```bash
bash deploy/schedule.sh
```

Executa diariamente às 06h no fuso America/Sao_Paulo, inclusive sábados e domingos. Não mantém máquina ligada. Para pausar:

```bash
gcloud scheduler jobs pause pipeline-orcamento-diario --location us-central1
```

Execuções manuais também usam o mesmo lock e reserva. Não configurar outro cron/GitHub Schedule para coletar o mesmo pipeline.

## 7. Monitorar e recuperar

Cloud Run → Job → Executions mostra sucesso/falha e logs. No Logs Explorer filtre `resource.type="cloud_run_job"` e `resource.labels.job_name="pipeline-orcamento"`. O pipeline emite JSON com status, quantidades, corte e job ID sem payloads de negócio. Crie alerta para execução falha e um monitor diário de ausência de publicação; sucesso do Scheduler significa que o disparo foi aceito, não que a carga terminou. Canais de alerta dependem de e-mail/grupo corporativo e ainda precisam ser configurados/testados.

Veja [OPERATIONS.md](../OPERATIONS.md) para crash, lock abandonado, backup e restauração. Versões de objetos e checkpoint acumulam histórico intencionalmente; não aplicar TTL genérico ao bucket. Custos dependem de volume/armazenamento/consultas; a carga batch evita DML de reescrita e consultas SQL de reconstrução, mas não torna toda a operação gratuita.

## Referências oficiais

- [Cloud Run Jobs](https://docs.cloud.google.com/run/docs/create-jobs).
- [Scheduler para Jobs](https://docs.cloud.google.com/run/docs/execute/jobs-on-schedule).
- [Identidade sem chave](https://docs.cloud.google.com/run/docs/securing/service-identity).
- [Carga batch atômica](https://docs.cloud.google.com/bigquery/docs/batch-loading-data).
- [Precondições GCS](https://docs.cloud.google.com/storage/docs/request-preconditions).
- [GitHub authentication](https://github.com/google-github-actions/auth).
- [Calendário Brasil](https://holidays.readthedocs.io/en/latest/auto_gen_docs/brazil/).
