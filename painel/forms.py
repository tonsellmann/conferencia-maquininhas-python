from django import forms

LIMITE_DE_ARQUIVOS = 10
LIMITE_POR_ARQUIVO = 5 * 1024 * 1024


class VariosArquivos(forms.ClearableFileInput):
    allow_multiple_selected = True


class CampoDeVariosArquivos(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", VariosArquivos(attrs={"accept": ".csv,text/csv"}))
        super().__init__(*args, **kwargs)

    def clean(self, dados, inicial=None):
        lista = dados if isinstance(dados, (list, tuple)) else [dados]
        return [super(CampoDeVariosArquivos, self).clean(d, inicial) for d in lista if d]


class EnvioDoMes(forms.Form):
    arquivos = CampoDeVariosArquivos(
        label="Arquivos do mês",
        help_text="Os extratos das maquininhas, o relatório de vendas do caixa e o extrato do banco, em CSV.",
    )

    def clean_arquivos(self):
        arquivos = self.cleaned_data["arquivos"]
        if not arquivos:
            raise forms.ValidationError("Escolha os arquivos do mês.")
        if len(arquivos) > LIMITE_DE_ARQUIVOS:
            raise forms.ValidationError(f"Mande até {LIMITE_DE_ARQUIVOS} arquivos por vez.")
        for arquivo in arquivos:
            if arquivo.size > LIMITE_POR_ARQUIVO:
                raise forms.ValidationError(f"{arquivo.name} passa de 5 MB: não parece um extrato do mês.")
            if not arquivo.name.lower().endswith(".csv"):
                raise forms.ValidationError(f"{arquivo.name} não é CSV. Exporte o extrato em CSV.")
        return arquivos
