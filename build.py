#!/usr/bin/env python3
"""Gera README.md e o site em docs/ a partir de conteudo/*.toml.

Uma fonte de texto, duas saídas. Só biblioteca padrão.
Uso: python3 build.py
"""
from __future__ import annotations

import html
import re
import struct
import sys
import tomllib
from pathlib import Path
from string import Template
from urllib.parse import quote

RAIZ = Path(__file__).resolve().parent

CAMPOS_SITE = (
    "assinatura", "subtitulo", "autor", "promessa", "intro", "quem_faz", "cta_rotulo",
    "descricao", "base_url", "fontes_css", "og_imagem", "ordem", "contato",
    "numeros", "diferenciais",
)
CAMPOS_CONTATO = (
    "whatsapp", "whatsapp_exibir", "whatsapp_texto", "email", "site", "instagram", "linkedin",
)
CAMPOS_SISTEMA = (
    "titulo", "chamada", "setor", "status", "resumo", "ganho", "capa", "capa_alt",
    "problema", "faz", "provas", "stack", "telas",
)
CAMPOS_TELA = ("arquivo", "alt", "legenda")
CAMPOS_PROVA = ("numero", "rotulo")
CAMPOS_DECISAO = ("titulo", "texto")
CAMPOS_VIDEO = ("arquivo", "poster", "legenda")
CAMPOS_NOTA = ("titulo", "texto")
CAMPOS_REEL = ("arquivo", "poster", "alt")

ROTULO_DEMO = "dados de demonstração"
SIZES_CARTAO = "(min-width: 900px) 50vw, 100vw"
SIZES_TELA = "(min-width: 1100px) 1000px, 100vw"
AVISO_README = "<!-- Gerado por build.py a partir de conteudo/. Não edite à mão. -->"


class ErroDeConteudo(Exception):
    """Conteúdo inválido. A mensagem nomeia o arquivo e o campo."""


# ── carga e validação ────────────────────────────────────────────────────────

def exigir(dados: dict, campos: tuple[str, ...], origem: str) -> None:
    for campo in campos:
        if dados.get(campo) in (None, "", [], {}):
            raise ErroDeConteudo(f"{origem}: campo obrigatório ausente ou vazio: '{campo}'")


def ler_toml(caminho: Path) -> dict:
    try:
        with caminho.open("rb") as arquivo:
            return tomllib.load(arquivo)
    except FileNotFoundError as erro:
        raise ErroDeConteudo(f"{caminho.name}: arquivo não encontrado em conteudo/") from erro
    except tomllib.TOMLDecodeError as erro:
        raise ErroDeConteudo(f"{caminho.name}: TOML inválido — {erro}") from erro


def carregar(raiz: Path) -> tuple[dict, list[dict]]:
    conteudo = raiz / "conteudo"
    site = ler_toml(conteudo / "site.toml")
    exigir(site, CAMPOS_SITE, "site.toml")
    exigir(site["contato"], CAMPOS_CONTATO, "site.toml [contato]")
    for numero, item in enumerate(site["numeros"], start=1):
        exigir(item, CAMPOS_PROVA, f"site.toml [[numeros]] nº {numero}")
    for numero, item in enumerate(site["diferenciais"], start=1):
        exigir(item, CAMPOS_DECISAO, f"site.toml [[diferenciais]] nº {numero}")
    if "reel" in site:
        exigir(site["reel"], CAMPOS_REEL, "site.toml [reel]")
    for numero, nota in enumerate(site.get("notas", []), start=1):
        exigir(nota, CAMPOS_NOTA, f"site.toml [[notas]] nº {numero}")
    sistemas = []
    for slug in site["ordem"]:
        origem = f"{slug}.toml"
        dados = ler_toml(conteudo / origem)
        exigir(dados, CAMPOS_SISTEMA, origem)
        for numero, tela in enumerate(dados["telas"], start=1):
            exigir(tela, CAMPOS_TELA, f"{origem} [[telas]] nº {numero}")
        for numero, prova in enumerate(dados["provas"], start=1):
            exigir(prova, CAMPOS_PROVA, f"{origem} [[provas]] nº {numero}")
        for numero, decisao in enumerate(dados.get("decisoes", []), start=1):
            exigir(decisao, CAMPOS_DECISAO, f"{origem} [[decisoes]] nº {numero}")
        if "video" in dados:
            exigir(dados["video"], CAMPOS_VIDEO, f"{origem} [video]")
        sistemas.append({**dados, "slug": slug})
    return site, sistemas


# ── imagem ───────────────────────────────────────────────────────────────────

def dimensoes_webp(caminho: Path) -> tuple[int, int]:
    with caminho.open("rb") as arquivo:
        cabecalho = arquivo.read(30)
    if len(cabecalho) < 30 or cabecalho[:4] != b"RIFF" or cabecalho[8:12] != b"WEBP":
        raise ErroDeConteudo(f"{caminho.name}: não é um WebP válido")
    formato = cabecalho[12:16]
    if formato == b"VP8 ":
        largura, altura = struct.unpack("<HH", cabecalho[26:30])
        return largura & 0x3FFF, altura & 0x3FFF
    if formato == b"VP8L":
        bits = int.from_bytes(cabecalho[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if formato == b"VP8X":
        return (int.from_bytes(cabecalho[24:27], "little") + 1,
                int.from_bytes(cabecalho[27:30], "little") + 1)
    raise ErroDeConteudo(f"{caminho.name}: variante de WebP desconhecida {formato!r}")


def dimensoes_svg(caminho: Path) -> tuple[int, int]:
    achado = re.search(r'viewBox="\s*[\d.]+\s+[\d.]+\s+([\d.]+)\s+([\d.]+)\s*"',
                       caminho.read_text(encoding="utf-8"))
    if not achado:
        raise ErroDeConteudo(f"{caminho.name}: SVG sem viewBox — sem ele não há medida")
    return round(float(achado.group(1))), round(float(achado.group(2)))


def fontes_da_imagem(docs: Path, base: str, origem: str) -> list[tuple[str, int, int]]:
    """[(caminho relativo a docs/, largura, altura)], da menor para a maior."""
    achadas = [
        (base + sufixo, *dimensoes_webp(docs / (base + sufixo)))
        for sufixo in ("-p.webp", "-g.webp")
        if (docs / (base + sufixo)).is_file()
    ]
    if not achadas:
        raise ErroDeConteudo(
            f"{origem}: imagem '{base}' não existe em docs/ (esperado {base}-g.webp)")
    return achadas


def e(texto: object) -> str:
    return html.escape(str(texto), quote=True)


def tag_img(docs: Path, base: str, alt: str, prefixo: str, origem: str, *,
            sizes: str, prioridade: bool = False) -> str:
    carga = 'fetchpriority="high"' if prioridade else 'loading="lazy"'
    if base.endswith(".svg"):
        if not (docs / base).is_file():
            raise ErroDeConteudo(f"{origem}: imagem '{base}' não existe em docs/")
        largura, altura = dimensoes_svg(docs / base)
        return (f'<img src="{e(prefixo + base)}" alt="{e(alt)}" width="{largura}" '
                f'height="{altura}" {carga} decoding="async">')
    fontes = fontes_da_imagem(docs, base, origem)
    maior, largura, altura = fontes[-1]
    srcset = ", ".join(f"{e(prefixo + caminho)} {larg}w" for caminho, larg, _ in fontes)
    return (f'<img src="{e(prefixo + maior)}" srcset="{srcset}" sizes="{e(sizes)}" '
            f'alt="{e(alt)}" width="{largura}" height="{altura}" {carga} decoding="async">')


# ── fragmentos de HTML ───────────────────────────────────────────────────────

def paragrafos(texto: str) -> str:
    blocos = (bloco.strip() for bloco in re.split(r"\n\s*\n", texto.strip()))
    return "\n".join(f"<p>{e(' '.join(bloco.split()))}</p>" for bloco in blocos if bloco)


def link_whatsapp(contato: dict, texto: str) -> str:
    return f'https://wa.me/{contato["whatsapp"]}?text={quote(texto, safe="")}'


def html_botao(site: dict, texto: str, classe: str) -> str:
    return (f'<a class="botao {classe}" href="{e(link_whatsapp(site["contato"], texto))}" '
            f'rel="noopener">{e(site["cta_rotulo"])}</a>')


def html_reel(docs: Path, site: dict) -> str:
    reel = site.get("reel")
    if not reel:
        return ""
    if not (docs / reel["arquivo"]).is_file():
        raise ErroDeConteudo(f"site.toml [reel]: vídeo '{reel['arquivo']}' não existe em docs/")
    poster, largura, altura = fontes_da_imagem(docs, reel["poster"], "site.toml [reel]")[-1]
    return (f'<video class="reel" autoplay muted loop playsinline preload="metadata" '
            f'poster="{e(poster)}" width="{largura}" height="{altura}" aria-label="{e(reel["alt"])}">'
            f'<source src="{e(reel["arquivo"])}" type="video/mp4"></video>')


def html_numeros(numeros: list[dict]) -> str:
    itens = "\n".join(f'<div class="numero"><dt>{e(n["numero"])}</dt><dd>{e(n["rotulo"])}</dd></div>'
                      for n in numeros)
    return f'<dl class="numeros">\n{itens}\n</dl>'


def html_diferenciais(diferenciais: list[dict]) -> str:
    return "\n".join(f'<article class="diferencial"><h3>{e(d["titulo"])}</h3>{paragrafos(d["texto"])}</article>'
                     for d in diferenciais)


def links_de_contato(contato: dict) -> list[tuple[str, str]]:
    return [
        (f'WhatsApp {contato["whatsapp_exibir"]}', link_whatsapp(contato, contato["whatsapp_texto"])),
        (contato["email"], f'mailto:{contato["email"]}'),
        (contato["site"].removeprefix("https://"), contato["site"]),
        (f'Instagram @{contato["instagram"]}', f'https://www.instagram.com/{contato["instagram"]}/'),
        (f'LinkedIn /in/{contato["linkedin"]}', f'https://www.linkedin.com/in/{contato["linkedin"]}/'),
    ]


def html_contato(contato: dict) -> str:
    itens = "\n".join(f'<li><a href="{e(url)}" rel="noopener">{e(rotulo)}</a></li>'
                      for rotulo, url in links_de_contato(contato))
    return f'<ul class="contato">\n{itens}\n</ul>'


def html_cartoes(docs: Path, sistemas: list[dict]) -> str:
    cartoes = []
    for numero, sistema in enumerate(sistemas, start=1):
        imagem = tag_img(docs, sistema["capa"], sistema["capa_alt"], "", f'{sistema["slug"]}.toml',
                         sizes=SIZES_CARTAO, prioridade=numero == 1)
        cartoes.append(
            f'<article class="cartao">\n'
            f'  <p class="indice" aria-hidden="true">{numero:02d}</p>\n'
            f'  <div class="cartao-imagem">{imagem}</div>\n'
            f'  <h2><a href="{e(sistema["slug"])}/">{e(sistema["titulo"])}</a></h2>\n'
            f'  <p class="chamada">{e(sistema["chamada"])}</p>\n'
            f'  <p class="resumo">{e(sistema["resumo"])}</p>\n'
            f'  <p class="meta"><span>{e(sistema["setor"])}</span> '
            f'<span class="status">{e(sistema["status"])}</span></p>\n'
            f'</article>')
    return "\n".join(cartoes)


def html_notas(docs: Path, notas: list[dict]) -> str:
    if not notas:
        return ""
    blocos = []
    for nota in notas:
        imagem = ""
        if nota.get("imagem"):
            imagem = tag_img(docs, nota["imagem"], nota.get("imagem_alt", ""), "", "site.toml [[notas]]",
                             sizes=SIZES_CARTAO)
        blocos.append(f'<article class="nota">{imagem}<h3>{e(nota["titulo"])}</h3>'
                      f'{paragrafos(nota["texto"])}</article>')
    return ('<section class="notas" aria-labelledby="t-notas">\n<h2 id="t-notas">Também fizemos</h2>\n'
            + "\n".join(blocos) + "\n</section>")


def html_telas(docs: Path, sistema: dict, prefixo: str) -> str:
    origem = f'{sistema["slug"]}.toml'
    figuras = []
    for tela in sistema["telas"]:
        imagem = tag_img(docs, tela["arquivo"], tela["alt"], prefixo, origem, sizes=SIZES_TELA)
        selo = f' <span class="selo-demo">{ROTULO_DEMO}</span>' if tela.get("demo", True) else ""
        figuras.append(f'<figure class="tela">{imagem}'
                       f'<figcaption>{e(tela["legenda"])}{selo}</figcaption></figure>')
    return "\n".join(figuras)


def html_video(docs: Path, sistema: dict, prefixo: str) -> str:
    video = sistema.get("video")
    if not video:
        return ""
    origem = f'{sistema["slug"]}.toml [video]'
    if not (docs / video["arquivo"]).is_file():
        raise ErroDeConteudo(f"{origem}: vídeo '{video['arquivo']}' não existe em docs/")
    poster, largura, altura = fontes_da_imagem(docs, video["poster"], origem)[-1]
    return (f'<figure class="video"><video controls preload="none" playsinline '
            f'poster="{e(prefixo + poster)}" width="{largura}" height="{altura}">'
            f'<source src="{e(prefixo + video["arquivo"])}" type="video/mp4"></video>'
            f'<figcaption>{e(video["legenda"])}</figcaption></figure>')


def html_provas(sistema: dict) -> str:
    itens = "\n".join(f'<div class="prova"><dt>{e(p["numero"])}</dt><dd>{e(p["rotulo"])}</dd></div>'
                      for p in sistema["provas"])
    return f'<dl class="provas">\n{itens}\n</dl>'


def html_decisoes(sistema: dict) -> str:
    return "\n".join(f'<div class="decisao"><h3>{e(d["titulo"])}</h3>{paragrafos(d["texto"])}</div>'
                     for d in sistema.get("decisoes", []))


def html_vizinhos(sistemas: list[dict], posicao: int) -> str:
    links = []
    if posicao > 0:
        anterior = sistemas[posicao - 1]
        links.append(f'<a class="vizinho anterior" href="../{e(anterior["slug"])}/">'
                     f'<span>Anterior</span> {e(anterior["titulo"])}</a>')
    if posicao < len(sistemas) - 1:
        proximo = sistemas[posicao + 1]
        links.append(f'<a class="vizinho proximo" href="../{e(proximo["slug"])}/">'
                     f'<span>Próximo</span> {e(proximo["titulo"])}</a>')
    return '<nav class="vizinhos" aria-label="Outros sistemas">' + "".join(links) + "</nav>"


# ── páginas ──────────────────────────────────────────────────────────────────

def modelo(raiz: Path, nome: str) -> Template:
    return Template((raiz / "modelos" / nome).read_text(encoding="utf-8"))


def envelopar(raiz: Path, site: dict, *, titulo: str, descricao: str, caminho: str,
              og: str, prefixo: str, corpo: str, texto_cta: str) -> str:
    if not (raiz / "docs" / og).is_file():
        raise ErroDeConteudo(f"imagem de compartilhamento '{og}' não existe em docs/")
    return modelo(raiz, "base.html").substitute(
        titulo=e(titulo), descricao=e(descricao),
        canonica=e(site["base_url"] + caminho), og_imagem=e(site["base_url"] + og),
        fontes_css=e(site["fontes_css"]), raiz=prefixo,
        assinatura=e(site["assinatura"]), subtitulo=e(site["subtitulo"]), autor=e(site["autor"]),
        corpo=corpo, contato=html_contato(site["contato"]),
        cta=html_botao(site, texto_cta, "botao-topo"),
    )


def pagina_home(raiz: Path, site: dict, sistemas: list[dict]) -> str:
    docs = raiz / "docs"
    texto_padrao = site["contato"]["whatsapp_texto"]
    corpo = modelo(raiz, "home.html").substitute(
        promessa=e(site["promessa"]), intro=paragrafos(site["intro"]),
        reel=html_reel(docs, site), numeros=html_numeros(site["numeros"]),
        diferenciais=html_diferenciais(site["diferenciais"]), quem_faz=paragrafos(site["quem_faz"]),
        autor=e(site["autor"]),
        cta_heroi=html_botao(site, texto_padrao, "botao-heroi"),
        cta_final=html_botao(site, texto_padrao, "botao-final"),
        cartoes=html_cartoes(docs, sistemas), notas=html_notas(docs, site.get("notas", [])),
    )
    return envelopar(raiz, site, titulo=f'{site["assinatura"]} — {site["subtitulo"]}',
                     descricao=site["descricao"], caminho="", og=site["og_imagem"],
                     prefixo="", corpo=corpo, texto_cta=texto_padrao)


def pagina_sistema(raiz: Path, site: dict, sistemas: list[dict], posicao: int) -> str:
    docs = raiz / "docs"
    sistema = sistemas[posicao]
    origem = f'{sistema["slug"]}.toml'
    texto_cta = f'Oi, {site["autor"].split()[0]}. Vi o {sistema["titulo"]} no portfólio e quero um sistema assim.'
    link = ""
    if sistema.get("link"):
        link = (f'<p class="link-publico"><a href="{e(sistema["link"])}" rel="noopener">'
                f'{e(sistema.get("link_rotulo") or sistema["link"])}</a></p>')
    corpo = modelo(raiz, "sistema.html").substitute(
        indice=f"{posicao + 1:02d}", titulo=e(sistema["titulo"]), chamada=e(sistema["chamada"]),
        setor=e(sistema["setor"]), status=e(sistema["status"]),
        ganho=paragrafos(sistema["ganho"]), cta_sistema=html_botao(site, texto_cta, "botao-final"),
        capa=tag_img(docs, sistema["capa"], sistema["capa_alt"], "../", origem,
                     sizes=SIZES_TELA, prioridade=True),
        problema=paragrafos(sistema["problema"]),
        faz="<ul class=\"faz\">\n" + "\n".join(f"<li>{e(item)}</li>" for item in sistema["faz"]) + "\n</ul>",
        telas=html_telas(docs, sistema, "../"), video=html_video(docs, sistema, "../"),
        provas=html_provas(sistema), decisoes=html_decisoes(sistema),
        stack=e(sistema["stack"]), link=link, vizinhos=html_vizinhos(sistemas, posicao),
    )
    return envelopar(raiz, site, titulo=f'{sistema["titulo"]} — {site["assinatura"]}',
                     descricao=sistema["resumo"], caminho=f'{sistema["slug"]}/',
                     og=sistema.get("og", site["og_imagem"]), prefixo="../", corpo=corpo,
                     texto_cta=texto_cta)


def readme(raiz: Path, site: dict, sistemas: list[dict]) -> str:
    docs = raiz / "docs"
    linhas = [AVISO_README, "", f'# {site["assinatura"]} — {site["subtitulo"]}', "",
              " ".join(site["intro"].split()), "",
              f'**[Abrir o portfólio completo →]({site["base_url"]})**', ""]
    for numero, sistema in enumerate(sistemas, start=1):
        url = f'{site["base_url"]}{sistema["slug"]}/'
        imagem = fontes_da_imagem(docs, sistema["capa"], f'{sistema["slug"]}.toml')[0][0]
        linhas += ["---", "", f'## {numero:02d} · {sistema["titulo"]}', "",
                   f'**{sistema["chamada"]}**', "",
                   f'[![{sistema["capa_alt"]}](docs/{imagem})]({url})', "",
                   " ".join(sistema["resumo"].split()), "",
                   f'`{sistema["setor"]}` · `{sistema["status"]}` — [ver telas e engenharia →]({url})', ""]
    linhas += ["---", "", "## Contato", ""]
    linhas += [f"- [{rotulo}]({url})" for rotulo, url in links_de_contato(site["contato"])]
    linhas += ["", f'{site["assinatura"]} · {site["autor"]}. As telas usam dados de demonstração. '
                   "O código dos sistemas não está neste repositório.", ""]
    return "\n".join(linhas)


def construir(raiz: Path) -> list[Path]:
    site, sistemas = carregar(raiz)
    saidas = {
        raiz / "docs/index.html": pagina_home(raiz, site, sistemas),
        raiz / "README.md": readme(raiz, site, sistemas),
        **{raiz / "docs" / sistema["slug"] / "index.html": pagina_sistema(raiz, site, sistemas, posicao)
           for posicao, sistema in enumerate(sistemas)},
    }
    for caminho, texto in saidas.items():
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(texto, encoding="utf-8")
    return list(saidas)


def main() -> int:
    try:
        escritos = construir(RAIZ)
    except ErroDeConteudo as erro:
        print(f"ERRO DE CONTEÚDO: {erro}", file=sys.stderr)
        return 1
    print(f"{len(escritos)} arquivos gerados")
    return 0


if __name__ == "__main__":
    sys.exit(main())
