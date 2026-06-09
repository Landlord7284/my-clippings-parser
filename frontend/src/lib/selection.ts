import type { AppConfig, BookRow, FilterState, SelectionSummary } from "@/types";

export const DEFAULT_CONFIG: AppConfig = {
  exportMarkdown: true,
  exportHtml: false,
  exportTxt: false,
  removeDuplicates: true,
  similarityThreshold: 0.8,
  includeBookmarks: true,
  includeMetadata: true,
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
  return labels;
}

export function activeFormatValues(config: AppConfig) {
  const values = [];
  if (config.exportMarkdown) values.push("markdown");
  if (config.exportHtml) values.push("html");
  if (config.exportTxt) values.push("txt");
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

export function buildSelectionSummary(
  rows: BookRow[],
  selectionMap: Record<string, boolean>,
  config: AppConfig,
): SelectionSummary {
  const selectedRows = rows.filter((row) => selectionMap[row.book_key]);
  return {
    selectedBooks: selectedRows.length,
    selectedHighlights: selectedRows.reduce((total, row) => total + row.highlights, 0),
    activeFormats: activeFormatLabels(config).length,
  };
}
