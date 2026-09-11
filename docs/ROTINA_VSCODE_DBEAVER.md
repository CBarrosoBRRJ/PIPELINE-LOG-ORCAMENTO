# Rotina de trabalho pelo VS Code e DBeaver

Preferência confirmada em 11/09/2026: desenvolver e analisar pelo VS Code/Python e pelo DBeaver, sem depender de abrir o terminal da VPS na rotina.

## Organização recomendada

| Onde | Responsabilidade |
|---|---|
| VS Code / Python nesta máquina | Desenvolver extrações, tratamentos, testes, consultas e documentação |
| DBeaver nesta máquina | Explorar tabelas, escrever SQL, conferir qualidade e indicadores |
| GitHub | Versionar código, regras e documentação; distribuir versões |
| PostgreSQL na VPS | Persistir dados e executar consultas SQL recebidas remotamente |
| Executor agendado na VPS | Rodar o pipeline com o computador pessoal desligado; implantação ainda pendente |

Não é necessário abrir o painel da VPS para consultar tabelas ou executar SQL autorizado. Acesso SSH pode ser usado pelo cliente para proteger a conexão, sem exigir comandos de administração a cada consulta. Configuração inicial, atualização do executor e incidentes de infraestrutura ainda exigem um responsável ou automação; não desaparecem por usar DBeaver.

Executar um script no VS Code usa o Python desta máquina, mesmo quando ele grava no banco remoto. Se depender dele para a carga diária, computador, internet e processo precisam estar disponíveis. Uma consulta SQL enviada pelo DBeaver é processada pelo PostgreSQL na VPS. O pipeline atual transforma em Python; não é um fluxo ELT exclusivamente executado em SQL no banco.

## Melhorar a base sem perder a evidência

1. Medir: executar `quality-profile`, consultar diagnósticos e identificar nulos/vazios por campo.
2. Explicar: diferenciar coluna inexistente, campo não preenchido, permissão, falta de histórico e valor inválido.
3. Tratar: corrigir a regra Python/SQL versionada ou a fonte apropriada; manter o JSON original na Bronze.
4. Validar em desenvolvimento: tipos, chaves, duração, amostra por projeto, soma antes/depois e qualidade.
5. Publicar: migrar de forma compatível, reprocessar quando necessário e conferir o resultado.

Não limpar a tabela de intervalos manualmente pelo grid do DBeaver: o próximo replay/daily reconstrói os derivados e pode desfazer essa edição. Correções de regras pertencem ao código e ao contrato; erros cadastrais devem ser corrigidos na fonte ou em um mapeamento de correção formal, com origem e justificativa. Esse mapeamento adicional ainda não existe.

NULL desconhecido não vira zero. O projeto já trata espaços/Unicode nos textos analíticos, preserva IDs, aplica contratos, deduplica por chaves e impõe integridade PostgreSQL. Próxima melhoria útil é uma camada de consumo com nomes de negócio e qualidade explícita para consultas recorrentes, conforme a necessidade dos relatórios. Não remover tabelas/colunas só porque não entram no primeiro relatório.

## Conexões e permissões

Manter uma conexão de leitura para análise e uma identidade de execução para as gravações do pipeline. Separar um ambiente de desenvolvimento/homologação da base consumida pelos relatórios. Esses papéis e o fluxo completo de promoção ainda precisam ser configurados; hoje a configuração fornecida usa uma conta administrativa.

O banco remoto já é acessível pelo DBeaver e pelo Python. A conexão externa anterior estava sem TLS. Para o acesso definitivo, configurar túnel SSH, VPN ou TLS validado; o DBeaver oferece configuração de túnel no próprio cliente. [Documentação DBeaver](https://dbeaver.com/docs/dbeaver/Network-configuration/).

Para Python, um túnel SSH pode expor uma porta somente em `127.0.0.1` desta máquina, apontando para o PostgreSQL remoto. Nesse caso, a configuração Python usa essa porta local. Host, porta e usuário SSH precisam ser confirmados antes de montar o comando. Um túnel aberto pelo DBeaver não deve ser presumido como compartilhado com Python. [Documentação PostgreSQL sobre túneis](https://www.postgresql.org/docs/current/ssh-tunnels.html).

Não mudar o `.env` do executor remoto para a porta local do túnel de desenvolvimento. Cada ambiente tem suas próprias credenciais/configuração fora do Git. `PG_SSLMODE=prefer` não garante TLS; um túnel SSH pode proteger o transporte mesmo que o diagnóstico PostgreSQL informe `tls=false`.

## Consultas Python no projeto atual

O ambiente `.venv` e o pacote já permitem acesso remoto. Exemplo somente leitura, para colocar em um script local e executar a partir da raiz do projeto:

```python
from sqlalchemy import text
from sls_orcamento_pdd.config import load_settings
from sls_orcamento_pdd.db.postgres import PostgresStore

settings = load_settings()
store = PostgresStore(settings)
item_id = 0  # Substitua pelo ID original do projeto, sem pontos.

with store.engine.connect() as connection:
    connection.execute(text("SET TRANSACTION READ ONLY"))
    rows = connection.execute(
        text(f"""
            SELECT status_to AS etapa, history_quality AS qualidade,
                   SUM(duration_hours) AS horas
            FROM {settings.pg_schema}.fct_item_status_interval
            WHERE board_id = :board_id AND item_id = :item_id
            GROUP BY status_to, history_quality
            ORDER BY horas DESC
        """),
        {"board_id": settings.monday_board_id, "item_id": item_id},
    ).mappings().all()
    for row in rows:
        print(dict(row))
```

O schema vem da configuração validada; filtros de negócio usam parâmetros. Este exemplo separa a qualidade, mas inclui visitas abertas até o corte. Não imprime URL de conexão, senha ou token. Um usuário PostgreSQL de leitura continua sendo a proteção permanente adequada.

No DBeaver, use [as consultas prontas](../sql/006_analise_projeto.sql) e [o guia de relacionamentos](RELACIONAMENTOS_E_KPIS.md).

## Passos para fechar a operação automática

Validar o acesso inicial da Hostinger, instalar o executor, conectar pela rede interna, configurar agendamento, backup e monitoramento. Depois, o uso cotidiano pode ficar concentrado no VS Code e DBeaver. Publicação automática a partir do GitHub ainda não está configurada; push sozinho não atualiza a VPS.

Detalhes: [implantação](DEPLOY_PASSO_A_PASSO.md), [governança](ARQUITETURA_E_GOVERNANCA.md) e [operação](../OPERATIONS.md). A preferência de interface não altera a regra de início em Entrada, os contratos ou o corte atual. Fechamento D+1 continua pendente.
