# Implantação passo a passo — GitHub, EasyPanel e VPS

Atualizado em 11/09/2026. Este documento acompanha [OPERATIONS.md](../OPERATIONS.md). Banco existente: `dados_globo.rede_globo`; não é necessário criar outro banco ou recarregar tudo.

## O que cada acesso significa

| Recurso | Para que serve | Credencial |
|---|---|---|
| Hospedagem da VPS | Gerenciar a máquina, console, sistema e acesso SSH | Conta da empresa onde a VPS foi contratada |
| EasyPanel (tela enviada) | Gerenciar serviços Docker, como o PostgreSQL | Login próprio do painel |
| SSH | Abrir o terminal Linux do servidor a partir desta máquina | IP/host, usuário Linux, porta e senha ou chave SSH |
| PostgreSQL / DBeaver | Consultar e gravar dados | Host/porta do banco, banco, usuário e senha PostgreSQL |
| GitHub | Versionar e distribuir o código | Conta GitHub e autorização de Git/deploy key |

O e-mail e a senha do EasyPanel não são necessariamente o usuário e a senha SSH. A porta externa PostgreSQL 5433 não é a porta SSH. A URL do repositório terminada em `.git` é suficiente para identificar onde publicar o código; não fornece acesso à VPS.

## Localizar o acesso SSH com segurança

1. Entre no site da empresa onde contratou a VPS, abra a máquina e procure **Acesso SSH**, **Detalhes de acesso**, **Terminal** ou **Console**. Os nomes variam por hospedagem.
2. Localize IP, sistema operacional, usuário Linux e porta SSH. A porta costuma ser 22, mas deve ser conferida. O usuário pode ser `root`, `ubuntu` ou outro: não presumir.
3. Se não encontrar, informe ao assistente **qual é a hospedagem**, para orientar pelos menus corretos. Não envie senha, token ou chave privada.
4. Se o console da hospedagem já abre o terminal Linux, execute `whoami` para identificar o usuário e `cat /etc/os-release` para identificar o sistema. O terminal dentro do serviço PostgreSQL no EasyPanel é um container e não equivale ao terminal da VPS.
5. No PowerShell desta máquina, a forma do comando é `ssh -p PORTA USUARIO@IP_DA_VPS`, substituindo os três campos. Na primeira conexão, confira a impressão da chave do servidor por um canal confiável da hospedagem antes de aceitar. Digite uma eventual senha apenas no terminal; os caracteres podem não aparecer.
6. Acesso por chave permite automação sem digitar senha. A chave pública é cadastrada no servidor; a privada fica nesta máquina. Se ainda não houver chave, configuraremos depois de validar o acesso existente. Não é preciso enviar a chave privada ao assistente.

## Caminho escolhido para este pipeline

Código no repositório `https://github.com/CBarrosoBRRJ/PIPELINE-LOG-ORCAMENTO`, cópia versionada em `/opt/sls_orcamento_pdd` na VPS, imagem Docker construída lá e cron do Linux chamando um job diário. O PostgreSQL continua gerenciado pelo EasyPanel.

Essa rota aproveita o Dockerfile, o Compose e os scripts existentes. O job inicia, faz uma carga e termina. **Não usar política de reinício contínuo para transformar esse job em serviço permanente**, pois isso pode repetir cargas sem respeitar o horário desejado.

O EasyPanel também admite código por GitHub/Git ou upload e agendamento por seus mecanismos, mas é preciso ajustar o ciclo de vida do job e validar a versão instalada. Publicar como App comum ou clicar Deploy não instala automaticamente nosso cron. A documentação atual descreve as fontes e o comportamento de implantação: [App](https://easypanel.io/docs/services/app), [Compose](https://easypanel.io/docs/services/compose). Não ativar simultaneamente cron do Linux e outro agendador do painel para o mesmo board.

## O que vai para o GitHub

Código Python, testes, SQL, Dockerfile, Compose, scripts, documentação e `.env.example` com exemplos. `.env`, backups, dados brutos, logs, `runtime/`, ambientes Python e chaves ficam fora. O repositório criado foi identificado como público em 11/09/2026; não publicar dados de negócio ou segredos nele. A visibilidade privada pode ser adotada para restringir também o código/documentação.

Nenhum segredo é necessário para compilar a imagem. Na VPS, o `.env` é configurado separadamente, com permissão 600. Um push futuro atualiza o código no GitHub, mas o servidor só muda após o procedimento de atualização abaixo.

## Instalar na VPS após validar o acesso

Execute os passos no terminal da VPS, com usuário autorizado a usar Docker e gravar no diretório escolhido. Não execute novamente a instalação do EasyPanel.

```bash
docker version
docker compose version
timedatectl
git --version
```

Faça o clone apenas se o diretório de destino ainda não existir. Se existir, primeiro confira seu conteúdo e repositório; não sobrescreva arquivos locais.

```bash
git clone https://github.com/CBarrosoBRRJ/PIPELINE-LOG-ORCAMENTO.git /opt/sls_orcamento_pdd
cd /opt/sls_orcamento_pdd
```

Transfira o `.env` local por SFTP/SCP ou preencha o arquivo diretamente na VPS. Não coloque o conteúdo no chat/GitHub. Antes de executar, adapte os campos ao servidor:

```dotenv
COMPOSE_FILE=compose.remote.yaml
PG_DSN=
PG_HOST=banco_de_dados_postgres-pipeline
PG_PORT=5432
PG_DB=dados_globo
PG_SCHEMA=rede_globo
PIPELINE_DOCKER_NETWORK=NOME_REAL_DA_REDE
PIPELINE_NETWORK_EXTERNAL=true
DOCKER_HTTP_TRANSPORT=requests
```

Preserve token Monday, IDs do quadro/coluna, configuração de status e credenciais do banco. O hostname interno acima foi informado na tela do EasyPanel. Ele precisa ser resolvido pela rede do container do pipeline; não basta estar na mesma VPS.

### Descobrir a rede do PostgreSQL

Use comandos que exibem somente nomes e redes, sem despejar variáveis de ambiente:

```bash
docker ps --format '{{.ID}} {{.Names}}'
# Substitua ID_DO_CONTAINER pelo container PostgreSQL correspondente:
docker inspect --format '{{json .NetworkSettings.Networks}}' ID_DO_CONTAINER
# Substitua NOME_DA_REDE pelo nome observado:
docker network inspect --format '{{.Name}} driver={{.Driver}} attachable={{.Attachable}}' NOME_DA_REDE
```

Para o job Compose entrar numa rede overlay do Swarm, a rede precisa permitir anexar containers independentes (`attachable`). Se não permitir, pare nesta etapa e revise a integração de rede com o assistente; não recrie nem remova redes do EasyPanel. `NOME_REAL_DA_REDE` é um marcador, não um valor pronto.

### Validar antes do agendamento

```bash
chmod 600 .env
mkdir -p runtime logs
docker compose build pipeline
docker compose run --rm pipeline check-db
docker compose run --rm pipeline daily
docker compose run --rm pipeline validate
docker compose run --rm pipeline health
bash scripts/backup.sh
```

Execute cada comando e só avance se ele terminar com sucesso. `check-db` deve mostrar `dados_globo` e `rede_globo`. A primeira execução na VPS retoma o watermark existente; não apague dados e não crie outro banco. A carga local anterior já foi validada, mas conexão interna, permissões e runtime precisam funcionar no servidor.

### Agendar e operar

O horário proposto é 03h São Paulo. Se `timedatectl` confirmar servidor em UTC, use `CRON_SCHEDULE="0 6 * * *"`. Se o servidor estiver em America/Sao_Paulo, use `"0 3 * * *"`. Outros fusos exigem ajuste; `PREFERRED_TIMEZONE` não muda o cron.

```bash
bash scripts/setup_cron.sh
crontab -l
```

Confira o próximo disparo em `logs/daily.log`, `etl_run` e `health`. Não manter outro cron na máquina local para o mesmo quadro. A periodicidade diária **não implementa D+1 fechado**; os dados atuais continuam calculados até o início da execução.

Configure backup recorrente e retenção, cópia fora da VPS e acompanhamento de falhas/atrasos. O script de backup existe e teve restore validado, mas ainda não há agendamento de backup nem envio de alertas externos implantados por este projeto. `health` verifica atraso/falha; alguém ou um monitor precisa executá-lo e agir sobre a falha.

Ao configurar acessos definitivos, separar usuário de execução e usuário de leitura do BI, restringir a porta pública do banco e usar túnel/VPN ou TLS validado para consultas externas. O transporte externo testado anteriormente estava sem TLS. Configurar HTTPS para o painel antes de transmitir credenciais por ele em redes não confiáveis.

## Atualizar o código depois

Manter mudanças de código no GitHub; não editar o mesmo código paralelamente na VPS. Pausar apenas o agendamento deste pipeline durante a atualização e preservar as demais tarefas do servidor. Registrar o commit atual e fazer backup antes de uma alteração de modelo.

```bash
cd /opt/sls_orcamento_pdd
git status --short
git rev-parse HEAD
# Se houver alterações locais, resolver antes de continuar.
git pull --ff-only
docker compose build pipeline
docker compose run --rm pipeline init-db
docker compose run --rm pipeline daily
docker compose run --rm pipeline validate
docker compose run --rm pipeline health
```

Reativar o agendamento somente após sucesso. O `.env` e o banco não são substituídos por `git pull`. Para retornar a uma versão anterior, usar o commit registrado e avaliar compatibilidade de schema; não apagar volumes ou restaurar backup por cima de produção como atalho.

## Situação e pendências reais

Banco e carga remotos funcionam. O objetivo analítico atual é estudar tempos e encontrar padrões; não há meta de prazo definida por etapa e isso não impede o estudo. Consultas e dicionário estão no [PRD analítico](PRD_ANALITICO.md).

A instalação do executor na VPS aguarda identificação e validação do acesso SSH/console. Não há cron remoto confirmado. GitHub preparado/publicado deve ser registrado na conversa e verificado pelo commit remoto; isso não equivale a implantação automática.
