import json
import unittest
import uuid
from pathlib import Path
import shutil

from kindle_extractor.extractor import KindleHighlightsExtractor


class RefactorEquivalenceTests(unittest.TestCase):
    def test_config_json_compatibility(self):
        config_path = Path("config.json")
        with open(config_path, "r", encoding="utf-8") as f:
            file_config = json.load(f)

        extractor = KindleHighlightsExtractor(file_config)
        self.assertIn("export_formats", extractor.config)
        self.assertIn("markdown", extractor.config["export_formats"])
        self.assertIn("html", extractor.config["export_formats"])
        self.assertIn("txt", extractor.config["export_formats"])

    def test_parse_title_and_author_preserves_current_rules(self):
        extractor = KindleHighlightsExtractor()

        title, author = extractor.parse_title_and_author(
            "A lógica do Cisne Negro (Taleb, Nassim Nicholas)"
        )
        self.assertEqual(title, "A lógica do Cisne Negro")
        self.assertEqual(author, "Nassim Nicholas Taleb")

        title2, author2 = extractor.parse_title_and_author(
            "Respire - uma vida em movimento - Rickson Gracie (Rickson Gracie)"
        )
        self.assertEqual(title2, "Respire - uma vida em movimento")
        self.assertEqual(author2, "Rickson Gracie")

    def test_deduplication_keeps_single_entry(self):
        extractor = KindleHighlightsExtractor(
            {
                "remove_duplicates": True,
                "similarity_threshold": 0.8,
                "export_formats": {
                    "markdown": {"enabled": False, "folder": "markdown"},
                    "html": {"enabled": False, "folder": "html"},
                    "txt": {"enabled": False, "folder": "txt"},
                },
            }
        )

        content = (
            "Livro Exemplo (Autor Exemplo)\n"
            "- Seu destaque na pagina 10 | posicao 100-102 | Adicionado em 1 de janeiro de 2024\n"
            "\n"
            "Texto igual\n"
            "==========\n"
            "Livro Exemplo (Autor Exemplo)\n"
            "- Seu destaque na pagina 10 | posicao 100-102 | Adicionado em 1 de janeiro de 2024\n"
            "\n"
            "Texto igual\n"
        )

        extractor.parse_content(content)

        self.assertEqual(extractor.stats["total_entries"], 1)
        self.assertEqual(extractor.stats["duplicates_removed"], 1)
        self.assertEqual(len(extractor.books["Livro Exemplo"]), 1)

    def test_generates_markdown_html_txt_with_filename_rule(self):
        extractor = KindleHighlightsExtractor(
            {
                "export_formats": {
                    "markdown": {
                        "enabled": True,
                        "include_metadata": True,
                        "folder": "markdown",
                    },
                    "html": {
                        "enabled": True,
                        "include_metadata": True,
                        "folder": "html",
                    },
                    "txt": {
                        "enabled": True,
                        "include_metadata": True,
                        "plain_text": True,
                        "folder": "txt",
                    },
                }
            }
        )

        content = (
            "Clean Code (Martin, Robert C.)\n"
            "- Seu destaque na página 12 | posição 200-201 | Adicionado em 2 de fevereiro de 2024\n"
            "\n"
            "Código limpo importa.\n"
        )
        extractor.parse_content(content)

        tmp_root = Path("tests") / f".tmp_{uuid.uuid4().hex}"
        output_dir = tmp_root / "temp_output"
        try:
            extractor.generate_files(output_dir)

            base = "clean-code-robert-c.-martin"
            self.assertTrue((output_dir / "markdown" / f"{base}.md").exists())
            self.assertTrue((output_dir / "html" / f"{base}.html").exists())
            self.assertTrue((output_dir / "txt" / f"{base}.txt").exists())
        finally:
            if tmp_root.exists():
                shutil.rmtree(tmp_root)


if __name__ == "__main__":
    unittest.main()
