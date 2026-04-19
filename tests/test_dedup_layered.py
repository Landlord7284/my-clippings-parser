import unittest
from datetime import datetime, timezone

from kindle_extractor.dedup import decide_duplicate, normalize_text
from kindle_extractor.extractor import KindleHighlightsExtractor


def _entry(start_pos, end_pos, content, date_obj=None, entry_type="highlight"):
    return {
        "type": entry_type,
        "start_pos": start_pos,
        "end_pos": end_pos,
        "content": content,
        "date_obj": date_obj or datetime(2024, 1, 1, tzinfo=timezone.utc),
    }


class LayeredDedupTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "remove_duplicates": True,
            "similarity_threshold": 0.8,
        }

    def test_normalize_text_removes_accents_case_and_extra_spaces(self):
        self.assertEqual(normalize_text("  Acao,   TESTE!!  "), "acao teste")

    def test_detects_exact_duplicate_first(self):
        existing = [_entry(100, 110, "Texto exatamente igual", datetime(2024, 1, 1))]
        new_entry = _entry(100, 110, "Texto exatamente igual", datetime(2024, 1, 2))

        decision = decide_duplicate(new_entry, existing, self.config)

        self.assertTrue(decision.is_duplicate)
        self.assertTrue(decision.replace_existing)
        self.assertEqual(decision.reason, "exact_duplicate_replaced_by_better_record")

    def test_case_real_same_start_and_expanded_text_collapses_to_complete(self):
        existing = [
            _entry(
                349,
                351,
                "primeiro impulso motivador como a necessidade de ser perfeito precisa sempre vencer",
                datetime(2024, 1, 1),
            )
        ]
        new_entry = _entry(
            349,
            353,
            "ele identifica o primeiro impulso motivador como a necessidade de ser perfeito precisa sempre vencer podemos ver como essa crenca afetou nixon",
            datetime(2024, 1, 2),
        )

        decision = decide_duplicate(new_entry, existing, self.config)

        self.assertTrue(decision.is_duplicate)
        self.assertTrue(decision.replace_existing)
        self.assertEqual(decision.reason, "same_start_containment_replaced_by_better_record")

    def test_case_real_same_range_with_subexcerpt_collapses(self):
        existing = [
            _entry(
                1476,
                1478,
                "acontece quando as condicoes mudam mas voce nao muda nao e facil ter empatia com uma pessoa em negacao",
                datetime(2024, 1, 1),
            )
        ]
        new_entry = _entry(
            1476,
            1478,
            "nao e facil ter empatia com uma pessoa em negacao",
            datetime(2024, 1, 2),
        )

        decision = decide_duplicate(new_entry, existing, self.config)

        self.assertTrue(decision.is_duplicate)
        self.assertFalse(decision.replace_existing)
        self.assertEqual(decision.reason, "same_range_containment_kept_existing_better_record")

    def test_case_real_related_positions_but_distinct_texts_is_preserved(self):
        existing = [_entry(355, 355, "Entre outros impulsos potencialmente autossabotadores estao")]
        new_entry = _entry(
            355,
            357,
            "O desejo de parecer forte o tempo todo e baseado na crenca de que nunca demonstrar vulnerabilidade equivale a forca",
        )

        decision = decide_duplicate(new_entry, existing, self.config)

        self.assertFalse(decision.is_duplicate)
        self.assertIsNone(decision.reason)

    def test_similarity_rule_remains_as_conservative_fallback(self):
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

    def test_extractor_exposes_layered_dedup_metrics(self):
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
