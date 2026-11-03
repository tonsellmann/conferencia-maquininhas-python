"""As taxas contratadas com cada maquininha (o MDR), por modalidade e faixa de parcelas.

No painel, a loja cadastra a tabela; aqui ela chega como um dicionário simples:

    {"Cartix": {"debito": "1.37", "credito": "2.99", "parcelado 2-6": "3.49", "parcelado 7-12": "3.99"}}
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Faixa:
    modalidade: str
    de: int
    ate: int
    percentual: Decimal


Tabela = dict[str, list[Faixa]]

NOME_DA_MODALIDADE = {"debito": "débito", "credito": "crédito à vista", "parcelado": "crédito parcelado"}


def ler_tabela(dados: dict[str, dict[str, object]]) -> Tabela:
    tabela: Tabela = {}
    for maquininha, faixas in dados.items():
        lista = []
        for chave, valor in faixas.items():
            partes = chave.strip().lower().split()
            modalidade = partes[0]
            if modalidade not in NOME_DA_MODALIDADE:
                raise ValueError(f"Modalidade desconhecida na tabela de {maquininha}: {chave!r}")
            de, ate = (1, 1)
            if modalidade == "parcelado":
                de, ate = (int(n) for n in partes[1].split("-")) if len(partes) > 1 else (2, 12)
            lista.append(Faixa(modalidade, de, ate, Decimal(str(valor).replace(",", "."))))
        tabela[maquininha] = lista
    return tabela


def percentual_contratado(tabela: Tabela, maquininha: str, modalidade: str, parcelas: int) -> Decimal | None:
    for faixa in tabela.get(maquininha, []):
        if faixa.modalidade == modalidade and (modalidade != "parcelado" or faixa.de <= parcelas <= faixa.ate):
            return faixa.percentual
    return None


def nome_da_faixa(modalidade: str, parcelas: int) -> str:
    if modalidade == "parcelado":
        return f"crédito em {parcelas}x"
    return NOME_DA_MODALIDADE.get(modalidade, modalidade)
