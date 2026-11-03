from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from conferencia import conferir

from .forms import EnvioDoMes
from .models import Conferencia, tabela_de_taxas


@login_required
def lista(request):
    return render(request, "painel/lista.html", {"formulario": EnvioDoMes(), "conferencias": Conferencia.objects.all()[:24]})


@login_required
@require_POST
def nova(request):
    formulario = EnvioDoMes(request.POST, request.FILES)
    if not formulario.is_valid():
        return render(request, "painel/lista.html", {"formulario": formulario, "conferencias": Conferencia.objects.all()[:24]}, status=400)
    tabela = tabela_de_taxas()
    if not tabela:
        messages.warning(request, "Nenhuma taxa contratada cadastrada: as taxas não foram conferidas. Cadastre em Maquininhas.")
    arquivos = {a.name: a.read() for a in formulario.cleaned_data["arquivos"]}
    resultado = conferir(arquivos, tabela)
    periodo = resultado.get("periodo") or {}
    conferencia = Conferencia.objects.create(
        criada_por=request.user,
        periodo_de=date.fromisoformat(periodo["de"]) if periodo else None,
        periodo_ate=date.fromisoformat(periodo["ate"]) if periodo else None,
        arquivos=sorted(arquivos),
        resultado=resultado,
    )
    return redirect("painel:detalhe", conferencia.pk)


@login_required
def detalhe(request, pk):
    conferencia = get_object_or_404(Conferencia, pk=pk)
    return render(request, "painel/detalhe.html", {"conferencia": conferencia, "r": conferencia.resultado})
