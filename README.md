# Conferência das maquininhas

Confere, todo mês, as vendas do caixa contra os extratos das maquininhas de cartão e o extrato do banco. Acha a taxa cobrada acima da contratada, o depósito que não caiu ou veio a menos, a venda sem transação, a transação sem venda, os estornos e as contestações.

**Projeto conceito.** A Padaria Bom Dia e as maquininhas Cartix, PagaJá e Vendemais são fictícias. Os formatos de extrato imitam o que se vê de verdade: latin-1, vírgula decimal, uma linha por parcela.

## Como funciona

- `conferencia/`: o núcleo em Python e pandas. Lê os três formatos e casa cada venda com a sua transação (mesma maquininha, valor e forma, pelo horário mais próximo). Confere a taxa venda por venda e descobre o percentual que a maquininha está aplicando de fato. Confere os depósitos em três passadas, para um depósito que faltou não "roubar" o do dia seguinte.
- `painel/`: o painel em Django. A loja cadastra as taxas contratadas no admin, manda os arquivos do mês e guarda o histórico das conferências.
- `demo/`: o mesmo pacote rodando no navegador pelo Pyodide (Python 3.14 e pandas).
- `exemplos/gerar_exemplos.py`: o mês de exemplo, com os problemas plantados.

## Por que Python

O trabalho é ler planilhas tortas e cruzar tabelas, e o pandas faz isso em poucas linhas. O mesmo código roda no servidor (Django) e no navegador (Pyodide).

## Rodar

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
python exemplos/gerar_exemplos.py
python -m pytest -q
python manage.py test painel
python manage.py migrate && python manage.py carregar_exemplo && python manage.py runserver
```

Os testes são 24 do núcleo (pytest) e 7 do painel (Django).
