import hashlib
import io
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd
import streamlit as st

from .book_selection_service import (
    BATCH_CLEAR_VISIBLE,
    BATCH_RECOMMENDED,
    BATCH_SELECT_VISIBLE,
    FILTER_ALL,
    STATUS_FILTER_LABELS,
    BookSelectionService,
)
from .extractor import KindleHighlightsExtractor
from .processing_store import ProcessingStore

STATE_ANALYSIS_ID = "analysis_id"
STATE_ANALYSIS = "analysis_result"
STATE_SELECTED_KEYS = "selected_book_keys"
STATE_SELECTION_MAP = "selected_book_map"
STATE_EDITOR_VERSION = "selection_editor_version"
STATE_LAST_UPLOADED_NAME = "last_uploaded_name"
STORE_PATH = Path(".kindle_processing_store.json")

STATUS_EMOJI = {
    "novo": "🟢 Novo",
    "nunca_exportado": "🟡 Nunca exportado",
    "com_novidades": "🔵 Com novidades",
    "sem_novidades": "⚪ Sem novidades",
}


def main():
    st.set_page_config(
        page_title="Extrator de Destaques Kindle",
        page_icon="📚",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    _inject_custom_css()
    _init_session_defaults()

    config = render_sidebar()
    render_header()

    uploaded_file = render_upload_section()
    render_status_section(uploaded_file)

    if uploaded_file is None:
        render_empty_state()
        render_help()
        return

    current_analysis_id = get_uploaded_file_hash(uploaded_file)
    reset_analysis_if_new_upload(current_analysis_id, uploaded_file.name)

    render_analysis_actions(uploaded_file, config, current_analysis_id)

    analysis_result = st.session_state.get(STATE_ANALYSIS)
    if analysis_result and st.session_state.get(STATE_ANALYSIS_ID) == current_analysis_id:
        render_intermediate_step(analysis_result, config)

    render_help()


def _init_session_defaults():
    st.session_state.setdefault(STATE_ANALYSIS_ID, None)
    st.session_state.setdefault(STATE_ANALYSIS, None)
    st.session_state.setdefault(STATE_SELECTED_KEYS, [])
    st.session_state.setdefault(STATE_SELECTION_MAP, {})
    st.session_state.setdefault(STATE_EDITOR_VERSION, 0)


def _inject_custom_css():
    st.markdown(
        """
        <style>
            .block-container {
                padding-top: 1.4rem;
                padding-bottom: 2rem;
                max-width: 1500px;
            }

            .hero {
                padding: 1.35rem 1.5rem;
                border: 1px solid rgba(120, 120, 140, 0.16);
                border-radius: 22px;
                background:
                    radial-gradient(circle at top right, rgba(99, 102, 241, 0.14), transparent 28%),
                    radial-gradient(circle at left center, rgba(16, 185, 129, 0.10), transparent 24%),
                    rgba(255, 255, 255, 0.03);
                margin-bottom: 1rem;
            }

            .hero h1 {
                margin: 0;
                padding: 0;
                font-size: 2rem;
            }

            .hero p {
                margin: 0.5rem 0 0 0;
                opacity: 0.85;
            }

            .section-card {
                border: 1px solid rgba(120, 120, 140, 0.14);
                border-radius: 18px;
                padding: 1rem 1rem 0.9rem 1rem;
                background: rgba(255, 255, 255, 0.025);
                margin-bottom: 1rem;
            }

            .subtle {
                opacity: 0.78;
            }

            div[data-testid="stMetric"] {
                border: 1px solid rgba(120, 120, 140, 0.14);
                border-radius: 16px;
                padding: 0.8rem 0.9rem;
                background: rgba(255, 255, 255, 0.028);
            }

            div[data-testid="stFileUploader"] {
                border-radius: 18px;
                padding: 0.35rem;
            }

            .pill-row {
                display: flex;
                gap: 0.5rem;
                flex-wrap: wrap;
                margin-top: 0.8rem;
            }

            .pill {
                font-size: 0.84rem;
                padding: 0.28rem 0.65rem;
                border-radius: 999px;
                border: 1px solid rgba(120, 120, 140, 0.18);
                background: rgba(255, 255, 255, 0.04);
            }

            .toolbar-note {
                margin-top: -0.3rem;
                margin-bottom: 0.5rem;
                opacity: 0.72;
                font-size: 0.92rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header():
    st.markdown(
        """
        <div class="hero">
            <h1>📚 Extrator de Destaques Kindle</h1>
            <p>
                Faça upload do <strong>My Clippings.txt</strong>, revise os livros detectados,
                selecione apenas o que importa e exporte em Markdown, HTML e/ou TXT.
            </p>
            <div class="pill-row">
                <span class="pill">Análise por livro</span>
                <span class="pill">Seleção intermediária</span>
                <span class="pill">Deduplicação</span>
                <span class="pill">Exportação em lote</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar() -> Dict[str, object]:
    with st.sidebar:
        st.header("⚙️ Configurações")
        st.caption("Ajuste a exportação antes de analisar o arquivo.")

        st.subheader("Formatos")
        export_markdown = st.checkbox("Markdown (.md)", value=True)
        export_html = st.checkbox("HTML (.html)", value=False)
        export_txt = st.checkbox("Texto (.txt)", value=False)

        st.subheader("Processamento")
        remove_duplicates = st.checkbox("Remover duplicatas", value=True)
        similarity_threshold = st.slider(
            "Limite de similaridade",
            min_value=0.5,
            max_value=1.0,
            value=0.8,
            step=0.1,
            help="Threshold para a camada conservadora de deduplicação.",
        )
        include_bookmarks = st.checkbox("Incluir marcadores", value=True)
        include_metadata = st.checkbox("Incluir metadados nos arquivos", value=True)

        st.divider()
        enabled_formats = _selected_format_labels(
            {
                "export_markdown": export_markdown,
                "export_html": export_html,
                "export_txt": export_txt,
            }
        )
        st.info(
            "\n".join(
                [
                    "A análise não exporta nada sozinha.",
                    f"Formatos ativos: {', '.join(enabled_formats)}.",
                ]
            )
        )

    return {
        "export_markdown": export_markdown,
        "export_html": export_html,
        "export_txt": export_txt,
        "remove_duplicates": remove_duplicates,
        "similarity_threshold": similarity_threshold,
        "include_bookmarks": include_bookmarks,
        "include_metadata": include_metadata,
    }


def render_upload_section():
    col_upload, col_preview = st.columns([1.35, 0.85], gap="large")

    with col_upload:
        with st.container(border=True):
            st.subheader("1. Upload do arquivo")
            st.caption("Use o arquivo original exportado pelo Kindle.")
            uploaded_file = st.file_uploader(
                "Selecione o arquivo 'My Clippings.txt'",
                type=["txt"],
                help="Arquivo exportado do Kindle contendo destaques, notas e marcadores.",
                label_visibility="visible",
            )

            if uploaded_file is not None:
                file_size = len(uploaded_file.getvalue())
                st.success(
                    f"Arquivo carregado: {uploaded_file.name} · {file_size:,} bytes".replace(",", ".")
                )
            return uploaded_file

    with col_preview:
        with st.container(border=True):
            st.subheader("2. O que acontece depois")
            st.markdown(
                """
                <div class="subtle">
                    O app lê as entradas, agrupa por livro, compara com o histórico local,
                    sugere seleção automática e gera um ZIP só com os livros escolhidos.
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown(
                """
                - **Análise**: leitura, parser e deduplicação
                - **Seleção**: busca, filtros e ações em lote
                - **Exportação**: Markdown, HTML e/ou TXT
                """
            )


def render_status_section(uploaded_file):
    metrics = _estimate_upload_metrics(uploaded_file)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Entradas", metrics["entries"])
    with col2:
        st.metric("Livros únicos", metrics["books"])
    with col3:
        st.metric("Arquivo", metrics["filename"])
    with col4:
        st.metric("Pronto para análise", metrics["ready"])


def _estimate_upload_metrics(uploaded_file) -> Dict[str, object]:
    if uploaded_file is None:
        return {
            "entries": "-",
            "books": "-",
            "filename": "Nenhum",
            "ready": "Não",
        }

    try:
        content = uploaded_file.getvalue().decode("utf-8")
        entries = [entry for entry in content.split("==========") if entry.strip()]
        titles = set()
        for entry in entries:
            lines = entry.strip().split("\n")
            if lines and lines[0].strip():
                titles.add(lines[0].strip())
        return {
            "entries": len(entries),
            "books": len(titles),
            "filename": uploaded_file.name,
            "ready": "Sim",
        }
    except UnicodeDecodeError:
        return {
            "entries": "?",
            "books": "?",
            "filename": uploaded_file.name,
            "ready": "Erro de encoding",
        }
    except Exception:
        return {
            "entries": "?",
            "books": "?",
            "filename": uploaded_file.name,
            "ready": "Erro",
        }


def render_analysis_actions(uploaded_file, config, current_analysis_id):
    with st.container(border=True):
        st.subheader("3. Análise")
        st.caption("Rode a análise para atualizar a classificação dos livros neste arquivo.")

        col1, col2, col3 = st.columns([1, 1, 1.2])
        with col1:
            if st.button("🔎 Analisar arquivo", type="primary", use_container_width=True):
                run_analysis(
                    uploaded_file,
                    config,
                    current_analysis_id,
                    force_reprocess=False,
                )
        with col2:
            if st.button("↻ Reanalisar", use_container_width=True):
                run_analysis(
                    uploaded_file,
                    config,
                    current_analysis_id,
                    force_reprocess=True,
                )
        with col3:
            analysis_result = st.session_state.get(STATE_ANALYSIS)
            ready = "Sim" if analysis_result else "Ainda não"
            st.info(f"Resultado disponível: {ready}")


def run_analysis(uploaded_file, config, analysis_id, force_reprocess=False):
    progress_bar = st.progress(0)
    status_text = st.empty()

    try:
        status_text.text("Inicializando análise...")
        progress_bar.progress(12)

        extractor = KindleHighlightsExtractor(build_extractor_config(config))
        content = uploaded_file.getvalue().decode("utf-8")

        status_text.text("Lendo entradas do My Clippings...")
        progress_bar.progress(48)
        extractor.parse_content(content)

        store = ProcessingStore(STORE_PATH)
        service = BookSelectionService(store)

        status_text.text("Classificando livros e calculando status...")
        progress_bar.progress(82)
        rows = service.build_books_table(
            extractor.books,
            persist=True,
            force_reprocess=force_reprocess,
        )
        selection_map = service.build_default_selection_map(rows)

        st.session_state[STATE_ANALYSIS_ID] = analysis_id
        st.session_state[STATE_ANALYSIS] = {
            "books": extractor.books,
            "rows": rows,
            "stats": extractor.stats,
        }
        st.session_state[STATE_SELECTION_MAP] = selection_map
        st.session_state[STATE_SELECTED_KEYS] = service.selected_book_keys(selection_map)
        st.session_state[STATE_EDITOR_VERSION] += 1

        progress_bar.progress(100)
        status_text.text("Análise concluída. Revise a seleção antes de exportar.")
    except UnicodeDecodeError:
        st.error("Não foi possível ler o arquivo como UTF-8.")
    except Exception as error:
        st.error(f"Erro inesperado na análise: {error}")
        st.exception(error)


def render_intermediate_step(analysis_result, config):
    rows = analysis_result["rows"]
    if not rows:
        st.warning("Nenhum livro foi detectado no arquivo.")
        return

    store = ProcessingStore(STORE_PATH)
    service = BookSelectionService(store)
    selection_map = service.sync_selection_map(rows, st.session_state.get(STATE_SELECTION_MAP))
    st.session_state[STATE_SELECTION_MAP] = selection_map

    with st.container(border=True):
        st.subheader("4. Seleção dos livros")
        st.caption("Filtre, revise a recomendação automática e exporte só o que fizer sentido.")

        filter_col1, filter_col2, filter_col3 = st.columns([2.2, 1.3, 1.3])
        with filter_col1:
            search_term = st.text_input(
                "Busca por título ou autor",
                key="selection_search_term",
                placeholder="Digite parte do título ou autor...",
            )
        with filter_col2:
            status_filter = st.selectbox(
                "Status",
                options=list(STATUS_FILTER_LABELS.keys()),
                format_func=lambda key: STATUS_FILTER_LABELS[key],
                index=list(STATUS_FILTER_LABELS.keys()).index(FILTER_ALL),
                key="selection_status_filter",
            )
        with filter_col3:
            author_options = ["Todos"] + sorted({row["author"] for row in rows})
            author_filter = st.selectbox(
                "Autor",
                options=author_options,
                key="selection_author_filter",
            )

        filtered_rows = service.filter_rows(
            rows,
            selection_map=selection_map,
            search_term=search_term,
            status_filter=status_filter,
            author_filter=None if author_filter == "Todos" else author_filter,
        )
        visible_keys = [row["book_key"] for row in filtered_rows]

        batch_col1, batch_col2, batch_col3 = st.columns(3)
        with batch_col1:
            if st.button("Marcar recomendados", use_container_width=True):
                _apply_batch_selection(service, rows, visible_keys, BATCH_RECOMMENDED)
        with batch_col2:
            if st.button("Marcar visíveis", use_container_width=True):
                _apply_batch_selection(service, rows, visible_keys, BATCH_SELECT_VISIBLE)
        with batch_col3:
            if st.button("Desmarcar visíveis", use_container_width=True):
                _apply_batch_selection(service, rows, visible_keys, BATCH_CLEAR_VISIBLE)

        st.markdown(
            f"<div class='toolbar-note'>Mostrando {len(filtered_rows)} de {len(rows)} livros.</div>",
            unsafe_allow_html=True,
        )

        if filtered_rows:
            selection_map = _render_books_data_editor(filtered_rows, selection_map)
        else:
            st.info("Nenhum livro encontrado com os filtros atuais.")

        st.session_state[STATE_SELECTION_MAP] = selection_map
        selected_book_keys = service.selected_book_keys(selection_map)
        st.session_state[STATE_SELECTED_KEYS] = selected_book_keys

        _render_selection_summary(rows, selection_map, config)

        with st.expander("Detalhes da análise"):
            stats = analysis_result.get("stats", {})
            metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
            metric_col1.metric("Entradas válidas", stats.get("total_entries", 0))
            metric_col2.metric("Duplicatas removidas", stats.get("duplicates_removed", 0))
            metric_col3.metric("Livros processados", stats.get("books_processed", 0))
            metric_col4.metric("Erros", stats.get("errors", 0))

            st.caption("Última análise por livro (America/Sao_Paulo):")
            for row in filtered_rows:
                st.text(f"- {row['title']}: {row['last_analysis_display']}")


def _render_books_data_editor(filtered_rows, selection_map: Dict[str, bool]) -> Dict[str, bool]:
    editor_df = pd.DataFrame(
        [
            {
                "Selecionar": bool(selection_map.get(row["book_key"], False)),
                "Status": STATUS_EMOJI.get(row["status"], row["status_label"]),
                "Título": row["title"],
                "Autor": row["author"],
                "Highlights": row["highlights"],
                "Notas": row["notes"],
                "Bookmarks": row["bookmarks"],
                "Novos": row["new_highlights_count"],
                "Última exportação": row["last_export_display"],
                "_book_key": row["book_key"],
            }
            for row in filtered_rows
        ]
    )

    edited_df = st.data_editor(
        editor_df,
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        key=f"selection_editor_{st.session_state.get(STATE_EDITOR_VERSION, 0)}",
        disabled=[
            "Status",
            "Título",
            "Autor",
            "Highlights",
            "Notas",
            "Bookmarks",
            "Novos",
            "Última exportação",
            "_book_key",
        ],
        column_config={
            "Selecionar": st.column_config.CheckboxColumn("Selecionar", width="small"),
            "Status": st.column_config.TextColumn("Status", width="medium"),
            "Título": st.column_config.TextColumn("Título", width="large"),
            "Autor": st.column_config.TextColumn("Autor", width="medium"),
            "Highlights": st.column_config.NumberColumn("Highlights", width="small"),
            "Notas": st.column_config.NumberColumn("Notas", width="small"),
            "Bookmarks": st.column_config.NumberColumn("Bookmarks", width="small"),
            "Novos": st.column_config.NumberColumn("Novos", width="small"),
            "Última exportação": st.column_config.TextColumn("Última exportação", width="medium"),
            "_book_key": None,
        },
    )

    updated_selection = dict(selection_map)
    for _, row in edited_df.iterrows():
        updated_selection[str(row["_book_key"])] = bool(row["Selecionar"])
    return updated_selection


def _render_selection_summary(rows, selection_map, config):
    service = BookSelectionService(ProcessingStore(STORE_PATH))
    selected_book_keys = service.selected_book_keys(selection_map)
    selected_count = len(selected_book_keys)
    selected_highlights = service.selected_highlights_total(rows, selection_map)
    selected_formats = _selected_format_labels(config)

    col1, col2, col3, col4 = st.columns([1, 1, 1, 1.2])
    with col1:
        st.metric("Livros selecionados", selected_count)
    with col2:
        st.metric("Highlights selecionados", selected_highlights)
    with col3:
        st.metric("Formatos", len(selected_formats))
    with col4:
        st.markdown(
            "**Saída ativa**  \n" + " / ".join(selected_formats),
        )

    action_col1, action_col2 = st.columns([2, 1])
    with action_col1:
        st.info(
            "A seleção padrão já marca livros novos, nunca exportados ou com mudanças desde a última exportação."
        )
    with action_col2:
        if st.button(
            "🚀 Exportar selecionados",
            type="primary",
            use_container_width=True,
        ):
            export_selected_books(
                st.session_state.get(STATE_ANALYSIS),
                config,
                selected_book_keys,
            )


def _apply_batch_selection(service, rows, visible_keys, action):
    selection_map = st.session_state.get(STATE_SELECTION_MAP, {})
    updated_selection = service.apply_batch_action(rows, selection_map, visible_keys, action)
    st.session_state[STATE_SELECTION_MAP] = updated_selection
    st.session_state[STATE_SELECTED_KEYS] = service.selected_book_keys(updated_selection)
    st.session_state[STATE_EDITOR_VERSION] += 1
    st.rerun()


def _selected_format_labels(config):
    labels = []
    if config.get("export_markdown"):
        labels.append("Markdown")
    if config.get("export_html"):
        labels.append("HTML")
    if config.get("export_txt"):
        labels.append("TXT")
    return labels or ["Nenhum"]


def export_selected_books(analysis_result, config, selected_book_keys: List[str]):
    if not selected_book_keys:
        st.warning("Selecione ao menos um livro para exportar.")
        return

    rows = analysis_result["rows"]
    key_to_title = {row["book_key"]: row["title"] for row in rows}
    selected_titles = [key_to_title[key] for key in selected_book_keys if key in key_to_title]
    if not selected_titles:
        st.warning("Nenhum livro válido foi selecionado para exportação.")
        return

    progress_bar = st.progress(0)
    status_text = st.empty()

    try:
        status_text.text("Gerando arquivos dos livros selecionados...")
        progress_bar.progress(34)

        extractor = KindleHighlightsExtractor(build_extractor_config(config))
        extractor.books = analysis_result["books"]
        selected_entries = sum(len(extractor.books.get(title, [])) for title in selected_titles)
        extractor.stats["books_processed"] = len(selected_titles)
        extractor.stats["total_entries"] = selected_entries

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "temp_output"
            extractor.generate_files(output_dir, selected_titles=selected_titles)

            progress_bar.progress(76)
            status_text.text("Compactando arquivos...")
            zip_buffer = create_zip_file(output_dir)

            progress_bar.progress(100)
            status_text.text("Exportação concluída.")

            show_results(extractor.stats, selected_titles)
            st.download_button(
                label="📥 Baixar ZIP",
                data=zip_buffer.getvalue(),
                file_name=f"kindle_destaques_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                mime="application/zip",
                type="primary",
                use_container_width=True,
            )

        store = ProcessingStore(STORE_PATH)
        export_formats = [
            format_name
            for format_name, format_config in build_extractor_config(config)["export_formats"].items()
            if format_config.get("enabled")
        ]
        service = BookSelectionService(store)
        service.mark_exported(
            selected_book_keys,
            export_formats=export_formats,
        )

        refreshed_rows = service.build_books_table(analysis_result["books"], persist=False)
        analysis_result["rows"] = refreshed_rows
        st.session_state[STATE_ANALYSIS] = analysis_result

        refreshed_selection = service.sync_selection_map(
            refreshed_rows,
            st.session_state.get(STATE_SELECTION_MAP),
        )
        st.session_state[STATE_SELECTION_MAP] = refreshed_selection
        st.session_state[STATE_SELECTED_KEYS] = service.selected_book_keys(refreshed_selection)
        st.session_state[STATE_EDITOR_VERSION] += 1
    except Exception as error:
        st.error(f"Erro inesperado na exportação: {error}")
        st.exception(error)


def create_zip_file(output_dir: Path):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for file_path in output_dir.rglob("*"):
            if file_path.is_file():
                relative_path = file_path.relative_to(output_dir)
                zip_file.write(file_path, relative_path)
    zip_buffer.seek(0)
    return zip_buffer


def show_results(stats, selected_titles):
    st.success("Exportação concluída com sucesso.")

    col1, col2, col3 = st.columns(3)
    col1.metric("Livros exportados", len(selected_titles))
    col2.metric("Entradas exportadas", stats["total_entries"])
    col3.metric("Arquivos gerados", sum(stats["files_generated"].values()))

    generated = {k.upper(): v for k, v in stats["files_generated"].items() if v > 0}
    if generated:
        st.markdown("**Arquivos por formato**")
        for label, count in generated.items():
            st.info(f"{label}: {count} arquivo(s)")


def build_extractor_config(config):
    return {
        "output_folder": "temp_output",
        "export_formats": {
            "markdown": {
                "enabled": config["export_markdown"],
                "include_metadata": config["include_metadata"],
                "folder": "markdown",
            },
            "html": {
                "enabled": config["export_html"],
                "include_metadata": config["include_metadata"],
                "css_style": "default",
                "folder": "html",
            },
            "txt": {
                "enabled": config["export_txt"],
                "include_metadata": config["include_metadata"],
                "plain_text": True,
                "folder": "txt",
            },
        },
        "remove_duplicates": config["remove_duplicates"],
        "similarity_threshold": config["similarity_threshold"],
        "include_bookmarks": config["include_bookmarks"],
        "date_format": "portuguese",
        "encoding": "utf-8",
    }


def get_uploaded_file_hash(uploaded_file):
    return hashlib.sha1(uploaded_file.getvalue()).hexdigest()


def reset_analysis_if_new_upload(current_analysis_id, uploaded_name):
    previous_id = st.session_state.get(STATE_ANALYSIS_ID)
    previous_name = st.session_state.get(STATE_LAST_UPLOADED_NAME)
    if (previous_id and previous_id != current_analysis_id) or (
        previous_name and previous_name != uploaded_name
    ):
        st.session_state[STATE_ANALYSIS] = None
        st.session_state[STATE_SELECTED_KEYS] = []
        st.session_state[STATE_SELECTION_MAP] = {}
        st.session_state[STATE_EDITOR_VERSION] += 1
        st.session_state.pop("selection_search_term", None)
        st.session_state.pop("selection_status_filter", None)
        st.session_state.pop("selection_author_filter", None)

    st.session_state[STATE_ANALYSIS_ID] = current_analysis_id
    st.session_state[STATE_LAST_UPLOADED_NAME] = uploaded_name


def render_empty_state():
    with st.container(border=True):
        st.subheader("Próximo passo")
        st.caption("Faça upload do `My Clippings.txt` para habilitar a análise e a seleção dos livros.")


def render_help():
    with st.expander("Como usar"):
        st.markdown(
            """
1. Faça upload do arquivo `My Clippings.txt`.
2. Ajuste formatos e opções na barra lateral.
3. Clique em **Analisar arquivo**.
4. Revise a tabela, filtre e selecione os livros.
5. Exporte apenas os marcados em um único ZIP.

**Onde encontrar o arquivo no Kindle**
- Conecte o Kindle ao computador via USB.
- Navegue até a pasta raiz do dispositivo.
- O arquivo `My Clippings.txt` fica na pasta principal.
            """
        )
