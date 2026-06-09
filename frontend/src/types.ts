export type AppConfig = {
  exportMarkdown: boolean;
  exportHtml: boolean;
  exportTxt: boolean;
  removeDuplicates: boolean;
  similarityThreshold: number;
  includeBookmarks: boolean;
  includeMetadata: boolean;
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
