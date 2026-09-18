"""Trava de publicação: prova que ela pega o que tem de pegar e falha fechada."""
import tempfile
import unittest
from pathlib import Path

import verificar


def arvore(arquivos: dict[str, str]) -> Path:
    raiz = Path(tempfile.mkdtemp())
    for nome, texto in arquivos.items():
        caminho = raiz / nome
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(texto, encoding="utf-8")
    return raiz


PAGINA_BOA = '<a href="a/">x</a><img src="img/t.webp" alt="tela" width="10" height="5">'


class TesteTermos(unittest.TestCase):
    def test_acha_termo_sem_diferenciar_maiuscula_e_diz_onde(self):
        raiz = arvore({"conteudo/x.toml": "linha boa\nfoi na Loja-Secreta ontem\n"})
        achados = verificar.achar_termos(raiz, ["loja-secreta"])
        self.assertEqual(len(achados), 1)
        self.assertIn("conteudo/x.toml:2", achados[0])

    def test_acha_termo_no_nome_do_arquivo(self):
        raiz = arvore({"docs/img/loja-secreta.svg": "<svg/>"})
        achados = verificar.achar_termos(raiz, ["Loja-Secreta"])
        self.assertTrue(any("nome de arquivo" in a for a in achados))

    def test_ignora_git_e_binarios(self):
        raiz = arvore({".git/config": "loja-secreta", "docs/a.webp": "loja-secreta"})
        self.assertEqual(verificar.achar_termos(raiz, ["loja-secreta"]), [])

    def test_lista_ausente_falha_fechada(self):
        with self.assertRaises(verificar.ErroDeVerificacao):
            verificar.ler_proibidos(Path("/nao/existe/proibidos.txt"))

    def test_lista_vazia_falha_fechada(self):
        raiz = arvore({"p.txt": "# só comentário\n\n"})
        with self.assertRaises(verificar.ErroDeVerificacao):
            verificar.ler_proibidos(raiz / "p.txt")


class TesteHtml(unittest.TestCase):
    def test_pagina_boa_passa(self):
        raiz = arvore({"index.html": PAGINA_BOA, "a/index.html": "<p>ok</p>", "img/t.webp": ""})
        self.assertEqual(verificar.conferir_html(raiz), [])

    def test_link_quebrado_e_relatado(self):
        raiz = arvore({"index.html": '<a href="sumiu/">x</a>'})
        achados = verificar.conferir_html(raiz)
        self.assertEqual(len(achados), 1)
        self.assertIn("sumiu/", achados[0])

    def test_srcset_e_poster_tambem_sao_conferidos(self):
        raiz = arvore({"index.html": '<video poster="p.webp"></video>'
                                      '<img src="a.webp" srcset="a.webp 800w, b.webp 1600w" alt="" width="1" height="1">',
                       "a.webp": ""})
        achados = verificar.conferir_html(raiz)
        self.assertEqual(len(achados), 2)

    def test_img_sem_alt_ou_sem_medida_e_relatada(self):
        raiz = arvore({"index.html": '<img src="a.webp" width="1" height="1"><img src="a.webp" alt="x">',
                       "a.webp": ""})
        achados = verificar.conferir_html(raiz)
        self.assertEqual(len(achados), 2)

    def test_link_externo_e_ancora_nao_sao_conferidos(self):
        raiz = arvore({"index.html": '<a href="https://exemplo.com">a</a><a href="#topo">b</a>'
                                      '<a href="mailto:a@exemplo.com">c</a>'})
        self.assertEqual(verificar.conferir_html(raiz), [])


if __name__ == "__main__":
    unittest.main()
