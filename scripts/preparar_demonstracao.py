"""Gera a demonstração do portfólio: a página, o CSS do painel, o pacote conferencia/ (que roda
no navegador pelo Pyodide) e os arquivos do mês de exemplo.

    python scripts/preparar_demonstracao.py ../Portfolio/public/demos/conferencia-maquininhas
"""

import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Uso: python scripts/preparar_demonstracao.py <pasta de destino>")
    destino = Path(sys.argv[1]).resolve()
    if destino.exists():
        shutil.rmtree(destino)
    (destino / "conferencia").mkdir(parents=True)
    for modulo in sorted((RAIZ / "conferencia").glob("*.py")):
        shutil.copy2(modulo, destino / "conferencia" / modulo.name)
    shutil.copytree(RAIZ / "exemplos" / "outubro-2026", destino / "exemplos")
    shutil.copy2(RAIZ / "painel" / "static" / "painel" / "painel.css", destino / "painel.css")
    for arquivo in ("index.html", "demo.js"):
        shutil.copy2(RAIZ / "demo" / arquivo, destino / arquivo)
    print(f"Demonstração em {destino}")


if __name__ == "__main__":
    main()
