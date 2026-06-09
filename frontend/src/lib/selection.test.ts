import { describe, expect, it } from "vitest";

import {
  DEFAULT_CONFIG,
  applyBatchSelection,
  buildSelectionSummary,
  filterRows,
} from "./selection";
import type { BookRow } from "@/types";

const rows: BookRow[] = [
  {
    book_key: "a",
    title: "Blade Runner",
    author: "Dick, Philip K.",
    highlights: 2,
    notes: 1,
    bookmarks: 0,
    status: "novo",
    status_label: "Novo",
    new_highlights_count: 2,
    default_selected: true,
    last_analysis_display: "-",
    last_export_display: "-",
  },
  {
    book_key: "b",
    title: "A Morte de Ivan Ilitch",
    author: "Tolstoi, Leon",
    highlights: 1,
    notes: 0,
    bookmarks: 0,
    status: "sem_novidades",
    status_label: "Sem novidades",
    new_highlights_count: 0,
    default_selected: false,
    last_analysis_display: "-",
    last_export_display: "1 de janeiro de 2024",
  },
];

describe("selection helpers", () => {
  it("filters by search, status, author, and selected-only", () => {
    const selectionMap = { a: true, b: false };

    expect(
      filterRows(rows, selectionMap, {
        search: "philip",
        status: "todos",
        author: "Todos",
        selectedOnly: false,
      }).map((row) => row.book_key),
    ).toEqual(["a"]);

    expect(
      filterRows(rows, selectionMap, {
        search: "",
        status: "sem_novidades",
        author: "Tolstoi, Leon",
        selectedOnly: false,
      }).map((row) => row.book_key),
    ).toEqual(["b"]);

    expect(
      filterRows(rows, selectionMap, {
        search: "",
        status: "todos",
        author: "Todos",
        selectedOnly: true,
      }).map((row) => row.book_key),
    ).toEqual(["a"]);
  });

  it("applies batch actions only to visible rows", () => {
    const selectionMap = { a: false, b: false };

    expect(applyBatchSelection(rows, selectionMap, [rows[0]], "select_visible")).toEqual({
      a: true,
      b: false,
    });

    expect(applyBatchSelection(rows, { a: false, b: true }, rows, "recommended")).toEqual({
      a: true,
      b: false,
    });
  });

  it("summarizes selected books, highlights, and active formats", () => {
    expect(buildSelectionSummary(rows, { a: true, b: false }, DEFAULT_CONFIG)).toEqual({
      selectedBooks: 1,
      selectedHighlights: 2,
      activeFormats: 1,
    });
  });
});
