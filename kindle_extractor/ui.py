import hashlib
import io
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

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
STATE_RESET_ROW_WIDGETS = "reset_row_widgets"
BOOK_CHECKBOX_PREFIX = "book_row_select_"


def main():
    st.set_page_config(
        page_title="Extrator de Destaques Kindle",
        page_icon="📚",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.title("📚 Extrator de Destaques Kindle")
    st.markdown("---")

    config = render_sidebar()
    uploaded_file = render_upload_section()
    render_status_section(uploaded_file)

    st.markdown("---")

    if uploaded_file is None:
        render_help()
        return

    current_analysis_id = get_uploaded_file_hash(uploaded_file)
    reset_analysis_if_new_upload(current_analysis_id)

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("🔎 Analisar arquivo", type="primary", use_container_width=True):
            run_analysis(uploaded_file, config, current_analysis_id, force_reprocess=False)
    with col2:
        if st.button("↻ Reanalisar", use_container_width=True):
            run_analysis(uploaded_file, config, current_analysis_id, force_reprocess=True)

    analysis_result = st.session_state.get(STATE_ANALYSIS)
    if analysis_result and st.session_state.get(STATE_ANALYSIS_ID) == current_analysis_id:
        render_intermediate_step(analysis_result, config)

    st.markdown("---")
    render_help()


def render_sidebar():
    with st.sidebar:
        st.header("⚙️ Configurações")
        st.subheader("Formatos de Exportação")
        export_markdown = st.checkbox("Markdown (.md)", value=True)
        export_html = st.checkbox("HTML (.html)", value=True)
        export_txt = st.checkbox("Texto (.txt)", value=False)

        st.subheader("Configurações Avançadas")
        remove_duplicates = st.checkbox("Remover duplicatas", value=True)
        similarity_threshold = st.slider(
            "Limite de similaridade",
            min_value=0.5,
            max_value=1.0,
            value=0.8,
            step=0.1,
            help="Threshold para detecção de duplicatas (0.5 = 50%, 1.0 = 100%)",
        )
        include_bookmarks = st.checkbox("Incluir marcadores", value=True)
        include_metadata = st.checkbox("Incluir metadados", value=True)

        st.markdown("---")
        st.info("Use a análise para escolher os livros antes da exportação.")

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
    col1, col2 = st.columns([2, 1])
    with col1:
        st.header("📁 Upload do Arquivo")
        uploaded_file = st.file_uploader(
            "Selecione o arquivo 'My Clippings.txt'",
            type=["txt"],
            help="Arquivo exportado do Kindle contendo os destaques",
        )

        if uploaded_file is not None:
            file_size = len(uploaded_file.getvalue())
            st.success(f"✅ Arquivo carregado: {uploaded_file.name} ({file_size:,} bytes)")

            with st.expander("👀 Preview do arquivo"):
                file_content = uploaded_file.getvalue().decode("utf-8")
                preview_lines = file_content.split("\n")[:20]
                st.text("\n".join(preview_lines))
                total_lines = len(file_content.split("\n"))
                if total_lines > 20:
                    st.info(f"... e mais {total_lines - 20} linhas")
    return uploaded_file


def render_status_section(uploaded_file):
    col1, col2 = st.columns([2, 1])
    with col2:
        st.header("📊 Status")
        if uploaded_file is None:
            st.info("Aguardando upload do arquivo...")
            return

        try:
            content = uploaded_file.getvalue().decode("utf-8")
            entries = content.split("==========")
            total_entries = len([entry for entry in entries if entry.strip()])

            titles = set()
            for entry in entries:
                if not entry.strip():
                    continue
                lines = entry.strip().split("\n")
                if lines and lines[0].strip():
                    titles.add(lines[0].strip())

            st.metric("📖 Entradas encontradas", total_entries)
            st.metric("📚 Livros únicos (aprox.)", len(titles))
        except Exception as error:
            st.error(f"Erro ao analisar arquivo: {error}")


def run_analysis(uploaded_file, config, analysis_id, force_reprocess=False):
    progress_bar = st.progress(0)
    status_text = st.empty()

    try:
        status_text.text("🔄 Inicializando análise...")
        progress_bar.progress(15)

        extractor = KindleHighlightsExtractor(build_extractor_config(config))
        content = uploaded_file.getvalue().decode("utf-8")

        status_text.text("📖 Lendo e classificando entradas...")
        progress_bar.progress(55)
        extractor.parse_content(content)

        store = ProcessingStore(Path(".kindle_processing_store.json"))
        service = BookSelectionService(store)

        status_text.text("📊 Calculando status por última exportação...")
        progress_bar.progress(85)
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
        _sync_checkbox_widget_state(rows, selection_map)

        progress_bar.progress(100)
        status_text.text("✅ Análise concluída. Revise os livros e exporte os selecionados.")
    except Exception as error:
        st.error(f"❌ Erro inesperado na análise: {error}")
        st.exception(error)


def render_intermediate_step(analysis_result, config):
    rows = analysis_result["rows"]
    if not rows:
        st.warning("Nenhum livro foi detectado no arquivo.")
        return

    store = ProcessingStore(Path(".kindle_processing_store.json"))
    service = BookSelectionService(store)

    if st.session_state.get(STATE_RESET_ROW_WIDGETS):
        _clear_checkbox_widget_state()
        st.session_state[STATE_RESET_ROW_WIDGETS] = False

    selection_map = service.sync_selection_map(rows, st.session_state.get(STATE_SELECTION_MAP))
    st.session_state[STATE_SELECTION_MAP] = selection_map

    st.subheader("Etapa intermediária: seleção de livros")

    filter_col1, filter_col2, filter_col3 = st.columns([2.5, 1.5, 1.5])
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

    batch_col1, batch_col2, batch_col3 = st.columns([1, 1, 1])
    with batch_col1:
        if st.button("Marcar recomendados", use_container_width=True):
            _apply_batch_selection(service, rows, visible_keys, BATCH_RECOMMENDED)
    with batch_col2:
        if st.button("Marcar todos os visíveis", use_container_width=True):
            _apply_batch_selection(service, rows, visible_keys, BATCH_SELECT_VISIBLE)
    with batch_col3:
        if st.button("Desmarcar visíveis", use_container_width=True):
            _apply_batch_selection(service, rows, visible_keys, BATCH_CLEAR_VISIBLE)

    st.caption(f"Mostrando {len(filtered_rows)} de {len(rows)} livros.")

    if filtered_rows:
        _render_books_selection_table(filtered_rows, selection_map)
    else:
        st.info("Nenhum livro encontrado com os filtros atuais.")

    st.session_state[STATE_SELECTION_MAP] = selection_map
    selected_book_keys = service.selected_book_keys(selection_map)
    st.session_state[STATE_SELECTED_KEYS] = selected_book_keys

    selected_count = len(selected_book_keys)
    selected_highlights = service.selected_highlights_total(rows, selection_map)
    selected_formats = _selected_format_labels(config)

    summary_col1, summary_col2 = st.columns([2, 1])
    with summary_col1:
        st.info(
            f"Selecionados: {selected_count} livro(s) | "
            f"Highlights selecionados: {selected_highlights} | "
            f"Formatos: {', '.join(selected_formats)}"
        )
    with summary_col2:
        if st.button(
            "🚀 Exportar livros selecionados",
            type="primary",
            use_container_width=True,
        ):
            export_selected_books(analysis_result, config, selected_book_keys)

    with st.expander("Detalhes da análise (secundário)"):
        st.caption("Última análise por livro (America/Sao_Paulo):")
        for row in filtered_rows:
            st.text(f"- {row['title']}: {row['last_analysis_display']}")


def _render_books_selection_table(filtered_rows, selection_map):
    header_cols = st.columns([0.8, 1.7, 3.0, 2.2, 1.0, 1.0, 1.2, 1.6, 1.8])
    headers = [
        "Seleção",
        "Status",
        "Título",
        "Autor",
        "Highlights",
        "Notas",
        "Bookmarks",
        "Novos highlights",
        "Última exportação",
    ]
    for col, label in zip(header_cols, headers):
        col.markdown(f"**{label}**")

    for row in filtered_rows:
        cols = st.columns([0.8, 1.7, 3.0, 2.2, 1.0, 1.0, 1.2, 1.6, 1.8])
        checkbox_key = _checkbox_state_key(row["book_key"])
        if checkbox_key not in st.session_state:
            st.session_state[checkbox_key] = bool(selection_map.get(row["book_key"], False))

        with cols[0]:
            checked = st.checkbox(
                f"Selecionar {row['title']}",
                key=checkbox_key,
                label_visibility="collapsed",
            )
        selection_map[row["book_key"]] = checked

        cols[1].write(row["status_label"])
        cols[2].write(row["title"])
        cols[3].write(row["author"])
        cols[4].write(row["highlights"])
        cols[5].write(row["notes"])
        cols[6].write(row["bookmarks"])
        cols[7].write(row["new_highlights_count"])
        cols[8].write(row["last_export_display"])


def _apply_batch_selection(service, rows, visible_keys, action):
    selection_map = st.session_state.get(STATE_SELECTION_MAP, {})
    updated_selection = service.apply_batch_action(rows, selection_map, visible_keys, action)
    st.session_state[STATE_SELECTION_MAP] = updated_selection
    st.session_state[STATE_SELECTED_KEYS] = service.selected_book_keys(updated_selection)
    _sync_checkbox_widget_state(rows, updated_selection)
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


def _checkbox_state_key(book_key: str) -> str:
    return f"{BOOK_CHECKBOX_PREFIX}{book_key}"


def _clear_checkbox_widget_state():
    keys_to_remove = [
        key
        for key in st.session_state.keys()
        if isinstance(key, str) and key.startswith(BOOK_CHECKBOX_PREFIX)
    ]
    for key in keys_to_remove:
        st.session_state.pop(key, None)


def _sync_checkbox_widget_state(rows, selection_map):
    for row in rows:
        checkbox_key = _checkbox_state_key(row["book_key"])
        st.session_state[checkbox_key] = bool(selection_map.get(row["book_key"], False))


def export_selected_books(analysis_result, config, selected_book_keys):
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
        status_text.text("📝 Gerando arquivos dos livros selecionados...")
        progress_bar.progress(35)

        extractor = KindleHighlightsExtractor(build_extractor_config(config))
        extractor.books = analysis_result["books"]
        selected_entries = sum(len(extractor.books.get(title, [])) for title in selected_titles)
        extractor.stats["books_processed"] = len(selected_titles)
        extractor.stats["total_entries"] = selected_entries

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "temp_output"
            extractor.generate_files(output_dir, selected_titles=selected_titles)

            progress_bar.progress(75)
            status_text.text("📦 Compactando arquivos...")
            zip_buffer = create_zip_file(output_dir)

            progress_bar.progress(100)
            status_text.text("✅ Exportação concluída.")

            show_results(extractor.stats, selected_titles)
            st.download_button(
                label="📥 Baixar arquivos selecionados (ZIP)",
                data=zip_buffer.getvalue(),
                file_name=f"kindle_destaques_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                mime="application/zip",
                type="primary",
                use_container_width=True,
            )

        store = ProcessingStore(Path(".kindle_processing_store.json"))
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
        # Defer widget reset to the next run (before table render) to avoid
        # mutating instantiated widget keys in the current run.
        st.session_state[STATE_RESET_ROW_WIDGETS] = True
    except Exception as error:
        st.error(f"❌ Erro inesperado na exportação: {error}")
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
    st.success("🎉 Exportação concluída com sucesso!")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📚 Livros exportados", len(selected_titles))
    with col2:
        st.metric("📄 Entradas exportadas", stats["total_entries"])
    with col3:
        total_files = sum(stats["files_generated"].values())
        st.metric("📁 Arquivos gerados", total_files)

    if any(stats["files_generated"].values()):
        st.subheader("Arquivos gerados por formato")
        for format_name, count in stats["files_generated"].items():
            if count > 0:
                st.info(f"**{format_name.upper()}**: {count} arquivo(s)")


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


def reset_analysis_if_new_upload(current_analysis_id):
    previous_id = st.session_state.get(STATE_ANALYSIS_ID)
    if previous_id and previous_id != current_analysis_id:
        st.session_state.pop(STATE_ANALYSIS, None)
        st.session_state.pop(STATE_SELECTED_KEYS, None)
        st.session_state.pop(STATE_SELECTION_MAP, None)
        st.session_state.pop(STATE_RESET_ROW_WIDGETS, None)
        st.session_state.pop("selection_search_term", None)
        st.session_state.pop("selection_status_filter", None)
        st.session_state.pop("selection_author_filter", None)
        _clear_checkbox_widget_state()
        st.session_state[STATE_ANALYSIS_ID] = current_analysis_id


def render_help():
    st.markdown(
        """
### Como usar
1. Faça upload do arquivo `My Clippings.txt`.
2. Ajuste os formatos e opções na barra lateral.
3. Clique em **Analisar arquivo** para ver status por livro.
4. Selecione os livros e exporte apenas os marcados.

### Onde encontrar o arquivo no Kindle
- Conecte o Kindle ao computador via USB.
- Navegue até a pasta raiz do dispositivo.
- O arquivo `My Clippings.txt` fica na pasta principal.
"""
    )
