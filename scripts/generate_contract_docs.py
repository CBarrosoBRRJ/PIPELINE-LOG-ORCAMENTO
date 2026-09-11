"""Generate field-level contract reference from the executable source of truth."""

from pathlib import Path

from sls_orcamento_pdd.models.contracts import CONTRACT_VERSION, required_columns
from sls_orcamento_pdd.models.keys import DIMENSION_IDENTITIES
from sls_orcamento_pdd.models.schemas import DEFINITIONS, foreign_keys


def main():
    lines = [
        "# Contrato de campos — referência gerada",
        "",
        f"Versão {CONTRACT_VERSION}. Fonte: `models/schemas.py` e `models/contracts.py`.",
        "Regenerar com `python scripts/generate_contract_docs.py`.",
        "",
        "Significado de negócio das tabelas: [PRD_ANALITICO.md](PRD_ANALITICO.md).",
        "Política de nulos e tratamento: [ARQUITETURA_E_GOVERNANCA.md](ARQUITETURA_E_GOVERNANCA.md).",
        "",
        "`id`: inteiro positivo de 64 bits; `text`: texto; `time`: timestamp com fuso;",
        "`date`: data; `num`: número finito não negativo; `bool`: booleano; `json`: objeto/lista.",
        "`localtime`: data/hora local sem fuso, para apresentação; referência temporal continua em UTC.",
        "Campos opcionais aceitam NULL. Campos obrigatórios não aceitam NULL e textos obrigatórios não aceitam vazio.",
        "SKs são calculadas antes da gravação; devem corresponder ao ID original. A obrigatoriedade de SK dimensional é imposta pelo banco.",
    ]
    references = {
        (child, column): f"{parent}.{target}" for child, column, parent, target in foreign_keys()
    }
    for name, (pk, fields) in DEFINITIONS.items():
        lines.extend(
            [
                "",
                f"## `{name}`",
                "",
                f"Chave primária: `{pk}`.",
                "",
                "| Campo | Tipo | Obrigatório | Referência |",
                "|---|---|---|---|",
            ]
        )
        for field in fields.split():
            column, kind = field.split(":")
            required = (
                column in required_columns(name)
                or column == DIMENSION_IDENTITIES.get(name, (None, None))[1]
            )
            ref = references.get((name, column), "—")
            lines.append(f"| `{column}` | {kind} | {'Sim' if required else 'Não'} | {ref} |")
    target = Path(__file__).resolve().parents[1] / "docs" / "CONTRATOS_DE_DADOS.md"
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
