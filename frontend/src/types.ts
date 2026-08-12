export type AppConfig = {
  exportMarkdown: boolean;
  exportHtml: boolean;
  exportTxt: boolean;
  removeDuplicates: boolean;
  similarityThreshold: number;
  /** Fracao de sobreposicao de posicao a partir da qual duas entradas sao a mesma. */
  dedupPositionOverlapRatio: number;
  /** Fracao de palavras em comum exigida quando as posicoes se sobrepoem. */
  dedupTokenOverlapThreshold: number;
  /** Janela em minutos para tratar destaques vizinhos como da mesma sessao. */
  dedupSessionWindowMinutes: number;
  includeBookmarks: boolean;
  includeMetadata: boolean;
  /** Exporta so as entradas ainda nao exportadas de cada livro. */
  exportOnlyNew: boolean;
};

export type BookRow = {
  book_key: string;
  title: string;
  author: string;
  highlights: number;
  notes: number;
  bookmarks: number;
  status: string;
  status_label: string;
  new_highlights_count: number;
  default_selected: boolean;
  last_analysis_display: string;
  last_export_display: string;
  last_export_formats?: string[];
};

export type BookEntry = {
  type: "highlight" | "note" | "bookmark" | "unknown";
  page: number | null;
  start_pos: number | null;
  end_pos: number | null;
  content: string;
  date_formatted: string;
};

export type BookEntriesResponse = {
  book_key: string;
  title: string;
  author: string;
  entries: BookEntry[];
};

export type StatusOption = {
  value: string;
  label: string;
};

export type AnalysisStats = {
  total_entries: number;
  duplicates_removed: number;
  books_processed: number;
  errors: number;
  files_generated: Record<string, number>;
};

export type AnalysisResponse = {
  analysisId: string;
  uploadedName: string;
  stats: AnalysisStats;
  rows: BookRow[];
  selectionMap: Record<string, boolean>;
  statusOptions: StatusOption[];
  authorOptions: string[];
};

export type ExportedBookFile = {
  filename: string;
  format: string;
  mimeType: string;
  contentBase64: string;
};

export type ExportBookFilesResponse = {
  files: ExportedBookFile[];
};

export type FilterState = {
  search: string;
  status: string;
  author: string;
  selectedOnly: boolean;
};

export type SelectionSummary = {
  selectedBooks: number;
  selectedHighlights: number;
  activeFormats: number;
};
