import type { AppConfig, BookRow, FilterState, SelectionSummary } from "@/types";

export const DEFAULT_CONFIG: AppConfig = {
  exportMarkdown: true,
  exportHtml: false,
  exportTxt: false,
  exportObsidian: false,
  removeDuplicates: true,
  similarityThreshold: 0.8,
  dedupPositionOverlapRatio: 0.6,
  dedupTokenOverlapThreshold: 0.75,
  dedupSessionWindowMinutes: 15,
  includeBookmarks: true,
  includeMetadata: true,
  exportOnlyNew: false,
};

export const DEFAULT_FILTERS: FilterState = {
  search: "",
  status: "todos",
  author: "Todos",
  selectedOnly: false,
};

export function activeFormatLabels(config: AppConfig) {
  const labels = [];
  if (config.exportMarkdown) labels.push("Markdown");
  if (config.exportHtml) labels.push("HTML");
  if (config.exportTxt) labels.push("TXT");
  if (config.exportObsidian) labels.push("Obsidian");
  return labels;
}

export function activeFormatValues(config: AppConfig) {
  const values = [];
  if (config.exportMarkdown) values.push("markdown");
  if (config.exportHtml) values.push("html");
  if (config.exportTxt) values.push("txt");
  if (config.exportObsidian) values.push("obsidian");
  return values;
}

export function filterRows(
  rows: BookRow[],
  selectionMap: Record<string, boolean>,
  filters: FilterState,
) {
  const normalizedSearch = filters.search.trim().toLowerCase();
  return rows.filter((row) => {
    const isSelected = Boolean(selectionMap[row.book_key]);
    const titleAuthor = `${row.title} ${row.author}`.toLowerCase();

    if (normalizedSearch && !titleAuthor.includes(normalizedSearch)) return false;
    if (filters.author !== "Todos" && row.author !== filters.author) return false;
    if (filters.selectedOnly && !isSelected) return false;
    if (filters.status === "selecionados" && !isSelected) return false;
    if (!["todos", "selecionados"].includes(filters.status) && row.status !== filters.status) {
      return false;
    }
    return true;
  });
}

export function applyBatchSelection(
  rows: BookRow[],
  selectionMap: Record<string, boolean>,
  visibleRows: BookRow[],
  action: "recommended" | "select_visible" | "clear_visible",
) {
  const next = { ...selectionMap };
  const rowByKey = new Map(rows.map((row) => [row.book_key, row]));

  for (const visibleRow of visibleRows) {
    const row = rowByKey.get(visibleRow.book_key);
    if (!row) continue;
    if (action === "recommended") next[row.book_key] = Boolean(row.default_selected);
    if (action === "select_visible") next[row.book_key] = true;
    if (action === "clear_visible") next[row.book_key] = false;
  }

  return next;
}

export function markRowsExported(
  rows: BookRow[],
  exportedKeys: string[],
  activeFormats: string[],
  lastExportDisplay: string,
): BookRow[] {
  const exported = new Set(exportedKeys);
  return rows.map((row) =>
    exported.has(row.book_key)
      ? {
        ...row,
        status: "sem_novidades",
        status_label: "Exportado",
        new_highlights_count: 0,
        last_export_display: lastExportDisplay,
        last_export_formats: activeFormats,
      }
      : row,
  );
}

export function buildSelectionSummary(
  rows: BookRow[],
  selectionMap: Record<string, boolean>,
  config: AppConfig,
): SelectionSummary {
  const selectedRows = rows.filter((row) => selectionMap[row.book_key]);
  return {
    selectedBooks: selectedRows.length,
    selectedHighlights: selectedRows.reduce(
      (total, row) => total + (config.exportOnlyNew ? row.new_highlights_count : row.highlights),
      0,
    ),
    activeFormats: activeFormatLabels(config).length,
  };
}
