# Continuar no VS Code e evoluir para múltiplas tabelas

Referência: 18/09/2026. Este arquivo documenta a transição de desenvolvimento;
não implementa a publicação de novas tabelas.

## Base para continuar

O código da versão implantada foi publicado no commit
`1b751425a47ab61248559a859a643ce6515c25c7`, originalmente na branch
`fix/horas-tres-decimais`. Ele inclui a configuração GCP, a correção do nome
do pacote para `sls_orcamento_ppd` e as horas publicadas com até três casas.

A base a utilizar daqui em diante é `main`, após a consolidação desse histórico.
O teste dessa versão no GitHub Actions passou: testes Python, lint, geração
de contratos/DDL e validação Terraform sem backend.
Evidência: https://github.com/CBarrosoBRRJ/PIPELINE-LOG-ORCAMENTO/actions/runs/35295621482

Segundo as saídas fornecidas pelo operador, o Job está implantado, o Scheduler
das 06h em America/Sao_Paulo foi criado e seu disparo manual concluiu a
publicação. A primeira execução pelo relógio e alertas ainda precisam de
acompanhamento. Acesso IAM e Scheduler são recursos do GCP: atualizar o Git
não importa suas credenciais, dados ou estado para o computador.

O workflow `ci.yml` roda testes em push/PR. O `deploy.yml` é de disparo manual
(`workflow_dispatch`); sua existência não significa que WIF/variáveis/ambiente
production estejam configurados. O deploy utilizado até aqui foi manual pelo
Cloud Shell. Não executar Terraform apply/destroy para sincronizar o código:
há provisionamento manual e estado parcial que exigem reconciliação própria.

## 1. Atualizar uma cópia existente no VS Code

Abra a pasta do repositório, depois Terminal > Novo terminal. Primeiro:

```powershell
git remote -v
git status -sb
```

Confira que origin aponta para este repositório. Se houver arquivos alterados,
preserve e revise seu trabalho antes de trocar branch. Não use reset --hard
nem sobrescreva alterações para fazer o pull funcionar.

Com a cópia limpa:

```powershell
git fetch origin
git switch main
git pull --ff-only origin main
git log -3 --oneline
git switch -c feature/publicacao-multitabelas
```

Se `main` não existir localmente, após fetch use
`git switch --track origin/main`. Se o pull acusar divergência, compare os
commits antes de escolher como integrar; não force a atualização.

Para uma cópia nova, escolha uma pasta de projetos e execute:

```powershell
git clone https://github.com/CBarrosoBRRJ/PIPELINE-LOG-ORCAMENTO.git
cd PIPELINE-LOG-ORCAMENTO
code .
git switch -c feature/publicacao-multitabelas
```

Se `code` não estiver no PATH, use Arquivo > Abrir pasta no VS Code.

## 2. Preparar Python e fazer a mudança

Use Python 3.11 ou superior. Se já existe ambiente virtual funcional, reutilize-o;
se foi copiado de outra máquina, recrie um ambiente novo em vez de copiar `.venv`.
Exemplo para uma instalação Python 3.11 disponível no Windows:

```powershell
py -3.11 -m venv .venv-dev
.\.venv-dev\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv-dev\Scripts\python.exe -m pytest -q
```

Selecione esse interpretador em Python: Select Interpreter. Mantenha ambientes
virtuais fora do Git; antes de qualquer commit confira os arquivos selecionados.
Não copie `.env`, tokens ou checkpoint do GCP para obter o código atualizado.

## 3. O que definir para publicar 2 ou 4 tabelas

O contrato atual publica uma tabela. A intenção de evoluir é legítima, mas ainda
faltam os nomes e conteúdos das novas saídas. Antes de implementar, preencha
para cada tabela: nome completo, propósito, origem, o que uma linha representa,
chave única, colunas/tipos, campos que podem ser NULL, forma de atualização,
histórico desejado, consumidores e validações.

Decida se `sla_orcamento` será preservada para manter DBeaver/BI compatíveis.
Não exponha todas as estruturas internas só porque agora existem mais destinos.
Dados desconhecidos continuam NULL e estado/credenciais permanecem privados.

Além de acrescentar schemas, será necessário revisar:

- `config.py` e `models/bq_consumption.py`: configuração, projeções e contratos.
- `db/bq.py`, `db/gcs.py` e checkpoint: publicação, journal e recuperação.
- Pipeline/CLI: modos de inicialização, replay, daily e validação de todas as saídas.
- DDL, documentação, AGENTS.md/PRD e testes: substituir conscientemente o
  contrato de tabela única quando o novo desenho estiver definido.

Hoje existe uma carga atômica por tabela, não uma transação distribuída entre
GCS e várias tabelas. Não basta repetir WRITE_TRUNCATE quatro vezes: a terceira
pode falhar depois de duas publicações. Defina consistência por geração/corte,
recuperação, promoção e comportamento dos consumidores antes de escolher
staging/transação/ponteiro de geração. Teste falhas em cada etapa.

## 4. Prompt para iniciar o trabalho na IDE

> Leia AGENTS.md, PRD.md, docs/ARQUITETURA_GCP.md, os contratos e OPERATIONS.md.
> Estou na branch feature/publicacao-multitabelas, derivada da main atualizada.
> Quero evoluir o pipeline para publicar as seguintes tabelas: [preencher nomes,
> finalidade, colunas e chave de cada uma]. Primeiro mapeie a implementação atual
> e proponha os contratos e o protocolo de publicação/recuperação entre tabelas.
> Preserve histórico, IDs, NULL, calendário, arredondamento e compatibilidade
> explicitamente necessária. Depois implemente, gere DDL/docs e teste sucesso,
> duplicidade, falha parcial e retomada em ambiente isolado. Não implante nem
> altere dados de produção durante o desenvolvimento.

## 5. Testar e enviar ao GitHub

No terminal do VS Code, após a implementação:

```powershell
.\.venv-dev\Scripts\python.exe scripts/generate_ddl.py
.\.venv-dev\Scripts\python.exe scripts/generate_contract_docs.py
.\.venv-dev\Scripts\python.exe -m pytest -q
.\.venv-dev\Scripts\python.exe -m ruff check src tests scripts/generate_ddl.py scripts/generate_contract_docs.py
git diff --check
git status -sb
git diff
```

No painel Controle do Código-Fonte, selecione apenas arquivos da mudança.
Crie commit, envie a branch e abra um Pull Request para main. Confira CI e
revisão antes do merge. Não envie dados da origem, ambientes virtuais ou secrets.

## 6. Atualizar o GCP depois do merge e da validação

Fluxo: VS Code -> GitHub/main -> Cloud Shell -> nova imagem no Artifact
Registry -> atualização do Job -> validação da publicação.

No Cloud Shell, confira a cópia limpa antes de mudar branch:

```bash
cd "$HOME/PIPELINE-LOG-ORCAMENTO"
git status -sb
git fetch origin
git switch main
git pull --ff-only origin main
git rev-parse HEAD
```

Se main não existir localmente, crie-a rastreando origin/main. Pare em qualquer
erro antes de continuar. `git pull` atualiza arquivos, não a imagem já implantada.

Siga o procedimento de build/push/deploy em docs/DEPLOY_GCP.md, levando em conta
que a implantação manual permanece o caminho usado e que o script/env também
precisarão refletir os novos destinos quando necessário. Para a mudança de modelo,
planeje backup coerente, migração/replay, janela sem execução concorrente e rollback
compatível com o estado. Não recrie Scheduler, não rode init-db/backfill indiscriminadamente
e não execute Terraform para publicar uma nova versão do aplicativo.

O Job pode continuar com o mesmo nome e agendamento se a nova versão mantiver
o modo daily. A decisão final depende do desenho das novas tabelas.
