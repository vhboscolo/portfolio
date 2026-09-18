"""O gerador não engole campo faltando, não deixa HTML do TOML passar cru e mede imagem sozinho."""
import shutil
import tempfile
import unittest
from pathlib import Path

import build

RAIZ = Path(__file__).resolve().parent


def webp_vp8x(largura: int, altura: int) -> bytes:
    return (b"RIFF" + (22).to_bytes(4, "little") + b"WEBPVP8X" + (10).to_bytes(4, "little")
            + bytes(4) + (largura - 1).to_bytes(3, "little") + (altura - 1).to_bytes(3, "little"))


SITE = '''
assinatura = "MARCA"
subtitulo = "Sistemas"
autor = "Pessoa"
titulo_home = "Título da home"
intro = "Intro."
descricao = "Descrição."
base_url = "https://exemplo.com/p/"
fontes_css = "https://fonts.googleapis.com/css2?family=X"
og_imagem = "img/og.jpg"
ordem = ["alfa", "beta"]
promessa = "Promessa da home"
quem_faz = "Eu construo."
cta_rotulo = "Chamar no WhatsApp"
[[numeros]]
numero = "8"
rotulo = "sistemas"
[[diferenciais]]
titulo = "Direto com quem faz"
texto = "Sem intermediário."
[reel]
arquivo = "video/reel.mp4"
poster = "img/alfa/capa"
alt = "Telas dos sistemas"
[contato]
whatsapp = "5500000000000"
whatsapp_exibir = "(00) 00000-0000"
whatsapp_texto = "Oi, vi o portfólio"
email = "a@exemplo.com"
site = "https://exemplo.com"
instagram = "marca"
linkedin = "marca"
'''

SISTEMA = '''
titulo = "{titulo}"
chamada = "Chamada"
setor = "Setor"
status = "Em produção"
resumo = "Resumo."
ganho = "O que muda no negócio."
capa = "img/{slug}/capa"
capa_alt = "Capa"
problema = """Primeiro parágrafo.

Segundo parágrafo."""
faz = ["Faz uma coisa", "Faz outra"]
stack = "Python"
[[provas]]
numero = "10"
rotulo = "testes"
[[telas]]
arquivo = "img/{slug}/capa"
alt = "Tela"
legenda = "Legenda"
'''


def montar(titulo_alfa: str = "Alfa") -> Path:
    raiz = Path(tempfile.mkdtemp())
    shutil.copytree(RAIZ / "modelos", raiz / "modelos")
    (raiz / "conteudo").mkdir()
    (raiz / "conteudo/site.toml").write_text(SITE, encoding="utf-8")
    for slug, titulo in (("alfa", titulo_alfa), ("beta", "Beta")):
        (raiz / f"conteudo/{slug}.toml").write_text(
            SISTEMA.format(titulo=titulo, slug=slug), encoding="utf-8")
        (raiz / f"docs/img/{slug}").mkdir(parents=True)
        (raiz / f"docs/img/{slug}/capa-g.webp").write_bytes(webp_vp8x(1600, 900))
    (raiz / "docs/img/og.jpg").write_bytes(b"")
    (raiz / "docs/video").mkdir()
    (raiz / "docs/video/reel.mp4").write_bytes(b"")
    return raiz


class TesteConstruir(unittest.TestCase):
    def test_gera_home_paginas_e_readme(self):
        raiz = montar()
        build.construir(raiz)
        home = (raiz / "docs/index.html").read_text(encoding="utf-8")
        self.assertIn('href="alfa/"', home)
        self.assertIn('href="beta/"', home)
        pagina = (raiz / "docs/alfa/index.html").read_text(encoding="utf-8")
        self.assertIn("<p>Primeiro parágrafo.</p>", pagina)
        self.assertIn("<p>Segundo parágrafo.</p>", pagina)
        self.assertIn('width="1600" height="900"', pagina)
        self.assertIn('href="../css/', pagina)
        readme = (raiz / "README.md").read_text(encoding="utf-8")
        self.assertIn("## 01 · Alfa", readme)
        self.assertIn("https://exemplo.com/p/beta/", readme)

    def test_campo_ausente_nomeia_arquivo_e_campo(self):
        raiz = montar()
        caminho = raiz / "conteudo/beta.toml"
        caminho.write_text(caminho.read_text(encoding="utf-8").replace('stack = "Python"\n', ""),
                           encoding="utf-8")
        with self.assertRaises(build.ErroDeConteudo) as contexto:
            build.construir(raiz)
        self.assertIn("beta.toml", str(contexto.exception))
        self.assertIn("stack", str(contexto.exception))

    def test_texto_do_toml_sai_escapado(self):
        raiz = montar(titulo_alfa="<script>alert(1)</script>")
        build.construir(raiz)
        pagina = (raiz / "docs/alfa/index.html").read_text(encoding="utf-8")
        self.assertNotIn("<script>alert(1)</script>", pagina)
        self.assertIn("&lt;script&gt;", pagina)

    def test_slug_sem_arquivo_falha(self):
        raiz = montar()
        (raiz / "conteudo/beta.toml").unlink()
        with self.assertRaises(build.ErroDeConteudo) as contexto:
            build.construir(raiz)
        self.assertIn("beta.toml", str(contexto.exception))

    def test_imagem_inexistente_falha(self):
        raiz = montar()
        (raiz / "docs/img/alfa/capa-g.webp").unlink()
        with self.assertRaises(build.ErroDeConteudo) as contexto:
            build.construir(raiz)
        self.assertIn("img/alfa/capa", str(contexto.exception))

    def test_tela_leva_selo_de_demonstracao_por_padrao(self):
        raiz = montar()
        build.construir(raiz)
        pagina = (raiz / "docs/alfa/index.html").read_text(encoding="utf-8")
        self.assertIn(build.ROTULO_DEMO, pagina)

    def test_duas_larguras_viram_srcset_com_a_medida_real(self):
        raiz = montar()
        (raiz / "docs/img/alfa/capa-p.webp").write_bytes(webp_vp8x(800, 450))
        build.construir(raiz)
        pagina = (raiz / "docs/alfa/index.html").read_text(encoding="utf-8")
        self.assertIn("capa-p.webp 800w", pagina)
        self.assertIn("capa-g.webp 1600w", pagina)


class TesteCamadaDeVenda(unittest.TestCase):
    def test_home_abre_com_promessa_numeros_diferenciais_e_quem_faz(self):
        raiz = montar()
        build.construir(raiz)
        home = (raiz / "docs/index.html").read_text(encoding="utf-8")
        for trecho in ("Promessa da home", "<dt>8</dt>", "Direto com quem faz", "Eu construo."):
            self.assertIn(trecho, home)

    def test_reel_toca_sozinho_mudo_em_loop_e_tem_poster(self):
        raiz = montar()
        build.construir(raiz)
        home = (raiz / "docs/index.html").read_text(encoding="utf-8")
        self.assertIn("autoplay muted loop playsinline", home)
        self.assertIn('poster="img/alfa/capa-g.webp"', home)
        self.assertIn('aria-label="Telas dos sistemas"', home)

    def test_reel_e_opcional_mas_arquivo_citado_tem_de_existir(self):
        raiz = montar()
        (raiz / "docs/video/reel.mp4").unlink()
        with self.assertRaises(build.ErroDeConteudo) as contexto:
            build.construir(raiz)
        self.assertIn("video/reel.mp4", str(contexto.exception))

    def test_numero_sem_rotulo_derruba_o_build_nomeando_o_campo(self):
        raiz = montar()
        caminho = raiz / "conteudo/site.toml"
        caminho.write_text(caminho.read_text(encoding="utf-8").replace('rotulo = "sistemas"\n', ""),
                           encoding="utf-8")
        with self.assertRaises(build.ErroDeConteudo) as contexto:
            build.construir(raiz)
        self.assertIn("numeros", str(contexto.exception))
        self.assertIn("rotulo", str(contexto.exception))

    def test_pagina_abre_pelo_ganho_e_fecha_com_chamada_que_cita_o_sistema(self):
        raiz = montar(titulo_alfa="Sistema & Cia")
        build.construir(raiz)
        pagina = (raiz / "docs/alfa/index.html").read_text(encoding="utf-8")
        self.assertIn("O que muda no negócio.", pagina)
        self.assertLess(pagina.index("O que muda no negócio."), pagina.index("Primeiro parágrafo."))
        self.assertIn("wa.me/5500000000000?text=", pagina)
        self.assertIn("Sistema%20%26%20Cia", pagina)

    def test_topo_de_toda_pagina_tem_botao_de_whatsapp(self):
        raiz = montar()
        build.construir(raiz)
        for nome in ("docs/index.html", "docs/beta/index.html"):
            pagina = (raiz / nome).read_text(encoding="utf-8")
            self.assertIn('class="botao botao-topo"', pagina)
            self.assertIn("Chamar no WhatsApp", pagina)


class TesteContatoECapaVetorial(unittest.TestCase):
    def test_site_proprio_e_opcional_no_contato(self):
        raiz = montar()
        caminho = raiz / "conteudo/site.toml"
        caminho.write_text(caminho.read_text(encoding="utf-8").replace('site = "https://exemplo.com"\n', ""),
                           encoding="utf-8")
        build.construir(raiz)
        home = (raiz / "docs/index.html").read_text(encoding="utf-8")
        self.assertNotIn('href="https://exemplo.com"', home)
        self.assertIn("mailto:a@exemplo.com", home)

    def test_capa_em_svg_entra_no_site_e_no_readme(self):
        raiz = montar()
        (raiz / "docs/img/beta/diagrama.svg").write_text('<svg viewBox="0 0 1200 700"></svg>', encoding="utf-8")
        caminho = raiz / "conteudo/beta.toml"
        caminho.write_text(caminho.read_text(encoding="utf-8").replace(
            'capa = "img/beta/capa"', 'capa = "img/beta/diagrama.svg"'), encoding="utf-8")
        build.construir(raiz)
        self.assertIn('src="img/beta/diagrama.svg"', (raiz / "docs/index.html").read_text(encoding="utf-8"))
        self.assertIn("(docs/img/beta/diagrama.svg)", (raiz / "README.md").read_text(encoding="utf-8"))


class TesteDimensoes(unittest.TestCase):
    def escrever(self, dados: bytes) -> Path:
        caminho = Path(tempfile.mkdtemp()) / "x.webp"
        caminho.write_bytes(dados)
        return caminho

    def test_vp8x(self):
        self.assertEqual(build.dimensoes_webp(self.escrever(webp_vp8x(1457, 812))), (1457, 812))

    def test_vp8_com_perda(self):
        dados = (b"RIFF" + bytes(4) + b"WEBPVP8 " + bytes(4) + bytes(3) + b"\x9d\x01\x2a"
                 + (1600).to_bytes(2, "little") + (900).to_bytes(2, "little"))
        self.assertEqual(build.dimensoes_webp(self.escrever(dados)), (1600, 900))

    def test_vp8l_sem_perda(self):
        bits = (1600 - 1) | ((900 - 1) << 14)
        dados = b"RIFF" + bytes(4) + b"WEBPVP8L" + bytes(4) + b"\x2f" + bits.to_bytes(4, "little") + bytes(5)
        self.assertEqual(build.dimensoes_webp(self.escrever(dados)), (1600, 900))

    def test_arquivo_que_nao_e_webp_falha(self):
        with self.assertRaises(build.ErroDeConteudo):
            build.dimensoes_webp(self.escrever(b"isto nao e uma imagem, e tem mais de trinta bytes"))


if __name__ == "__main__":
    unittest.main()
