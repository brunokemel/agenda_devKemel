import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parser import parse_txt, extract_links, normalize_importance


SAMPLE = """TITULO: Reuniao
IMPORTANCIA: urgente
TAGS: trabalho
CADERNO: Trabalho
SECAO: Reunioes

Ver https://exemplo.com e ana@empresa.com
---
# Lista
[baixa]
Comprar leite
"""


class ParserTest(unittest.TestCase):
    def test_split_and_importance(self):
        notes = parse_txt(SAMPLE, "agenda.txt")
        self.assertEqual(len(notes), 2)
        self.assertEqual(notes[0]["importance"], "urgente")
        self.assertEqual(notes[0]["title"], "Reuniao")
        self.assertEqual(notes[0]["notebook"], "Trabalho")
        self.assertEqual(notes[1]["importance"], "baixa")

    def test_links(self):
        links = extract_links("veja https://exemplo.com e ana@empresa.com")
        urls = [l["url"] for l in links]
        self.assertTrue(any("exemplo.com" in u for u in urls))
        self.assertTrue(any(u.startswith("mailto:") for u in urls))

    def test_normalize(self):
        self.assertEqual(normalize_importance("HIGH"), "alta")
        self.assertEqual(normalize_importance("!!!"), "media")


if __name__ == "__main__":
    unittest.main()
