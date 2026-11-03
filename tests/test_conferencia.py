from decimal import Decimal
from pathlib import Path
import sys

import pandas as pd
import pytest

from conferencia import conferir
from conferencia.casamento import casar
from conferencia.depositos import conferir_depositos, maquininha_do_lancamento
from conferencia.dinheiro import aplicar_percentual, centavos, reais
from conferencia.formatos import FormatoDesconhecido, ler_extrato, ler_extrato_do_banco, ler_vendas_do_caixa
from conferencia.relatorio import percentual_aplicado
from conferencia.taxas import ler_tabela, percentual_contratado

EXEMPLOS = Path(__file__).parent.parent / "exemplos"
sys.path.insert(0, str(EXEMPLOS))
from gerar_exemplos import TAXAS, gerar  # noqa: E402


# ---- dinheiro ---------------------------------------------------------------------------------

@pytest.mark.parametrize("texto, esperado", [
    ("1.234,56", 123456), ("1234.56", 123456), ("R$ 12,00", 1200), ("-10,00", -1000),
    ("0,5", 50), ("7", 700), (12.5, 1250), ("1.234.567,89", 123456789),
])
def test_le_valor_de_qualquer_extrato(texto, esperado):
    assert centavos(texto) == esperado


def test_recusa_valor_que_nao_e_valor():
    with pytest.raises(ValueError):
        centavos("doze reais")
    with pytest.raises(ValueError):
        centavos("")


def test_escreve_reais_e_arredonda_a_taxa_meio_para_cima():
    assert reais(123456) == "R$ 1.234,56"
    assert reais(-50) == "-R$ 0,50"
    assert aplicar_percentual(450, Decimal("3.29")) == 15  # 14,805 centavos
    assert aplicar_percentual(1000, Decimal("1.25")) == 13  # 12,5 → 13


# ---- formatos ---------------------------------------------------------------------------------

CARTIX = (
    "Data da venda;Bandeira;Produto;Parcelas;Valor bruto;Taxa (R$);Valor líquido;NSU;Previsão de pagamento;Situação\n"
    "05/10/2026 14:03;VISA;Crédito parcelado;3;300,00;10,47;289,53;000123;04/11/2026;Aprovada\n"
    "05/10/2026 15:10;ELO;Débito;1;12,50;0,17;12,33;000124;06/10/2026;Cancelada\n"
)


def test_le_o_extrato_da_cartix_em_latin1_e_abre_as_parcelas():
    maquininha, transacoes, recebiveis = ler_extrato(CARTIX.encode("latin-1"))
    assert maquininha == "Cartix"
    assert transacoes[["id", "modalidade", "parcelas", "bruto", "taxa", "status"]].values.tolist() == [
        ["CX-000123", "parcelado", 3, 30000, 1047, "aprovada"],
        ["CX-000124", "debito", 1, 1250, 17, "estornada"],
    ]
    parcelas = recebiveis[recebiveis["transacao_id"] == "CX-000123"]
    assert parcelas["valor"].tolist() == [9651, 9651, 9651]
    assert parcelas["data_prevista"].dt.strftime("%d/%m").tolist() == ["04/11", "04/12", "03/01"]


def test_le_o_extrato_da_pagaja_com_data_iso_e_fuso():
    texto = (
        "transaction_id,created_at,card_brand,payment_method,installments,gross_amount,fee_amount,net_amount,status,settlement_date\n"
        "a1,2026-10-05T23:30:00-03:00,mastercard,credit,1,45.90,1.45,44.45,chargeback,2026-11-04\n"
    )
    _, transacoes, _ = ler_extrato(texto.encode())
    linha = transacoes.iloc[0]
    assert (linha["quando"].strftime("%d/%m %H:%M"), linha["bandeira"], linha["status"], linha["liquido"]) == ("05/10 23:30", "Mastercard", "contestada", 4445)


def test_le_o_extrato_da_vendemais_que_vem_uma_linha_por_parcela():
    texto = (
        "ID da transação;Data;Hora;Cartão;Tipo;Parcela;Total de parcelas;Valor da parcela;Desconto;Líquido da parcela;Data prevista;Status\n"
        "77;05/10/2026;10:00:00;Visa;Crédito;1;2;100,01;3,29;96,72;04/11/2026;A receber\n"
        "77;05/10/2026;10:00:00;Visa;Crédito;2;2;100,00;3,29;96,71;04/12/2026;A receber\n"
    )
    _, transacoes, recebiveis = ler_extrato(("﻿" + texto).encode("utf-8"))
    assert transacoes[["id", "modalidade", "parcelas", "bruto", "taxa"]].values.tolist() == [["VM-77", "parcelado", 2, 20001, 658]]
    assert recebiveis["valor"].tolist() == [9672, 9671]


def test_extrato_desconhecido_diz_o_que_aconteceu():
    with pytest.raises(FormatoDesconhecido):
        ler_extrato(b"coluna1;coluna2\n1;2\n")


def test_tabela_de_taxas_por_faixa_de_parcelas():
    tabela = ler_tabela({"Cartix": {"debito": "1.37", "credito": "2,49", "parcelado 2-6": "3.49", "parcelado 7-12": "3.99"}})
    assert percentual_contratado(tabela, "Cartix", "credito", 1) == Decimal("2.49")
    assert percentual_contratado(tabela, "Cartix", "parcelado", 6) == Decimal("3.49")
    assert percentual_contratado(tabela, "Cartix", "parcelado", 7) == Decimal("3.99")
    assert percentual_contratado(tabela, "PagaJá", "debito", 1) is None


def test_descobre_o_percentual_que_a_maquininha_aplicou():
    brutos = [450, 1200, 2340, 3450, 7990, 1890]
    taxas = [aplicar_percentual(b, Decimal("3.29")) for b in brutos]
    assert percentual_aplicado(brutos, taxas) == Decimal("3.29")


# ---- casamento das vendas ---------------------------------------------------------------------

def test_casa_vendas_iguais_pela_hora_mais_proxima():
    vendas = pd.DataFrame({
        "venda": [1, 2, 3],
        "quando": pd.to_datetime(["2026-10-17 07:11", "2026-10-17 07:16", "2026-10-17 09:00"]),
        "valor": [1200, 1200, 3450],
        "forma": ["debito", "debito", "credito"],
        "parcelas": [1, 1, 1],
        "maquininha": ["Cartix", "Cartix", "Cartix"],
    })
    transacoes = pd.DataFrame({
        "id": ["A", "B", "C"],
        "maquininha": ["Cartix"] * 3,
        "quando": pd.to_datetime(["2026-10-17 07:15:40", "2026-10-17 07:12:05", "2026-10-17 12:00:00"]),
        "bruto": [1200, 1200, 3450],
        "modalidade": ["debito", "debito", "credito"],
        "status": ["aprovada"] * 3,
    })
    pares, sem_transacao, sem_venda = casar(vendas, transacoes)
    assert sorted(zip(pares["venda"], pares["transacao"])) == [(1, "B"), (2, "A")]
    assert sem_transacao["venda"].tolist() == [3]  # 3 horas de diferença não é a mesma venda
    assert sem_venda["id"].tolist() == ["C"]


# ---- depósitos --------------------------------------------------------------------------------

def test_reconhece_a_maquininha_no_historico_do_banco():
    assert maquininha_do_lancamento("TED RECEBIDA PAGAJA INST PGTO", ["Cartix", "PagaJá"]) == "PagaJá"
    assert maquininha_do_lancamento("PAG CONTA ENERGIA", ["Cartix", "PagaJá"]) is None


def test_deposito_que_faltou_nao_rouba_o_do_dia_seguinte():
    recebiveis = pd.DataFrame({
        "transacao_id": ["a", "b", "c"],
        "maquininha": ["PagaJá"] * 3,
        "parcela": [1, 1, 1],
        "data_prevista": pd.to_datetime(["2026-10-20", "2026-10-21", "2026-10-22"]),
        "valor": [19534, 8748, 17040],
    })
    banco = pd.DataFrame({
        "data": pd.to_datetime(["2026-10-21", "2026-10-22", "2026-10-23"]),
        "historico": ["TED PAGAJA"] * 3,
        "valor": [8748, 17040, 999],
    })
    conferencia, _ = conferir_depositos(recebiveis, banco, ["PagaJá"])
    assert conferencia["situacao"].tolist() == ["não caiu", "ok", "ok"]


def test_lancado_no_dia_util_seguinte_nao_e_atraso_e_o_ultimo_dia_fica_aguardando():
    recebiveis = pd.DataFrame({
        "transacao_id": ["a", "b"],
        "maquininha": ["Cartix", "Cartix"],
        "parcela": [1, 1],
        "data_prevista": pd.to_datetime(["2026-10-07", "2026-10-30"]),
        "valor": [5000, 7000],
    })
    banco = pd.DataFrame({"data": pd.to_datetime(["2026-10-08"]), "historico": ["CRED CARTIX"], "valor": [5000]})
    banco = pd.concat([banco, pd.DataFrame({"data": pd.to_datetime(["2026-10-30"]), "historico": ["PAG ENERGIA"], "valor": [-100]})])
    conferencia, futuro = conferir_depositos(recebiveis, banco, ["Cartix"])
    assert conferencia["situacao"].tolist() == ["ok", "aguardando"]
    assert futuro.empty


# ---- o mês de exemplo inteiro -----------------------------------------------------------------

@pytest.fixture(scope="module")
def relatorio_de_outubro():
    gerar()
    arquivos = {p.name: p.read_bytes() for p in (EXEMPLOS / "outubro-2026").glob("*.csv")}
    return conferir(arquivos, TAXAS)


def test_acha_exatamente_os_problemas_plantados(relatorio_de_outubro):
    r = relatorio_de_outubro
    assert r["erros"] == []
    tipos = sorted(a["tipo"] for a in r["alertas"])
    assert tipos == sorted(["deposito", "deposito", "contestacao", "taxa", "venda-sem-transacao", "venda-sem-transacao", "transacao-sem-venda", "estorno"])
    titulos = [a["titulo"] for a in r["alertas"]]
    assert "Cartix cobrou 3,29% no crédito à vista; o contratado é 2,49%" in titulos
    assert "Depósito da PagaJá de 20/10 não caiu: R$ 195,34" in titulos
    assert "Depósito da Vendemais de 26/10 veio a menos: R$ 89,90" in titulos
    # O mais grave e o de maior valor primeiro
    assert r["alertas"][0]["gravidade"] == "alta" and r["alertas"][-1]["gravidade"] == "info"


def test_casa_as_vendas_do_mes(relatorio_de_outubro):
    vendas = relatorio_de_outubro["vendas"]
    assert vendas["no_cartao"] == vendas["casadas"] + vendas["sem_transacao"]
    assert (vendas["sem_transacao"], vendas["sem_venda"]) == (2, 1)


def test_resumo_bate_com_os_extratos(relatorio_de_outubro):
    r = relatorio_de_outubro
    cartix = next(m for m in r["maquininhas"] if m["maquininha"] == "Cartix")
    assert cartix["cobrado_a_mais"] == r["totais"]["cobrado_a_mais"] > 0
    assert all(m["bruto"] - m["taxa"] == m["liquido"] for m in r["maquininhas"])
    assert r["totais"]["nao_recebido"] == 19534 + 8990
    assert r["agenda"] and all(a["data"] > r["totais"]["conferido_ate"] for a in r["agenda"])


def test_arquivo_estranho_vira_erro_e_nao_derruba_a_conferencia(relatorio_de_outubro):
    arquivos = {p.name: p.read_bytes() for p in (EXEMPLOS / "outubro-2026").glob("*.csv")}
    arquivos["fotos.csv"] = b"isso;nao;e;extrato\n1;2;3;4\n"
    r = conferir(arquivos, TAXAS)
    assert len(r["erros"]) == 1 and r["erros"][0].startswith("fotos.csv: ")
    assert len(r["alertas"]) == len(relatorio_de_outubro["alertas"])
