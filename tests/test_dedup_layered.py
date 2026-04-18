import unittest
from datetime import datetime

from kindle_extractor.dedup import decide_duplicate, normalize_text
from kindle_extractor.extractor import KindleHighlightsExtractor


def _entry(start_pos, end_pos, content, date_obj=None):
    return {
        "start_pos": start_pos,
        "end_pos": end_pos,
        "content": content,
        "date_obj": date_obj or datetime(2024, 1, 1),
    }


class LayeredDedupTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "remove_duplicates": True,
            "similarity_threshold": 0.8,
            "dedup_prefix_words": 5,
        }

    def test_normalize_text_removes_accents_case_and_extra_spaces(self):
        self.assertEqual(
            normalize_text("  A\u00e7\u00e3o,   TESTE!!  "),
            "acao teste",
        )

    def test_detects_exact_duplicate_first(self):
        existing = [_entry(100, 110, "Texto exatamente igual", datetime(2024, 1, 1))]
        new_entry = _entry(100, 110, "Texto exatamente igual", datetime(2024, 1, 2))

        decision = decide_duplicate(new_entry, existing, self.config)

        self.assertTrue(decision.is_duplicate)
        self.assertTrue(decision.replace_existing)
        self.assertEqual(decision.reason, "exact_duplicate_replaced_by_better_record")

    def test_same_start_and_same_prefix_prefers_longer_end_position(self):
        existing = [
            _entry(
                200,
                210,
                "este trecho comeca igual e termina curto",
                datetime(2024, 1, 1),
            )
        ]
        new_entry = _entry(
            200,
            230,
            "este trecho comeca igual e termina com versao mais completa",
            datetime(2024, 1, 1),
        )

        decision = decide_duplicate(new_entry, existing, self.config)

        self.assertTrue(decision.is_duplicate)
        self.assertTrue(decision.replace_existing)
        self.assertEqual(decision.reason, "same_start_prefix_replaced_by_better_record")

    def test_same_start_with_different_texts_is_not_removed(self):
        existing = [_entry(300, 305, "primeiro bloco com conteudo A", datetime(2024, 1, 1))]
        new_entry = _entry(300, 330, "segundo bloco totalmente distinto", datetime(2024, 1, 2))

        decision = decide_duplicate(new_entry, existing, self.config)

        self.assertFalse(decision.is_duplicate)
        self.assertIsNone(decision.reason)

    def test_similarity_rule_remains_as_fallback(self):
        config = dict(self.config)
        config["similarity_threshold"] = 0.6

        existing = [
            _entry(
                400,
                420,
                "abertura completamente diferente mas o restante do texto compartilhado e muito semelhante",
                datetime(2024, 1, 1),
            )
        ]
        new_entry = _entry(
            400,
            420,
            "inicio distante e diferente mas o restante do texto compartilhado e muito semelhante",
            datetime(2024, 1, 1),
        )

        decision = decide_duplicate(new_entry, existing, config)

        self.assertTrue(decision.is_duplicate)
        self.assertEqual(decision.reason, "similarity_fallback")

    def test_extractor_exposes_dedup_metrics_and_report(self):
        extractor = KindleHighlightsExtractor(
            {
                "remove_duplicates": True,
                "similarity_threshold": 0.8,
                "dedup_prefix_words": 5,
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
            "- Seu destaque na pagina 10 | posicao 100-102 | Adicionado em 2 de janeiro de 2024\n"
            "\n"
            "Texto igual\n"
        )

        extractor.parse_content(content)

        self.assertEqual(extractor.stats["duplicates_removed"], 1)
        self.assertEqual(extractor.stats["dedup_metrics"]["exact_duplicates_removed"], 1)
        self.assertEqual(len(extractor.stats["dedup_report"]), 1)
        self.assertEqual(
            extractor.stats["dedup_report"][0]["reason"],
            "exact_duplicate_replaced_by_better_record",
        )


if __name__ == "__main__":
    unittest.main()
