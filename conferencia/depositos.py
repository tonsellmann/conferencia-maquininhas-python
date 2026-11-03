"""Confere se o dinheiro de cada maquininha caiu no banco.

A maquininha não deposita venda por venda: deposita, num dia, a soma das parcelas previstas para
aquele dia. Então a conta é por maquininha e por dia: o que estava previsto (pelo extrato dela)
contra o que entrou na conta (pelo extrato do banco). O banco às vezes lança no dia útil seguinte,
e isso não é atraso.
"""

from __future__ import annotations

import unicodedata

import pandas as pd

FOLGA_EM_DIAS_UTEIS = 1


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn").upper()


def maquininha_do_lancamento(historico: str, maquininhas: list[str]) -> str | None:
    """'TED CRED PAGAJA PAGAMENTOS' → 'PagaJá'."""
    texto = _sem_acento(historico)
    for nome in maquininhas:
        if _sem_acento(nome) in texto:
            return nome
    return None


def conferir_depositos(recebiveis: pd.DataFrame, banco: pd.DataFrame, maquininhas: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Devolve (conferência por maquininha e dia, previsto para depois do extrato do banco)."""
    previsto = (
        recebiveis.assign(data=recebiveis["data_prevista"].dt.normalize())
        .groupby(["maquininha", "data"], as_index=False)["valor"].sum()
        .rename(columns={"valor": "previsto"})
    )
    if banco.empty:
        vazio = pd.DataFrame(columns=["maquininha", "data", "previsto", "recebido", "diferenca", "situacao"])
        return vazio, previsto.rename(columns={"previsto": "valor"}).sort_values(["data", "maquininha"]).reset_index(drop=True)

    corte = banco["data"].max()
    futuro = previsto[previsto["data"] > corte].rename(columns={"previsto": "valor"})
    previsto = previsto[previsto["data"] <= corte]

    creditos = banco[banco["valor"] > 0].copy()
    creditos["maquininha"] = creditos["historico"].map(lambda h: maquininha_do_lancamento(h, maquininhas))
    creditos = creditos.dropna(subset=["maquininha"])

    # Três passadas, da mais segura para a menos: um depósito que faltou não pode "roubar" o do
    # dia seguinte, senão o erro de um dia contamina a semana.
    previsto = previsto.sort_values(["data", "maquininha"]).reset_index(drop=True)
    recebido_de: dict[int, int] = {}
    usados: set[int] = set()

    def janela(item, de, ate):
        return creditos[
            (creditos["maquininha"] == item.maquininha) & (creditos["data"] >= de) & (creditos["data"] <= ate) & ~creditos.index.isin(usados)
        ]

    def limite_de(item):
        return item.data + pd.offsets.BDay(FOLGA_EM_DIAS_UTEIS)

    # 1. O valor exato, no dia ou no dia útil seguinte.
    for i, item in previsto.iterrows():
        exatos = janela(item, item.data, limite_de(item))
        exatos = exatos[(exatos["valor"] - item.previsto).abs() <= 1]
        if not exatos.empty:
            escolhido = exatos["data"].idxmin()
            usados.add(escolhido)
            recebido_de[i] = int(creditos.loc[escolhido, "valor"])
    # 2. Valor diferente no mesmo dia; 3. valor diferente no dia útil seguinte.
    for mesmo_dia in (True, False):
        for i, item in previsto.iterrows():
            if i in recebido_de:
                continue
            candidatos = janela(item, item.data, item.data if mesmo_dia else limite_de(item))
            if not candidatos.empty:
                escolhido = (candidatos["valor"] - item.previsto).abs().idxmin()
                usados.add(escolhido)
                recebido_de[i] = int(creditos.loc[escolhido, "valor"])

    linhas = []
    for i, item in previsto.iterrows():
        limite = limite_de(item)
        recebido = recebido_de.get(i, 0)
        diferenca = recebido - int(item.previsto)
        if recebido == 0 and limite > corte:
            # O banco ainda pode lançar no dia útil seguinte, que o extrato não cobre.
            situacao = "aguardando"
        elif recebido == 0:
            situacao = "não caiu"
        elif abs(diferenca) <= 1:
            situacao = "ok"
        elif diferenca < 0:
            situacao = "veio a menos"
        else:
            situacao = "veio a mais"
        linhas.append({"maquininha": item.maquininha, "data": item.data, "previsto": int(item.previsto), "recebido": recebido, "diferenca": diferenca, "situacao": situacao})

    conferencia = pd.DataFrame(linhas, columns=["maquininha", "data", "previsto", "recebido", "diferenca", "situacao"])
    return conferencia, futuro.sort_values(["data", "maquininha"]).reset_index(drop=True)
