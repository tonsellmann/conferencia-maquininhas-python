from io import StringIO
from pathlib import Path

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import Conferencia, Maquininha, Taxa, tabela_de_taxas

EXEMPLO = Path(__file__).resolve().parent.parent / "exemplos" / "outubro-2026"


def arquivos_do_exemplo():
    return [SimpleUploadedFile(p.name, p.read_bytes(), content_type="text/csv") for p in sorted(EXEMPLO.glob("*.csv"))]


class PainelTest(TestCase):
    def setUp(self):
        call_command("carregar_exemplo", stdout=StringIO())
        self.dona = User.objects.create_user("dona", password="senha-de-teste")

    def entrar(self):
        self.client.force_login(self.dona)

    def test_sem_login_vai_para_a_entrada(self):
        resposta = self.client.get(reverse("painel:lista"))
        self.assertEqual(resposta.status_code, 302)
        self.assertIn("/admin/login/", resposta["Location"])

    def test_as_taxas_cadastradas_viram_a_tabela_da_conferencia(self):
        tabela = tabela_de_taxas()
        self.assertEqual(tabela["Cartix"]["credito"], "2.49")
        self.assertEqual(set(tabela), {"Cartix", "PagaJá", "Vendemais"})

    def test_conferir_o_mes_guarda_e_mostra_os_alertas(self):
        self.entrar()
        resposta = self.client.post(reverse("painel:nova"), {"arquivos": arquivos_do_exemplo()})
        conferencia = Conferencia.objects.get()
        self.assertRedirects(resposta, reverse("painel:detalhe", args=[conferencia.pk]))
        self.assertEqual(str(conferencia), "Conferência de 01/10 a 31/10/2026")
        self.assertEqual(len(conferencia.arquivos), 5)
        pagina = self.client.get(reverse("painel:detalhe", args=[conferencia.pk])).content.decode()
        self.assertIn("Cartix cobrou 3,29% no crédito à vista; o contratado é 2,49%", pagina)
        self.assertIn("Depósito da PagaJá de 20/10 não caiu: R$ 195,34", pagina)
        self.assertIn("R$ 285,24", pagina)  # previsto e não recebido: 195,34 + 89,90
        lista = self.client.get(reverse("painel:lista")).content.decode()
        self.assertIn("alertas graves", lista)

    def test_taxa_que_volta_ao_contratado_some_dos_alertas(self):
        Taxa.objects.filter(maquininha__nome="Cartix", faixa="credito").update(percentual="3.29")
        self.entrar()
        self.client.post(reverse("painel:nova"), {"arquivos": arquivos_do_exemplo()})
        alertas = Conferencia.objects.get().resultado["alertas"]
        self.assertFalse(any(a["tipo"] == "taxa" for a in alertas))

    def test_recusa_arquivo_que_nao_e_csv_e_arquivo_grande(self):
        self.entrar()
        resposta = self.client.post(reverse("painel:nova"), {"arquivos": [SimpleUploadedFile("extrato.pdf", b"%PDF-1.7")]})
        self.assertEqual(resposta.status_code, 400)
        self.assertContains(resposta, "não é CSV", status_code=400)
        grande = SimpleUploadedFile("grande.csv", b"x" * (5 * 1024 * 1024 + 1))
        self.assertContains(self.client.post(reverse("painel:nova"), {"arquivos": [grande]}), "passa de 5 MB", status_code=400)
        self.assertFalse(Conferencia.objects.exists())

    def test_healthcheck_responde_sem_login(self):
        self.assertJSONEqual(self.client.get(reverse("painel:saude")).content, {"ok": True})

    def test_so_aceita_post_para_conferir(self):
        self.entrar()
        self.assertEqual(self.client.get(reverse("painel:nova")).status_code, 405)

    def test_maquininha_aparece_no_admin_com_as_taxas(self):
        self.dona.is_staff = self.dona.is_superuser = True
        self.dona.save()
        self.entrar()
        resposta = self.client.get(reverse("admin:painel_maquininha_changelist"))
        self.assertContains(resposta, "Crédito à vista: 2.49%")
        self.assertEqual(Maquininha.objects.count(), 3)
