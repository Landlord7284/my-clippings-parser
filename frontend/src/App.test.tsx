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
    vi.restoreAllMocks();
  });

  it("renders controls and keeps export disabled before analysis", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: /Extrator de Destaques Kindle/i })).toBeInTheDocument();
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

  it("shows row download actions after analysis", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
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
              highlights: 1,
              notes: 0,
              bookmarks: 0,
              status: "novo",
              status_label: "Novo",
              new_highlights_count: 1,
              default_selected: true,
              last_analysis_display: "2026-06-08 21:40",
              last_export_display: "-",
            },
          ],
          selectionMap: { "book-1": true },
          statusOptions: [{ value: "todos", label: "Todos" }, { value: "novo", label: "Novo" }],
          authorOptions: ["Autor A"],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    const { container } = render(<App />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;

    await user.upload(input, new File(["content"], "My Clippings.txt", { type: "text/plain" }));
    await user.click(screen.getByRole("button", { name: /Analisar/i }));

    expect(await screen.findByRole("button", { name: "Baixar Livro A" })).toBeInTheDocument();
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
                status_label: "Alterados",
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
              { value: "com_novidades", label: "Alterados" },
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

    expect(await screen.findByText("Alterados")).toBeInTheDocument();
    expect(screen.getByText("Pendente")).toBeInTheDocument();
    expect(screen.getByText("Exportado")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Baixar Livro Alterado" }));

    expect(toast.error).toHaveBeenCalledWith(
      "Servidor desatualizado. Reinicie a API e tente novamente.",
    );
  });
});
