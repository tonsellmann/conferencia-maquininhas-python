"""Cada maquininha manda o extrato num formato. Aqui cada um vira a mesma tabela.

As três maquininhas são fictícias, como a padaria, mas os formatos imitam o que se vê de verdade:
separador ponto e vírgula ou vírgula, acento em latin-1, valor com vírgula decimal, data com ou sem
hora, uma linha por venda ou uma linha por parcela.

Tabelas normalizadas:

transações: id, maquininha, quando, bandeira, modalidade (debito | credito | parcelado),
            parcelas, bruto, taxa, liquido (centavos), status (aprovada | estornada | contestada)
recebíveis: transacao_id, maquininha, parcela, data_prevista, valor (centavos líquidos)
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import pandas as pd

from .dinheiro import centavos

COLUNAS_TRANSACOES = ["id", "maquininha", "quando", "bandeira", "modalidade", "parcelas", "bruto", "taxa", "liquido", "status"]
COLUNAS_RECEBIVEIS = ["transacao_id", "maquininha", "parcela", "data_prevista", "valor"]


class FormatoDesconhecido(ValueError):
    pass


def texto_do_arquivo(conteudo: bytes) -> str:
    """UTF-8 (com ou sem BOM) ou, se não for, latin-1: o padrão de muito sistema brasileiro."""
    try:
        return conteudo.decode("utf-8-sig")
    except UnicodeDecodeError:
        return conteudo.decode("latin-1")


def _tabela(texto: str, separador: str) -> pd.DataFrame:
    tabela = pd.read_csv(io.StringIO(texto), sep=separador, dtype=str, keep_default_na=False)
    tabela.columns = [c.strip() for c in tabela.columns]
    return tabela


def _modalidade(texto: str, parcelas: int) -> str:
    t = texto.strip().lower()
    if "déb" in t or "deb" in t:
        return "debito"
    return "parcelado" if parcelas > 1 else "credito"


def _cartix(texto: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cartix: ';', latin-1, 'dd/mm/aaaa hh:mm', '1.234,56'; uma linha por venda, com a previsão
    de pagamento da primeira parcela. As outras caem de 30 em 30 dias."""
    t = _tabela(texto, ";")
    parcelas = t["Parcelas"].replace("", "1").astype(int)
    transacoes = pd.DataFrame({
        "id": "CX-" + t["NSU"].str.strip(),
        "maquininha": "Cartix",
        "quando": pd.to_datetime(t["Data da venda"], format="%d/%m/%Y %H:%M"),
        "bandeira": t["Bandeira"].str.strip().str.title(),
        "modalidade": [_modalidade(p, n) for p, n in zip(t["Produto"], parcelas)],
        "parcelas": parcelas,
        "bruto": t["Valor bruto"].map(centavos),
        "taxa": t["Taxa (R$)"].map(centavos),
        "liquido": t["Valor líquido"].map(centavos),
        "status": t["Situação"].str.strip().str.lower().map({"aprovada": "aprovada", "cancelada": "estornada", "em disputa": "contestada"}).fillna("aprovada"),
    })
    primeira = pd.to_datetime(t["Previsão de pagamento"], format="%d/%m/%Y")
    linhas = []
    for (_, venda), data in zip(transacoes.iterrows(), primeira):
        valores = _dividir(int(venda["liquido"]), int(venda["parcelas"]))
        for n, valor in enumerate(valores, start=1):
            linhas.append((venda["id"], "Cartix", n, (data + pd.DateOffset(days=30 * (n - 1))).normalize(), valor))
    return transacoes, pd.DataFrame(linhas, columns=COLUNAS_RECEBIVEIS)


def _pagaja(texto: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """PagaJá: ',', UTF-8, data ISO, '1234.56', nomes em inglês (sistema de fora); uma linha por venda."""
    t = _tabela(texto, ",")
    parcelas = t["installments"].replace("", "1").astype(int)
    transacoes = pd.DataFrame({
        "id": "PJ-" + t["transaction_id"].str.strip(),
        "maquininha": "PagaJá",
        "quando": pd.to_datetime(t["created_at"], format="ISO8601").dt.tz_localize(None),
        "bandeira": t["card_brand"].str.strip().str.title(),
        "modalidade": [_modalidade(p, n) for p, n in zip(t["payment_method"], parcelas)],
        "parcelas": parcelas,
        "bruto": t["gross_amount"].map(centavos),
        "taxa": t["fee_amount"].map(centavos),
        "liquido": t["net_amount"].map(centavos),
        "status": t["status"].str.strip().map({"approved": "aprovada", "refunded": "estornada", "chargeback": "contestada"}).fillna("aprovada"),
    })
    primeira = pd.to_datetime(t["settlement_date"], format="%Y-%m-%d")
    linhas = []
    for (_, venda), data in zip(transacoes.iterrows(), primeira):
        for n, valor in enumerate(_dividir(int(venda["liquido"]), int(venda["parcelas"])), start=1):
            linhas.append((venda["id"], "PagaJá", n, (data + pd.DateOffset(days=30 * (n - 1))).normalize(), valor))
    return transacoes, pd.DataFrame(linhas, columns=COLUNAS_RECEBIVEIS)


def _vendemais(texto: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Vendemais: ';', UTF-8 com BOM, data e hora em colunas separadas, uma linha POR PARCELA.
    A venda é a soma das suas parcelas."""
    t = _tabela(texto, ";")
    t["parcela"] = t["Parcela"].astype(int)
    t["total"] = t["Total de parcelas"].astype(int)
    for coluna, nova in [("Valor da parcela", "bruto"), ("Desconto", "taxa"), ("Líquido da parcela", "liquido")]:
        t[nova] = t[coluna].map(centavos)
    t["quando"] = pd.to_datetime(t["Data"] + " " + t["Hora"], format="%d/%m/%Y %H:%M:%S")
    t["id"] = "VM-" + t["ID da transação"].str.strip()
    vendas = t.groupby("id", sort=False).agg(
        quando=("quando", "first"),
        bandeira=("Cartão", "first"),
        tipo=("Tipo", "first"),
        parcelas=("total", "first"),
        bruto=("bruto", "sum"),
        taxa=("taxa", "sum"),
        liquido=("liquido", "sum"),
        status=("Status", "first"),
    ).reset_index()
    transacoes = pd.DataFrame({
        "id": vendas["id"],
        "maquininha": "Vendemais",
        "quando": vendas["quando"],
        "bandeira": vendas["bandeira"].str.strip().str.title(),
        "modalidade": [_modalidade(p, n) for p, n in zip(vendas["tipo"], vendas["parcelas"])],
        "parcelas": vendas["parcelas"].astype(int),
        "bruto": vendas["bruto"].astype("int64"),
        "taxa": vendas["taxa"].astype("int64"),
        "liquido": vendas["liquido"].astype("int64"),
        "status": vendas["status"].str.strip().str.lower().map({"paga": "aprovada", "a receber": "aprovada", "estornada": "estornada", "chargeback": "contestada"}).fillna("aprovada"),
    })
    recebiveis = pd.DataFrame({
        "transacao_id": t["id"],
        "maquininha": "Vendemais",
        "parcela": t["parcela"],
        "data_prevista": pd.to_datetime(t["Data prevista"], format="%d/%m/%Y"),
        "valor": t["liquido"].astype("int64"),
    })
    return transacoes, recebiveis


def _dividir(total: int, partes: int) -> list[int]:
    """O líquido em parcelas; o centavo que sobra vai na primeira, como as maquininhas fazem."""
    base, sobra = divmod(total, partes)
    return [base + (sobra if i == 0 else 0) for i in range(partes)]


@dataclass(frozen=True)
class Formato:
    maquininha: str
    cabecalho: str
    ler: object


FORMATOS = [
    Formato("Cartix", "Data da venda;Bandeira;Produto", _cartix),
    Formato("PagaJá", "transaction_id,created_at,card_brand", _pagaja),
    Formato("Vendemais", "ID da transação;Data;Hora;Cartão", _vendemais),
]


def ler_extrato(conteudo: bytes) -> tuple[str, pd.DataFrame, pd.DataFrame]:
    """Descobre de que maquininha é o extrato pelo cabeçalho e devolve (maquininha, transações, recebíveis)."""
    texto = texto_do_arquivo(conteudo)
    primeira_linha = texto.splitlines()[0] if texto else ""
    for formato in FORMATOS:
        if primeira_linha.startswith(formato.cabecalho):
            transacoes, recebiveis = formato.ler(texto)
            return formato.maquininha, transacoes[COLUNAS_TRANSACOES], recebiveis[COLUNAS_RECEBIVEIS]
    raise FormatoDesconhecido("Não reconheci o extrato: o cabeçalho não é de nenhuma maquininha cadastrada.")


def ler_vendas_do_caixa(conteudo: bytes) -> pd.DataFrame:
    """O relatório de vendas do sistema do caixa: data;hora;valor;forma;parcelas;maquininha."""
    t = _tabela(texto_do_arquivo(conteudo), ";")
    esperadas = {"data", "hora", "valor", "forma", "parcelas", "maquininha"}
    if not esperadas <= set(t.columns):
        raise FormatoDesconhecido(f"O relatório do caixa precisa das colunas {', '.join(sorted(esperadas))}.")
    vendas = pd.DataFrame({
        "venda": range(1, len(t) + 1),
        "quando": pd.to_datetime(t["data"] + " " + t["hora"], format="%d/%m/%Y %H:%M"),
        "valor": t["valor"].map(centavos),
        "forma": t["forma"].str.strip().str.lower(),
        "parcelas": t["parcelas"].replace("", "1").astype(int),
        "maquininha": t["maquininha"].str.strip(),
    })
    return vendas


def ler_extrato_do_banco(conteudo: bytes) -> pd.DataFrame:
    """O extrato da conta, exportado em CSV pelo banco: data;historico;valor."""
    t = _tabela(texto_do_arquivo(conteudo), ";")
    return pd.DataFrame({
        "data": pd.to_datetime(t["data"], format="%d/%m/%Y"),
        "historico": t["historico"].str.strip(),
        "valor": t["valor"].map(centavos),
    })
