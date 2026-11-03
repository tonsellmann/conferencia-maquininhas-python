"""Gera o mês de exemplo da Padaria Bom Dia (fictícia, em Itabuna): o relatório do caixa, os
extratos das três maquininhas e o extrato do banco de outubro de 2026, com problemas plantados
para a conferência achar.

    python exemplos/gerar_exemplos.py

Plantados de propósito:
- a taxa promocional da Cartix no crédito à vista (2,49%) acaba sem aviso: a partir de 15/10, 3,29%;
- o depósito da PagaJá de 20/10 não cai;
- o repasse da Vendemais de 26/10 vem R$ 89,90 a menos (o aluguel da maquininha, descontado sem aviso);
- duas vendas do caixa sem transação e uma transação sem venda no caixa;
- um estorno na Cartix e uma contestação na Vendemais;
- duas vendas de R$ 12,00 no débito da Cartix com três minutos de diferença.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

PASTA = Path(__file__).parent / "outubro-2026"
FERIADOS = {date(2026, 10, 12), date(2026, 11, 2), date(2026, 11, 15), date(2026, 11, 20)}

TAXAS = {
    "Cartix": {"debito": "1.37", "credito": "2.49", "parcelado 2-6": "3.49", "parcelado 7-12": "3.99"},
    "PagaJá": {"debito": "1.49", "credito": "3.15", "parcelado 2-12": "3.79"},
    "Vendemais": {"debito": "0.99", "credito": "2.69", "parcelado 2-6": "3.29", "parcelado 7-12": "3.79"},
}


def dia_util(d: date) -> bool:
    return d.weekday() < 5 and d not in FERIADOS


def proximo_dia_util(d: date, depois: int = 1) -> date:
    for _ in range(depois):
        d += timedelta(days=1)
        while not dia_util(d):
            d += timedelta(days=1)
    return d


def taxa_de(maquininha: str, modalidade: str, parcelas: int) -> Decimal:
    tabela = TAXAS[maquininha]
    if modalidade != "parcelado":
        return Decimal(tabela[modalidade])
    for chave, valor in tabela.items():
        if chave.startswith("parcelado"):
            de, ate = (int(n) for n in chave.split()[1].split("-"))
            if de <= parcelas <= ate:
                return Decimal(valor)
    raise KeyError(maquininha)


def centavos_de(valor: Decimal) -> int:
    return int(valor.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def br(c: int) -> str:
    inteiro, resto = divmod(c, 100)
    return f"{inteiro:,}".replace(",", ".") + f",{resto:02d}"


def ponto(c: int) -> str:
    return f"{c // 100}.{c % 100:02d}"


@dataclass
class Venda:
    id: str
    maquininha: str
    quando: datetime
    bandeira: str
    modalidade: str
    parcelas: int
    bruto: int
    taxa: int = 0
    status: str = "aprovada"
    no_caixa: bool = True
    caixa_quando: datetime | None = None
    parcelas_liquidas: list[tuple[date, int, int, int]] = field(default_factory=list)  # (data, bruto, taxa, liquido)

    @property
    def liquido(self) -> int:
        return self.bruto - self.taxa


def gerar() -> None:
    sorteio = random.Random(2026)
    vendas: list[Venda] = []
    caixa_extra: list[tuple[datetime, int, str, int, str]] = []  # vendas em dinheiro e Pix
    n = 0

    dia = date(2026, 10, 1)
    while dia <= date(2026, 10, 31):
        movimento = 52 if dia.weekday() >= 5 else 40
        for _ in range(movimento):
            n += 1
            quando = datetime.combine(dia, datetime.min.time()) + timedelta(minutes=sorteio.randint(6 * 60, 20 * 60 - 1), seconds=sorteio.randint(0, 59))
            forma = sorteio.choices(["debito", "credito", "parcelado", "pix", "dinheiro"], [42, 30, 2, 18, 8])[0]
            if forma == "parcelado":
                bruto = sorteio.randint(150, 420) * 100 + sorteio.choice([0, 50, 90])
                parcelas = sorteio.choice([2, 3])
            else:
                bruto = sorteio.choice([450, 690, 890, 1200, 1250, 1590, 1890, 2340, 2790, 3450, 4120, 5680, 7990])
                parcelas = 1
            if forma in ("pix", "dinheiro"):
                caixa_extra.append((quando + timedelta(minutes=sorteio.randint(0, 2)), bruto, forma, 1, ""))
                continue
            maquininha = sorteio.choices(["Cartix", "PagaJá", "Vendemais"], [45, 30, 25])[0]
            bandeira = sorteio.choices(["Visa", "Mastercard", "Elo"], [45, 40, 15])[0]
            venda = Venda(f"{n:06d}", maquininha, quando, bandeira, forma, parcelas, bruto)
            venda.caixa_quando = quando + timedelta(minutes=sorteio.randint(-3, 4), seconds=sorteio.randint(0, 59))
            vendas.append(venda)
        dia += timedelta(days=1)

    # Duas vendas iguais com três minutos de diferença, para o casamento escolher o par certo.
    gemeas = [
        Venda("900001", "Cartix", datetime(2026, 10, 17, 7, 12, 5), "Visa", "debito", 1, 1200),
        Venda("900002", "Cartix", datetime(2026, 10, 17, 7, 15, 40), "Elo", "debito", 1, 1200),
    ]
    gemeas[0].caixa_quando = datetime(2026, 10, 17, 7, 11, 30)
    gemeas[1].caixa_quando = datetime(2026, 10, 17, 7, 16, 10)
    vendas += gemeas

    # Taxas. A taxa promocional da Cartix no crédito à vista (2,49%) acaba sem aviso em 15/10.
    for v in vendas:
        percentual = taxa_de(v.maquininha, v.modalidade, v.parcelas)
        if v.maquininha == "Cartix" and v.modalidade == "credito" and v.quando.date() >= date(2026, 10, 15):
            percentual = Decimal("3.29")
        v.taxa = centavos_de(Decimal(v.bruto) * percentual / 100)

    # Planta os problemas.
    por_maquininha = lambda nome, modalidade: [v for v in vendas if v.maquininha == nome and v.modalidade == modalidade]
    sorteio.choice(por_maquininha("Cartix", "debito")).status = "estornada"
    sorteio.choice(por_maquininha("Vendemais", "credito")).status = "contestada"
    sorteio.choice(por_maquininha("PagaJá", "debito")).no_caixa = False
    fantasmas = [
        (datetime(2026, 10, 9, 18, 42), 3450, "credito", 1, "Cartix"),
        (datetime(2026, 10, 23, 10, 5), 1890, "credito", 1, "Cartix"),
    ]

    # Agenda: débito em D+1 útil; crédito em D+30 (dia útil seguinte se cair em fim de semana);
    # parcelado com uma parcela a cada 30 dias.
    for v in vendas:
        base = v.quando.date()
        if v.modalidade == "debito":
            datas = [proximo_dia_util(base)]
        else:
            datas = []
            for parcela in range(1, v.parcelas + 1):
                d = base + timedelta(days=30 * parcela)
                datas.append(d if dia_util(d) else proximo_dia_util(d))
        base_bruto, sobra_bruto = divmod(v.bruto, v.parcelas)
        base_taxa, sobra_taxa = divmod(v.taxa, v.parcelas)
        for i, d in enumerate(datas):
            pb = base_bruto + (sobra_bruto if i == 0 else 0)
            pt = base_taxa + (sobra_taxa if i == 0 else 0)
            v.parcelas_liquidas.append((d, pb, pt, pb - pt))

    PASTA.mkdir(parents=True, exist_ok=True)
    vendas.sort(key=lambda v: v.quando)

    # Caixa
    linhas = ["data;hora;valor;forma;parcelas;maquininha"]
    registros = [(v.caixa_quando, v.bruto, v.modalidade, v.parcelas, v.maquininha) for v in vendas if v.no_caixa] + caixa_extra + fantasmas
    for quando, valor, forma, parcelas, maquininha in sorted(registros):
        linhas.append(f"{quando:%d/%m/%Y};{quando:%H:%M};{br(valor)};{forma};{parcelas};{maquininha}")
    (PASTA / "caixa-outubro-2026.csv").write_text("\n".join(linhas) + "\n", encoding="utf-8")

    # Cartix: latin-1, ';', vírgula decimal, uma linha por venda
    linhas = ["Data da venda;Bandeira;Produto;Parcelas;Valor bruto;Taxa (R$);Valor líquido;NSU;Previsão de pagamento;Situação"]
    for v in (v for v in vendas if v.maquininha == "Cartix"):
        produto = {"debito": "Débito", "credito": "Crédito à vista", "parcelado": "Crédito parcelado"}[v.modalidade]
        situacao = {"aprovada": "Aprovada", "estornada": "Cancelada", "contestada": "Em disputa"}[v.status]
        linhas.append(f"{v.quando:%d/%m/%Y %H:%M};{v.bandeira.upper()};{produto};{v.parcelas};{br(v.bruto)};{br(v.taxa)};{br(v.liquido)};{v.id};{v.parcelas_liquidas[0][0]:%d/%m/%Y};{situacao}")
    (PASTA / "cartix-outubro-2026.csv").write_bytes(("\n".join(linhas) + "\n").encode("latin-1"))

    # PagaJá: UTF-8, ',', ponto decimal, data ISO com fuso
    linhas = ["transaction_id,created_at,card_brand,payment_method,installments,gross_amount,fee_amount,net_amount,status,settlement_date"]
    for v in (v for v in vendas if v.maquininha == "PagaJá"):
        metodo = "debit" if v.modalidade == "debito" else "credit"
        status = {"aprovada": "approved", "estornada": "refunded", "contestada": "chargeback"}[v.status]
        linhas.append(f"{v.id},{v.quando:%Y-%m-%dT%H:%M:%S}-03:00,{v.bandeira.lower()},{metodo},{v.parcelas},{ponto(v.bruto)},{ponto(v.taxa)},{ponto(v.liquido)},{status},{v.parcelas_liquidas[0][0]:%Y-%m-%d}")
    (PASTA / "pagaja-october-2026.csv").write_text("\n".join(linhas) + "\n", encoding="utf-8")

    # Vendemais: UTF-8 com BOM, ';', uma linha por parcela
    linhas = ["ID da transação;Data;Hora;Cartão;Tipo;Parcela;Total de parcelas;Valor da parcela;Desconto;Líquido da parcela;Data prevista;Status"]
    for v in (v for v in vendas if v.maquininha == "Vendemais"):
        tipo = "Débito" if v.modalidade == "debito" else "Crédito"
        for i, (d, pb, pt, pl) in enumerate(v.parcelas_liquidas, start=1):
            status = {"estornada": "Estornada", "contestada": "Chargeback"}.get(v.status, "Paga" if d <= date(2026, 10, 31) else "A receber")
            linhas.append(f"{v.id};{v.quando:%d/%m/%Y};{v.quando:%H:%M:%S};{v.bandeira};{tipo};{i};{v.parcelas};{br(pb)};{br(pt)};{br(pl)};{d:%d/%m/%Y};{status}")
    (PASTA / "vendemais-outubro-2026.csv").write_text("\n".join(linhas) + "\n", encoding="utf-8-sig")

    # Banco: um crédito por maquininha e dia, até 30/10, com os problemas plantados
    depositos: dict[tuple[str, date], int] = {}
    for v in vendas:
        if v.status != "aprovada":
            continue
        for d, _, _, liquido in v.parcelas_liquidas:
            depositos[(v.maquininha, d)] = depositos.get((v.maquininha, d), 0) + liquido
    historico = {"Cartix": "CRED CARTIX PAGAMENTOS SA", "PagaJá": "TED RECEBIDA PAGAJA INST PGTO", "Vendemais": "CREDITO VENDEMAIS ADQ"}
    lancamentos = []
    for (maquininha, d), valor in sorted(depositos.items(), key=lambda x: (x[0][1], x[0][0])):
        if d > date(2026, 10, 30):
            continue
        if maquininha == "PagaJá" and d == date(2026, 10, 20):
            continue
        if maquininha == "Vendemais" and d == date(2026, 10, 26):
            valor -= 8990
        if maquininha == "Cartix" and d == date(2026, 10, 7):
            d = proximo_dia_util(d)  # lançado no dia útil seguinte: não é atraso
        lancamentos.append((d, historico[maquininha], valor))
    for d in (date(2026, 10, 5), date(2026, 10, 15), date(2026, 10, 25)):
        lancamentos.append((d, "PAG BOLETO MOINHO DO SUL FARINHAS", -sorteio.randint(180000, 260000)))
    lancamentos.append((date(2026, 10, 10), "PAG CONTA ENERGIA", -84230))
    linhas = ["data;historico;valor"]
    for d, texto, valor in sorted(lancamentos, key=lambda x: x[0]):
        linhas.append(f"{d:%d/%m/%Y};{texto};{'-' if valor < 0 else ''}{br(abs(valor))}")
    (PASTA / "banco-outubro-2026.csv").write_text("\n".join(linhas) + "\n", encoding="utf-8")

    print(f"{len(vendas)} vendas no cartão, {len(caixa_extra)} em dinheiro e Pix; arquivos em {PASTA}")


if __name__ == "__main__":
    gerar()
