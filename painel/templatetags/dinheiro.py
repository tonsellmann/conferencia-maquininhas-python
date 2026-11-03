from datetime import date

from django import template

from conferencia.dinheiro import percentual, reais

register = template.Library()


@register.filter
def em_reais(centavos):
    return reais(int(centavos or 0))


@register.filter
def em_percentual(valor):
    return percentual(valor)


@register.filter
def dia(iso):
    """'2026-10-20' → '20/10'."""
    return date.fromisoformat(str(iso)[:10]).strftime("%d/%m") if iso else ""
