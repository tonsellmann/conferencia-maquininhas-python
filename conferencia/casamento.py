"""Casa cada venda do caixa com a transação da maquininha.

Não existe um número em comum entre o sistema do caixa e o extrato da maquininha. O que se tem é a
maquininha, o valor, a forma de pagamento e a hora, que nunca bate no segundo (o caixa registra
antes ou depois de passar o cartão). O par certo é o de mesma maquininha, mesmo valor e mesma
forma, com a menor diferença de horário dentro da tolerância. Duas vendas de R$ 12,00 no débito
com minutos de diferença são o caso difícil: os pares são escolhidos do mais próximo para o mais
distante, e cada venda e cada transação entram num par só.
"""

from __future__ import annotations

import pandas as pd

TOLERANCIA_EM_MINUTOS = 10


def casar(vendas: pd.DataFrame, transacoes: pd.DataFrame, tolerancia: int = TOLERANCIA_EM_MINUTOS) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Devolve (pares, vendas sem transação, transações sem venda)."""
    cartao = vendas[vendas["forma"].isin(["debito", "credito", "parcelado"])]
    candidatos = cartao.merge(
        transacoes,
        left_on=["maquininha", "valor", "forma"],
        right_on=["maquininha", "bruto", "modalidade"],
        suffixes=("_venda", "_transacao"),
    )
    candidatos["distancia"] = (candidatos["quando_transacao"] - candidatos["quando_venda"]).abs().dt.total_seconds() / 60
    candidatos = candidatos[candidatos["distancia"] <= tolerancia].sort_values(["distancia", "venda", "id"])

    usadas_vendas: set[int] = set()
    usadas_transacoes: set[str] = set()
    pares = []
    for linha in candidatos.itertuples(index=False):
        if linha.venda in usadas_vendas or linha.id in usadas_transacoes:
            continue
        usadas_vendas.add(linha.venda)
        usadas_transacoes.add(linha.id)
        pares.append({"venda": linha.venda, "transacao": linha.id, "minutos": round(float(linha.distancia), 1)})

    pares_df = pd.DataFrame(pares, columns=["venda", "transacao", "minutos"])
    sem_transacao = cartao[~cartao["venda"].isin(usadas_vendas)]
    sem_venda = transacoes[~transacoes["id"].isin(usadas_transacoes)]
    return pares_df, sem_transacao, sem_venda
