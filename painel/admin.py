from django.contrib import admin

from .models import Conferencia, Maquininha, Taxa


class TaxaInline(admin.TabularInline):
    model = Taxa
    extra = 1


@admin.register(Maquininha)
class MaquininhaAdmin(admin.ModelAdmin):
    inlines = [TaxaInline]
    list_display = ["nome", "taxas_cadastradas"]

    @admin.display(description="taxas")
    def taxas_cadastradas(self, maquininha):
        return ", ".join(f"{t.get_faixa_display()}: {t.percentual}%" for t in maquininha.taxas.all())


@admin.register(Conferencia)
class ConferenciaAdmin(admin.ModelAdmin):
    list_display = ["__str__", "criada_em", "criada_por", "alertas_graves"]
    readonly_fields = ["criada_em", "criada_por", "periodo_de", "periodo_ate", "arquivos", "resultado"]
