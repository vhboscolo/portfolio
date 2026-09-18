#!/usr/bin/env python3
"""Trava de publicação: termo proibido, link quebrado, imagem sem alt ou medida.

Uso: python3 verificar.py [caminho/proibidos.txt]

A lista de termos mora FORA deste repositório — aqui dentro, ela mesma seria
o vazamento. Sem a lista o script falha: trava que não acha a própria regra
não pode dizer "limpo".
"""
from __future__ import annotations

import os
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
PROIBIDOS_PADRAO = RAIZ.parent / "portfolio-interno" / "proibidos.txt"
EXTENSOES_BINARIAS = frozenset(
    {".webp", ".jpg", ".jpeg", ".png", ".gif", ".ico", ".mp4", ".woff2", ".pdf"}
)
DIRETORIOS_IGNORADOS = frozenset({".git", "__pycache__", ".pytest_cache"})
PREFIXOS_EXTERNOS = ("http://", "https://", "mailto:", "tel:", "data:", "#")


class ErroDeVerificacao(Exception):
    """A verificação não pôde rodar. Nunca é tratada como 'limpo'."""


def ler_proibidos(caminho: Path) -> list[str]:
    if not caminho.is_file():
        raise ErroDeVerificacao(f"lista de termos proibidos não encontrada: {caminho}")
    linhas = (linha.strip() for linha in caminho.read_text(encoding="utf-8").splitlines())
    termos = [linha for linha in linhas if linha and not linha.startswith("#")]
    if not termos:
        raise ErroDeVerificacao(f"lista de termos proibidos está vazia: {caminho}")
    return termos


def _arquivos(raiz: Path):
    for caminho in sorted(raiz.rglob("*")):
        partes = caminho.relative_to(raiz).parts
        if caminho.is_file() and not DIRETORIOS_IGNORADOS.intersection(partes):
            yield caminho


def achar_termos(raiz: Path, termos: list[str]) -> list[str]:
    dobrados = [(termo, termo.casefold()) for termo in termos]
    achados: list[str] = []
    for caminho in _arquivos(raiz):
        relativo = caminho.relative_to(raiz).as_posix()
        nome_dobrado = relativo.casefold()
        achados.extend(
            f"{relativo}: nome de arquivo contém termo proibido '{termo}'"
            for termo, dobrado in dobrados
            if dobrado in nome_dobrado
        )
        if caminho.suffix.lower() in EXTENSOES_BINARIAS:
            continue
        try:
            texto = caminho.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            achados.append(f"{relativo}: não é UTF-8 nem binário conhecido — conferir à mão")
            continue
        for numero, linha in enumerate(texto.splitlines(), start=1):
            linha_dobrada = linha.casefold()
            achados.extend(
                f"{relativo}:{numero}: termo proibido '{termo}'"
                for termo, dobrado in dobrados
                if dobrado in linha_dobrada
            )
    return achados


def achar_no_historico(raiz: Path, termos: list[str]) -> list[str]:
    """Varre mensagens, autores e diffs de todos os commits. O push leva o histórico inteiro."""
    if not (raiz / ".git").exists():
        return []
    processo = subprocess.run(
        ["git", "-C", str(raiz), "log", "--all", "-p", "--format=%H %an <%ae>%n%B"],
        capture_output=True, text=True, errors="replace", check=False,
    )
    if processo.returncode != 0:
        if "does not have any commits" in processo.stderr:
            return []
        raise ErroDeVerificacao(f"git log falhou: {processo.stderr.strip()}")
    historico = processo.stdout.casefold()
    return [
        f"histórico do git: termo proibido '{termo}' (reescreva antes de publicar)"
        for termo in termos
        if termo.casefold() in historico
    ]


class _Coletor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.imagens: list[dict[str, str | None]] = []
        self.referencias: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        atributos = dict(attrs)
        if tag == "img":
            self.imagens.append(atributos)
        for nome in ("href", "src", "poster"):
            valor = atributos.get(nome)
            if valor:
                self.referencias.append(valor)
        for parte in (atributos.get("srcset") or "").split(","):
            if parte.strip():
                self.referencias.append(parte.strip().split()[0])


def _existe(pagina: Path, referencia: str) -> bool:
    limpa = referencia.split("#")[0].split("?")[0]
    if not limpa:
        return True
    alvo = (pagina.parent / limpa).resolve()
    if limpa.endswith("/") or alvo.is_dir():
        alvo = alvo / "index.html"
    return alvo.is_file()


def conferir_html(docs: Path) -> list[str]:
    achados: list[str] = []
    for pagina in sorted(docs.rglob("*.html")):
        relativo = pagina.relative_to(docs).as_posix()
        coletor = _Coletor()
        coletor.feed(pagina.read_text(encoding="utf-8"))
        for imagem in coletor.imagens:
            faltam = [nome for nome in ("alt", "width", "height") if nome not in imagem]
            if faltam:
                achados.append(f"{relativo}: <img src='{imagem.get('src')}'> sem {', '.join(faltam)}")
        achados.extend(
            f"{relativo}: referência quebrada '{referencia}'"
            for referencia in dict.fromkeys(coletor.referencias)
            if not referencia.startswith(PREFIXOS_EXTERNOS) and not _existe(pagina, referencia)
        )
    return achados


def verificar(raiz: Path, caminho_proibidos: Path) -> list[str]:
    termos = ler_proibidos(caminho_proibidos)
    return [
        *achar_termos(raiz, termos),
        *achar_no_historico(raiz, termos),
        *conferir_html(raiz / "docs"),
    ]


def main(argumentos: list[str]) -> int:
    caminho = Path(argumentos[0]) if argumentos else Path(
        os.environ.get("PORTFOLIO_PROIBIDOS", PROIBIDOS_PADRAO)
    )
    try:
        achados = verificar(RAIZ, caminho)
    except ErroDeVerificacao as erro:
        print(f"NÃO VERIFICADO: {erro}", file=sys.stderr)
        return 1
    for achado in achados:
        print(achado)
    print(f"{len(achados)} problema(s)" if achados else "limpo")
    return 1 if achados else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
