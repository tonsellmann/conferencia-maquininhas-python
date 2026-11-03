from django.conf import settings
from django.db import models

FAIXAS = [
    ("debito", "Débito"),
    ("credito", "Crédito à vista"),
    ("parcelado 2-6", "Parcelado de 2 a 6 vezes"),
    ("parcelado 7-12", "Parcelado de 7 a 12 vezes"),
    ("parcelado 2-12", "Parcelado de 2 a 12 vezes"),
]


class Maquininha(models.Model):
    nome = models.CharField("nome", max_length=40, unique=True, help_text="Como aparece no extrato do banco, sem acento tanto faz: Cartix, PagaJá.")

    class Meta:
        ordering = ["nome"]
        verbose_name = "maquininha"

    def __str__(self):
        return self.nome


class Taxa(models.Model):
    maquininha = models.ForeignKey(Maquininha, on_delete=models.CASCADE, related_name="taxas")
    faixa = models.CharField(max_length=20, choices=FAIXAS)
    percentual = models.DecimalField("taxa contratada (%)", max_digits=5, decimal_places=2)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["maquininha", "faixa"], name="uma_taxa_por_faixa")]
        verbose_name = "taxa contratada"
        verbose_name_plural = "taxas contratadas"

    def __str__(self):
        return f"{self.maquininha} · {self.get_faixa_display()}: {self.percentual}%"


def tabela_de_taxas() -> dict[str, dict[str, str]]:
    """As taxas cadastradas no formato que a conferência usa."""
    tabela: dict[str, dict[str, str]] = {}
    for taxa in Taxa.objects.select_related("maquininha"):
        tabela.setdefault(taxa.maquininha.nome, {})[taxa.faixa] = str(taxa.percentual)
    return tabela


class Conferencia(models.Model):
    criada_em = models.DateTimeField(auto_now_add=True)
    criada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="conferencias")
    periodo_de = models.DateField(null=True)
    periodo_ate = models.DateField(null=True)
    arquivos = models.JSONField(default=list)
    resultado = models.JSONField()

    class Meta:
        ordering = ["-criada_em"]
        verbose_name = "conferência"

    def __str__(self):
        return f"Conferência de {self.periodo_de:%d/%m} a {self.periodo_ate:%d/%m/%Y}" if self.periodo_de else "Conferência sem extrato"

    @property
    def alertas_graves(self) -> int:
        return sum(1 for a in self.resultado.get("alertas", []) if a["gravidade"] == "alta")
