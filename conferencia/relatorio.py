"""A conferência do mês: lê os arquivos, confere taxas, vendas e depósitos e devolve um relatório
em dicionário simples (números em centavos, datas em ISO), que o painel em Django e a demonstração
no navegador mostram cada um do seu jeito."""

from __future__ import annotations

from decimal import Decimal

import pandas as pd

from .casamento import casar
from .depositos import conferir_depositos
from .dinheiro import aplicar_percentual, percentual, reais
from .formatos import COLUNAS_RECEBIVEIS, COLUNAS_TRANSACOES, FormatoDesconhecido, ler_extrato, ler_extrato_do_banco, ler_vendas_do_caixa, texto_do_arquivo
from .taxas import ler_tabela, nome_da_faixa, percentual_contratado

GRAVIDADE = {"alta": 0, "media": 1, "info": 2}
TOLERANCIA_EM_CENTAVOS = 1


def _dia(data) -> str:
    return pd.Timestamp(data).strftime("%d/%m")


def _hora(data) -> str:
    return pd.Timestamp(data).strftime("%d/%m às %H:%M")


def _separar(arquivos: dict[str, bytes]):
    extratos, vendas, banco, erros = [], [], [], []
    for nome, conteudo in arquivos.items():
        cabecalho = texto_do_arquivo(conteudo).splitlines()[0].strip().lower() if conteudo else ""
        try:
            if cabecalho.startswith("data;hora;valor;forma"):
                vendas.append(ler_vendas_do_caixa(conteudo))
            elif cabecalho.startswith("data;historico;valor"):
                banco.append(ler_extrato_do_banco(conteudo))
            else:
                extratos.append(ler_extrato(conteudo))
        except FormatoDesconhecido as erro:
            erros.append(f"{nome}: {erro}")
        except (ValueError, KeyError) as erro:
            erros.append(f"{nome}: o arquivo parece ser do formato certo, mas tem uma linha que não deu para ler ({erro}).")
    return extratos, vendas, banco, erros


def _conferir_taxas(transacoes: pd.DataFrame, tabela) -> pd.DataFrame:
    linhas = []
    for t in transacoes.itertuples(index=False):
        contratado = percentual_contratado(tabela, t.maquininha, t.modalidade, int(t.parcelas))
        esperado = aplicar_percentual(int(t.bruto), contratado) if contratado is not None else None
        linhas.append({
            "id": t.id,
            "contratado": contratado,
            "esperado": esperado,
            "diferenca": int(t.taxa) - esperado if esperado is not None else 0,
            "cobrado_pct": (Decimal(int(t.taxa)) * 100 / Decimal(int(t.bruto))).quantize(Decimal("0.01")) if t.bruto else Decimal(0),
        })
    return transacoes.merge(pd.DataFrame(linhas), on="id")


def percentual_aplicado(brutos: list[int], taxas: list[int]) -> Decimal:
    """O percentual que a maquininha está aplicando de fato. Com o arredondamento ao centavo, o
    percentual de cada venda varia (R$ 4,50 a 3,29% dá R$ 0,15, que é 3,33%); o aplicado é o que
    reproduz, exatamente, o maior número de cobranças."""
    efetivos = [Decimal(t) * 100 / Decimal(b) for b, t in zip(brutos, taxas) if b]
    if not efetivos:
        return Decimal(0)
    menor, maior = (min(efetivos) - Decimal("0.05")).quantize(Decimal("0.01")), (max(efetivos) + Decimal("0.05")).quantize(Decimal("0.01"))
    melhor, acertos = Decimal(0), -1
    candidato = max(menor, Decimal("0.01"))
    while candidato <= maior:
        certos = sum(aplicar_percentual(b, candidato) == t for b, t in zip(brutos, taxas))
        if certos > acertos:
            melhor, acertos = candidato, certos
        candidato += Decimal("0.01")
    return melhor


def conferir(arquivos: dict[str, bytes], taxas: dict[str, dict[str, object]]) -> dict:
    """Arquivos: nome → bytes (os extratos das maquininhas, o relatório do caixa e o extrato do banco)."""
    tabela = ler_tabela(taxas)
    extratos, lista_vendas, lista_banco, erros = _separar(arquivos)

    transacoes = pd.concat([e[1] for e in extratos], ignore_index=True) if extratos else pd.DataFrame(columns=COLUNAS_TRANSACOES)
    recebiveis = pd.concat([e[2] for e in extratos], ignore_index=True) if extratos else pd.DataFrame(columns=COLUNAS_RECEBIVEIS)
    vendas = pd.concat(lista_vendas, ignore_index=True) if lista_vendas else pd.DataFrame(columns=["venda", "quando", "valor", "forma", "parcelas", "maquininha"])
    banco = pd.concat(lista_banco, ignore_index=True) if lista_banco else pd.DataFrame(columns=["data", "historico", "valor"])
    maquininhas = sorted(transacoes["maquininha"].unique().tolist())

    alertas: list[dict] = []
    if transacoes.empty:
        return {"erros": erros or ["Nenhum extrato de maquininha entre os arquivos."], "alertas": [], "maquininhas": [], "taxas": [], "vendas": {}, "depositos": [], "agenda": [], "totais": {}, "periodo": None}

    # 1. Taxas: o que foi cobrado contra o que foi contratado, venda por venda.
    conferidas = _conferir_taxas(transacoes, tabela)
    aprovadas = conferidas[conferidas["status"] == "aprovada"]
    sem_tabela = aprovadas[aprovadas["contratado"].isna()]
    for (maquininha, modalidade, parcelas), grupo in sem_tabela.groupby(["maquininha", "modalidade", "parcelas"]):
        alertas.append({"gravidade": "info", "tipo": "sem-taxa", "titulo": f"{maquininha}: sem taxa cadastrada para {nome_da_faixa(modalidade, int(parcelas))}", "detalhe": f"{len(grupo)} vendas não foram conferidas. Cadastre a taxa contratada.", "valor": 0})

    divergentes = aprovadas[aprovadas["contratado"].notna() & (aprovadas["diferenca"].abs() > TOLERANCIA_EM_CENTAVOS)]
    divergencias = []
    fim_do_periodo = transacoes["quando"].max()
    for (maquininha, modalidade, parcelas), grupo in divergentes.groupby(["maquininha", "modalidade", "parcelas"]):
        contratado = grupo["contratado"].iloc[0]
        cobrado = percentual_aplicado(grupo["bruto"].tolist(), grupo["taxa"].tolist())
        a_mais = int(grupo["diferenca"].sum())
        primeira = grupo["quando"].min()
        dias = max(1, (fim_do_periodo - primeira).days + 1)
        por_ano = a_mais * 365 // dias
        divergencias.append({
            "maquininha": maquininha,
            "faixa": nome_da_faixa(modalidade, int(parcelas)),
            "contratado": str(contratado),
            "cobrado": str(cobrado),
            "desde": primeira.isoformat(),
            "vendas": len(grupo),
            "diferenca": a_mais,
        })
        if a_mais > 0:
            alertas.append({
                "gravidade": "alta",
                "tipo": "taxa",
                "titulo": f"{maquininha} cobrou {percentual(cobrado)} no {nome_da_faixa(modalidade, int(parcelas))}; o contratado é {percentual(contratado)}",
                "detalhe": f"Desde {_dia(primeira)}, em {len(grupo)} vendas: {reais(a_mais)} a mais, perto de {reais(por_ano)} por ano nesse ritmo. Peça o estorno da diferença e a taxa contratada de volta.",
                "valor": a_mais,
            })

    # 2. Vendas do caixa contra transações das maquininhas.
    resumo_vendas: dict = {}
    if not vendas.empty:
        pares, sem_transacao, sem_venda = casar(vendas, transacoes)
        for v in sem_transacao.itertuples(index=False):
            alertas.append({"gravidade": "media", "tipo": "venda-sem-transacao", "titulo": f"Venda do caixa sem transação na {v.maquininha}: {reais(int(v.valor))}", "detalhe": f"Registrada em {_hora(v.quando)}, no {nome_da_faixa(v.forma, int(v.parcelas))}. Pode ter sido passada em outra maquininha, ou não ter sido passada.", "valor": int(v.valor)})
        for t in sem_venda[sem_venda["status"] == "aprovada"].itertuples(index=False):
            alertas.append({"gravidade": "media", "tipo": "transacao-sem-venda", "titulo": f"Transação da {t.maquininha} que não está no caixa: {reais(int(t.bruto))}", "detalhe": f"Em {_hora(t.quando)}, {t.bandeira}, {nome_da_faixa(t.modalidade, int(t.parcelas))}. A venda não foi registrada no sistema.", "valor": int(t.bruto)})
        resumo_vendas = {
            "vendas_no_caixa": int(len(vendas)),
            "no_cartao": int(vendas["forma"].isin(["debito", "credito", "parcelado"]).sum()),
            "casadas": int(len(pares)),
            "sem_transacao": int(len(sem_transacao)),
            "sem_venda": int((sem_venda["status"] == "aprovada").sum()),
            "maior_diferenca_minutos": float(pares["minutos"].max()) if not pares.empty else 0.0,
        }

    # 3. Estornos e contestações.
    for t in transacoes[transacoes["status"] != "aprovada"].itertuples(index=False):
        if t.status == "contestada":
            alertas.append({"gravidade": "alta", "tipo": "contestacao", "titulo": f"Cliente contestou uma venda de {reais(int(t.bruto))} na {t.maquininha}", "detalhe": f"Venda de {_hora(t.quando)}, {t.bandeira}. A maquininha segura o valor até a disputa acabar: separe o comprovante e a nota.", "valor": int(t.bruto)})
        else:
            alertas.append({"gravidade": "info", "tipo": "estorno", "titulo": f"Estorno de {reais(int(t.bruto))} na {t.maquininha}", "detalhe": f"Venda de {_hora(t.quando)}. Confira se a devolução foi combinada com o cliente.", "valor": int(t.bruto)})

    # 4. Depósitos: o previsto de cada dia contra o que entrou na conta.
    validas = set(transacoes.loc[transacoes["status"] == "aprovada", "id"])
    recebiveis_validos = recebiveis[recebiveis["transacao_id"].isin(validas)]
    depositos, agenda = conferir_depositos(recebiveis_validos, banco, maquininhas)
    for d in depositos[~depositos["situacao"].isin(["ok", "aguardando"])].itertuples(index=False):
        if d.situacao == "não caiu":
            alertas.append({"gravidade": "alta", "tipo": "deposito", "titulo": f"Depósito da {d.maquininha} de {_dia(d.data)} não caiu: {reais(int(d.previsto))}", "detalhe": "O extrato da maquininha previa o pagamento nesse dia, e nada entrou na conta até o dia útil seguinte.", "valor": int(d.previsto)})
        else:
            alertas.append({"gravidade": "alta" if d.diferenca < 0 else "info", "tipo": "deposito", "titulo": f"Depósito da {d.maquininha} de {_dia(d.data)} {d.situacao}: {reais(abs(int(d.diferenca)))}", "detalhe": f"Previsto {reais(int(d.previsto))}, entrou {reais(int(d.recebido))}.", "valor": abs(int(d.diferenca))})

    # 5. Resumo por maquininha.
    resumo = []
    for maquininha, grupo in conferidas[conferidas["status"] == "aprovada"].groupby("maquininha"):
        bruto, taxa = int(grupo["bruto"].sum()), int(grupo["taxa"].sum())
        esperado = int(grupo["esperado"].dropna().sum())
        a_mais = int(grupo.loc[grupo["diferenca"] > TOLERANCIA_EM_CENTAVOS, "diferenca"].sum())
        resumo.append({
            "maquininha": maquininha,
            "vendas": int(len(grupo)),
            "bruto": bruto,
            "taxa": taxa,
            "taxa_esperada": esperado,
            "cobrado_a_mais": a_mais,
            "taxa_efetiva": str((Decimal(taxa) * 100 / Decimal(bruto)).quantize(Decimal("0.01"))) if bruto else "0.00",
            "liquido": int(grupo["liquido"].sum()),
        })

    alertas.sort(key=lambda a: (GRAVIDADE[a["gravidade"]], -a["valor"]))
    return {
        "erros": erros,
        "periodo": {"de": transacoes["quando"].min().date().isoformat(), "ate": transacoes["quando"].max().date().isoformat()},
        "totais": {
            "bruto": sum(r["bruto"] for r in resumo),
            "taxa": sum(r["taxa"] for r in resumo),
            "cobrado_a_mais": sum(r["cobrado_a_mais"] for r in resumo),
            "nao_recebido": int(-depositos.loc[depositos["situacao"].isin(["não caiu", "veio a menos"]), "diferenca"].sum()) if not depositos.empty else 0,
            "a_receber": int(agenda["valor"].sum()) if not agenda.empty else 0,
            "conferido_ate": banco["data"].max().date().isoformat() if not banco.empty else None,
        },
        "alertas": alertas,
        "maquininhas": resumo,
        "taxas": divergencias,
        "vendas": resumo_vendas,
        "depositos": [
            {"maquininha": d.maquininha, "data": d.data.date().isoformat(), "previsto": int(d.previsto), "recebido": int(d.recebido), "situacao": d.situacao}
            for d in depositos.itertuples(index=False)
        ],
        "agenda": [{"data": a.data.date().isoformat(), "maquininha": a.maquininha, "valor": int(a.valor)} for a in agenda.itertuples(index=False)],
    }
