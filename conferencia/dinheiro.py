"""Dinheiro em centavos inteiros. Cada extrato escreve valor de um jeito ("1.234,56", "1234.56",
"R$ 12,00"); aqui tudo vira int, e a conta de taxa não perde centavo em ponto flutuante."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation


def centavos(valor: object) -> int:
    """'1.234,56' → 123456; '1234.56' → 123456; '-10,00' → -1000; 12.5 → 1250."""
    if valor is None:
        raise ValueError("valor vazio")
    if isinstance(valor, int):
        return valor * 100
    if isinstance(valor, float):
        valor = repr(valor)
    texto = str(valor).strip().replace("R$", "").replace(" ", "").replace(" ", "")
    if not texto:
        raise ValueError("valor vazio")
    if "," in texto:
        # Formato brasileiro: ponto separa milhar, vírgula separa os centavos.
        texto = texto.replace(".", "").replace(",", ".")
    try:
        numero = Decimal(texto)
    except InvalidOperation as erro:
        raise ValueError(f"valor inválido: {valor!r}") from erro
    return int((numero * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def reais(centavos_: int) -> str:
    """123456 → 'R$ 1.234,56'."""
    sinal = "-" if centavos_ < 0 else ""
    inteiro, resto = divmod(abs(int(centavos_)), 100)
    return f"{sinal}R$ {inteiro:,}".replace(",", ".") + f",{resto:02d}"


def percentual(valor: Decimal | float) -> str:
    """Decimal('2.99') → '2,99%'."""
    return f"{Decimal(str(valor)).quantize(Decimal('0.01'))}%".replace(".", ",")


def aplicar_percentual(centavos_: int, percentual_: Decimal) -> int:
    """A taxa de uma venda: o percentual sobre o bruto, arredondado ao centavo (meio para cima)."""
    return int((Decimal(centavos_) * percentual_ / 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
