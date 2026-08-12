import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { toast } from "sonner";

import App from "./App";

vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
  },
}));

describe("App shell", () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.classList.remove("dark");
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("renders controls and keeps export disabled before analysis", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: /Kindle Highlights/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Analisar/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Exportar ZIP/i })).toBeDisabled();
    expect(screen.getByLabelText("Busca")).toBeInTheDocument();
    expect(screen.getByText("Status")).toBeInTheDocument();
    expect(screen.getByText("Autor")).toBeInTheDocument();
  });

  it("updates format controls", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByLabelText("HTML"));

    expect(screen.getByText("Markdown / HTML")).toBeInTheDocument();
  });

  it("persists dark theme selection", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "Alternar tema" }));

    expect(document.documentElement).toHaveClass("dark");
    expect(window.localStorage.getItem("kindle-notes-theme")).toBe("dark");
  });

  it("updates the row after individual download without reanalyzing", async () => {
    const user = userEvent.setup();
    window.URL.createObjectURL = vi.fn();
    window.URL.revokeObjectURL = vi.fn();
    vi.spyOn(window.URL, "createObjectURL").mockReturnValue("blob:download");
    vi.spyOn(window.URL, "revokeObjectURL").mockImplementation(() => {});
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            analysisId: "analysis-1",
            uploadedName: "My Clippings.txt",
            stats: {
              total_entries: 1,
              duplicates_removed: 0,
              books_processed: 1,
              errors: 0,
              files_generated: {},
            },
            rows: [
              {
                book_key: "book-1",
                title: "Livro A",
                author: "Autor A",
                highlights: 4,
                notes: 2,
                bookmarks: 3,
                status: "com_novidades",
                status_label: "Alterado",
                new_highlights_count: 1,
                default_selected: true,
                last_analysis_display: "2026-06-08 21:30",
                last_export_display: "2026-06-08 20:30",
              },
            ],
            selectionMap: { "book-1": true },
            statusOptions: [
              { value: "todos", label: "Todos" },
              { value: "com_novidades", label: "Alterado" },
              { value: "sem_novidades", label: "Exportado" },
            ],
            authorOptions: ["Autor A"],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            files: [
              {
                filename: "livro-a.md",
                format: "markdown",
                mimeType: "text/markdown; charset=utf-8",
                contentBase64: window.btoa("# Livro A"),
              },
            ],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    const { container } = render(<App />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;

    await user.upload(input, new File(["content"], "My Clippings.txt", { type: "text/plain" }));
    await user.click(screen.getByRole("button", { name: /Analisar/i }));
    expect(await screen.findByText("Alterado")).toBeInTheDocument();

    await user.click(await screen.findByRole("button", { name: "Baixar Livro A" }));

    expect(await screen.findByText("Exportado")).toBeInTheDocument();
    expect(screen.queryByText("2026-06-08 20:30")).not.toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "0" })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/analyze");
    expect(fetchMock.mock.calls[1][0]).toBe("/api/export/book");
  });

  it("opens the reading panel and filters entries by text and type", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            analysisId: "analysis-1",
            uploadedName: "My Clippings.txt",
            stats: {
              total_entries: 2,
              duplicates_removed: 0,
              books_processed: 1,
              errors: 0,
              files_generated: {},
            },
            rows: [
              {
                book_key: "book-1",
                title: "Livro A",
                author: "Autor A",
                highlights: 1,
                notes: 1,
                bookmarks: 0,
                status: "novo",
                status_label: "Novo",
                new_highlights_count: 1,
                default_selected: true,
                last_analysis_display: "-",
                last_export_display: "-",
              },
            ],
            selectionMap: { "book-1": true },
            statusOptions: [{ value: "todos", label: "Todos" }],
            authorOptions: ["Autor A"],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            book_key: "book-1",
            title: "Livro A",
            author: "Autor A",
            entries: [
              {
                type: "highlight",
                page: 12,
                start_pos: 200,
                end_pos: 205,
                content: "O tempo é a substância de que sou feito.",
                date_formatted: "2 de fevereiro de 2024",
              },
              {
                type: "note",
                page: 12,
                start_pos: 206,
                end_pos: 206,
                content: "Revisar depois.",
                date_formatted: "2 de fevereiro de 2024",
              },
            ],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    const { container } = render(<App />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;

    await user.upload(input, new File(["content"], "My Clippings.txt", { type: "text/plain" }));
    await user.click(screen.getByRole("button", { name: /Analisar/i }));

    await user.click(await screen.findByRole("button", { name: /Ler destaques de Livro A/i }));

    expect(await screen.findByText(/O tempo é a substância/)).toBeInTheDocument();
    expect(screen.getByText("Revisar depois.")).toBeInTheDocument();
    expect(screen.getByText("Página 12 · Posição 200-205 · 2 de fevereiro de 2024")).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText(/Buscar no texto/i), "substância");
    expect(screen.queryByText("Revisar depois.")).not.toBeInTheDocument();

    await user.clear(screen.getByPlaceholderText(/Buscar no texto/i));
    await user.click(screen.getByRole("tab", { name: "Notas" }));

    expect(screen.getByText("Revisar depois.")).toBeInTheDocument();
    expect(screen.queryByText(/O tempo é a substância/)).not.toBeInTheDocument();
  });

  it("shows compact status labels and friendly stale-server download errors", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            analysisId: "analysis-1",
            uploadedName: "My Clippings.txt",
            stats: {
              total_entries: 4,
              duplicates_removed: 0,
              books_processed: 4,
              errors: 0,
              files_generated: {},
            },
            rows: [
              {
                book_key: "changed",
                title: "Livro Alterado",
                author: "Autor A",
                highlights: 2,
                notes: 0,
                bookmarks: 0,
                status: "com_novidades",
                status_label: "Alterado",
                new_highlights_count: 1,
                default_selected: true,
                last_analysis_display: "2026-06-08 21:40",
                last_export_display: "2026-06-08 20:40",
              },
              {
                book_key: "pending",
                title: "Livro Pendente",
                author: "Autor B",
                highlights: 1,
                notes: 0,
                bookmarks: 0,
                status: "nunca_exportado",
                status_label: "Pendente",
                new_highlights_count: 1,
                default_selected: true,
                last_analysis_display: "2026-06-08 21:40",
                last_export_display: "-",
              },
              {
                book_key: "exported",
                title: "Livro Exportado",
                author: "Autor C",
                highlights: 1,
                notes: 0,
                bookmarks: 0,
                status: "sem_novidades",
                status_label: "Exportado",
                new_highlights_count: 0,
                default_selected: false,
                last_analysis_display: "2026-06-08 21:40",
                last_export_display: "2026-06-08 21:00",
              },
            ],
            selectionMap: { changed: true, pending: true, exported: false },
            statusOptions: [
              { value: "todos", label: "Todos" },
              { value: "novo", label: "Novo" },
              { value: "com_novidades", label: "Alterado" },
              { value: "nunca_exportado", label: "Pendente" },
              { value: "sem_novidades", label: "Exportado" },
            ],
            authorOptions: ["Autor A", "Autor B", "Autor C"],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(new Response("Method Not Allowed", { status: 405 }));
    const { container } = render(<App />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;

    await user.upload(input, new File(["content"], "My Clippings.txt", { type: "text/plain" }));
    await user.click(screen.getByRole("button", { name: /Analisar/i }));

    expect(await screen.findByText("Alterado")).toBeInTheDocument();
    expect(screen.getByText("Pendente")).toBeInTheDocument();
    expect(screen.getByText("Exportado")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Baixar Livro Alterado" }));

    expect(toast.error).toHaveBeenCalledWith(
      "Servidor desatualizado. Reinicie a API e tente novamente.",
    );
  });
});
