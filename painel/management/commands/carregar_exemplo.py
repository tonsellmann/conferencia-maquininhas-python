"""Cadastra as três maquininhas do exemplo e as taxas contratadas: python manage.py carregar_exemplo"""

import sys
from pathlib import Path

from django.core.management.base import BaseCommand

from painel.models import Maquininha, Taxa

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "exemplos"))
from gerar_exemplos import TAXAS  # noqa: E402


class Command(BaseCommand):
    help = "Cadastra as maquininhas e as taxas contratadas do mês de exemplo."

    def handle(self, *args, **opcoes):
        for nome, faixas in TAXAS.items():
            maquininha, _ = Maquininha.objects.get_or_create(nome=nome)
            for faixa, percentual in faixas.items():
                Taxa.objects.update_or_create(maquininha=maquininha, faixa=faixa, defaults={"percentual": percentual})
        self.stdout.write(self.style.SUCCESS(f"{len(TAXAS)} maquininhas e as taxas contratadas cadastradas."))
