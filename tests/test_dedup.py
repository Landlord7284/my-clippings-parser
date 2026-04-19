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


def _dedup_config(similarity_threshold=0.8):
    return {"remove_duplicates": True, "similarity_threshold": similarity_threshold}


def test_normalize_text_removes_accents_case_and_extra_spaces():
    assert normalize_text("  Ação,   TESTE!!  ") == "acao teste"


def test_detects_exact_duplicate_and_prefers_more_recent_record():
    existing = [_entry(100, 110, "Texto exatamente igual", datetime(2024, 1, 1))]
    new_entry = _entry(100, 110, "Texto exatamente igual", datetime(2024, 1, 2))

    decision = decide_duplicate(new_entry, existing, _dedup_config())

    assert decision.is_duplicate is True
    assert decision.replace_existing is True
    assert decision.reason == "exact_duplicate_replaced_by_better_record"


def test_same_start_with_expanded_text_replaces_shorter_entry():
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

    decision = decide_duplicate(new_entry, existing, _dedup_config())

    assert decision.is_duplicate is True
    assert decision.replace_existing is True
    assert decision.reason in {
        "same_start_containment_replaced_by_better_record",
        "same_start_expansion_replaced_by_better_record",
    }


def test_same_range_with_redundant_subexcerpt_keeps_existing_record():
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

    decision = decide_duplicate(new_entry, existing, _dedup_config())

    assert decision.is_duplicate is True
    assert decision.replace_existing is False
    assert decision.reason == "same_range_containment_kept_existing_better_record"


def test_distinct_text_with_related_position_is_not_removed():
    existing = [_entry(355, 355, "Entre outros impulsos potencialmente autossabotadores estao")]
    new_entry = _entry(
        355,
        357,
        "O desejo de parecer forte o tempo todo e baseado na crenca de que nunca demonstrar vulnerabilidade equivale a forca",
    )

    decision = decide_duplicate(new_entry, existing, _dedup_config())

    assert decision.is_duplicate is False
    assert decision.reason is None


def test_similarity_fallback_can_detect_near_duplicates_conservatively():
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

    decision = decide_duplicate(new_entry, existing, _dedup_config(similarity_threshold=0.6))

    assert decision.is_duplicate is True
    assert decision.reason == "similarity_fallback"


def test_entries_with_different_type_are_not_deduplicated():
    existing = [_entry(100, 102, "Mesmo conteúdo", entry_type="highlight")]
    new_entry = _entry(100, 102, "Mesmo conteúdo", entry_type="note")

    decision = decide_duplicate(new_entry, existing, _dedup_config())

    assert decision.is_duplicate is False


def test_real_regression_case_same_start_expansion_from_my_clippings():
    existing = [
        _entry(
            2153,
            2154,
            "Você será requisitado a fazer coisas erradas não importa para onde vá.",
            datetime(2024, 1, 1),
        )
    ]
    new_entry = _entry(
        2153,
        2156,
        "Você será requisitado a fazer coisas erradas não importa para onde vá. Em algum momento, toda criatura vivente deve fazer isso.",
        datetime(2024, 1, 2),
    )

    decision = decide_duplicate(new_entry, existing, _dedup_config())

    assert decision.is_duplicate is True
    assert decision.replace_existing is True


def test_real_regression_case_same_range_prefers_longer_context():
    existing = [
        _entry(
            3041,
            3045,
            "Não tenho desejos materiais e não estou endividado. Meu apartamento está quitado.",
            datetime(2024, 1, 1),
        )
    ]
    new_entry = _entry(
        3041,
        3045,
        "Prefiro levar uma vida ascética. Não tenho desejos materiais e não estou endividado. Meu apartamento está quitado.",
        datetime(2024, 1, 2),
    )

    decision = decide_duplicate(new_entry, existing, _dedup_config())

    assert decision.is_duplicate is True
    assert decision.replace_existing is True


def test_extractor_exposes_dedup_metrics_for_exact_duplicates():
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
        "- Seu destaque na pagina 10 | posicao 100-102 | Adicionado em 1 de janeiro de 2024\n\n"
        "Texto igual\n"
        "==========\n"
        "Livro Exemplo (Autor Exemplo)\n"
        "- Seu destaque na pagina 10 | posicao 100-102 | Adicionado em 2 de janeiro de 2024\n\n"
        "Texto igual\n"
    )

    extractor.parse_content(content)

    assert extractor.stats["duplicates_removed"] == 1
    assert extractor.stats["dedup_metrics"]["exact_duplicates_removed"] == 1
    assert len(extractor.stats["dedup_report"]) == 1
