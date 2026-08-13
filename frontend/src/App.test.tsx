import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { toast } from "sonner";

import App from "./App";
import { DEFAULT_CONFIG } from "@/lib/selection";

function bookRow(overrides: Record<string, unknown> = {}) {
  return {
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
    ...overrides,
  };
}

function analysisPayload(overrides: Record<string, unknown> = {}) {
  const rows = (overrides.rows as ReturnType<typeof bookRow>[]) ?? [bookRow()];
  return {
    analysisId: "analysis-1",
    uploadedName: "My Clippings.txt",
    stats: {
      total_entries: 1,
      duplicates_removed: 0,
      books_processed: rows.length,
      errors: 0,
      files_generated: {},
    },
    selectionMap: Object.fromEntries(
      rows.map((row) => [row.book_key, Boolean(row.default_selected)]),
    ),
    statusOptions: [
      { value: "todos", label: "Todos" },
      { value: "novo", label: "Novo" },
      { value: "com_novidades", label: "Alterado" },
      { value: "nunca_exportado", label: "Pendente" },
      { value: "sem_novidades", label: "Exportado" },
    ],
    authorOptions: [...new Set(rows.map((row) => String(row.author)))],
    ...overrides,
    rows,
  };
}

function bookEntriesPayload(entries: Record<string, unknown>[] = []) {
  return { book_key: "book-1", title: "Livro A", author: "Autor A", entries };
}

const LATEST_URL = "/api/analysis/latest";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/**
 * O app pede a ultima analise ao montar, antes de qualquer acao do teste.
 * Rotear por URL evita que essa chamada consuma a fila ordenada de respostas.
 */
function mockApi(queue: Array<() => Response>, latest: (() => Response) | null = null) {
  const pending = [...queue];
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url === LATEST_URL) {
      return latest ? latest() : new Response(null, { status: 404 });
    }
    const next = pending.shift();
    if (!next) throw new Error(`Chamada inesperada: ${url}`);
    return next();
  });
}

/** URLs pedidas pelo teste, sem a busca automatica do mount. */
function apiCalls(fetchMock: { mock: { calls: unknown[][] } }) {
  return fetchMock.mock.calls.map((call) => String(call[0])).filter((url) => url !== LATEST_URL);
}

async function analyze(user: ReturnType<typeof userEvent.setup>, container: HTMLElement) {
  const input = container.querySelector('input[type="file"]') as HTMLInputElement;
  await user.upload(input, new File(["content"], "My Clippings.txt", { type: "text/plain" }));
  await user.click(screen.getByRole("button", { name: /Analisar/i }));
}

vi.mock("sonner", () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
  },
}));

describe("App shell", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    document.documentElement.classList.remove("dark");
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("renders controls and keeps export disabled before analysis", () => {
    mockApi([]);
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
    mockApi([]);
    render(<App />);

    await user.click(screen.getByLabelText("HTML"));

    expect(screen.getByText("Markdown / HTML")).toBeInTheDocument();
  });

  it("persists dark theme selection", async () => {
    const user = userEvent.setup();
    mockApi([]);
    render(<App />);

    await user.click(screen.getByRole("button", { name: "Alternar tema" }));

    expect(document.documentElement).toHaveClass("dark");
    expect(window.localStorage.getItem("kindle-notes-theme")).toBe("dark");
  });

  it("updates the row after individual download without reanalyzing", async () => {
    const user = userEvent.setup();
    // jsdom nao implementa nenhum dos dois: precisam existir antes do spy.
    window.URL.createObjectURL = vi.fn();
    window.URL.revokeObjectURL = vi.fn();
    vi.spyOn(window.URL, "createObjectURL").mockReturnValue("blob:download");
    vi.spyOn(window.URL, "revokeObjectURL").mockImplementation(() => {});
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    const fetchMock = mockApi([
      () => jsonResponse(analysisPayload()),
      () =>
        jsonResponse({
          files: [
            {
              filename: "livro-a.md",
              format: "markdown",
              mimeType: "text/markdown; charset=utf-8",
              contentBase64: window.btoa("# Livro A"),
            },
          ],
        }),
    ]);
    const { container } = render(<App />);

    await analyze(user, container);
    expect(await screen.findByText("Alterado")).toBeInTheDocument();

    await user.click(await screen.findByRole("button", { name: "Baixar Livro A" }));

    expect(await screen.findByText("Exportado")).toBeInTheDocument();
    expect(screen.queryByText("2026-06-08 20:30")).not.toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "0" })).toBeInTheDocument();
    expect(apiCalls(fetchMock)).toEqual(["/api/analyze", "/api/export/book"]);
  });

  it("opens the reading panel and filters entries by text and type", async () => {
    const user = userEvent.setup();
    mockApi([
      () => jsonResponse(analysisPayload({ rows: [bookRow({ status: "novo", status_label: "Novo" })] })),
      () =>
        jsonResponse(
          bookEntriesPayload([
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
          ]),
        ),
    ]);
    const { container } = render(<App />);

    await analyze(user, container);
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
    mockApi([
      () =>
        jsonResponse(
          analysisPayload({
            rows: [
              bookRow({ book_key: "changed", title: "Livro Alterado", highlights: 2, notes: 0, bookmarks: 0 }),
              bookRow({
                book_key: "pending",
                title: "Livro Pendente",
                author: "Autor B",
                highlights: 1,
                notes: 0,
                bookmarks: 0,
                status: "nunca_exportado",
                status_label: "Pendente",
                last_export_display: "-",
              }),
              bookRow({
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
                last_export_display: "2026-06-08 21:00",
              }),
            ],
          }),
        ),
      () => new Response("Method Not Allowed", { status: 405 }),
    ]);
    const { container } = render(<App />);

    await analyze(user, container);

    expect(await screen.findByText("Alterado")).toBeInTheDocument();
    expect(screen.getByText("Pendente")).toBeInTheDocument();
    expect(screen.getByText("Exportado")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Baixar Livro Alterado" }));

    expect(toast.error).toHaveBeenCalledWith(
      "Servidor desatualizado. Reinicie a API e tente novamente.",
    );
  });

  it("carries the metadata toggle into the clip page link", async () => {
    const user = userEvent.setup();
    mockApi([
      () => jsonResponse(analysisPayload()),
      () => jsonResponse(bookEntriesPayload()),
      () => jsonResponse(bookEntriesPayload()),
    ]);
    const { container } = render(<App />);

    await analyze(user, container);
    await user.click(await screen.findByRole("button", { name: /Ler destaques de Livro A/i }));

    expect(await screen.findByRole("link", { name: /Página de recorte/i })).toHaveAttribute(
      "href",
      "/clip/analysis-1/book-1",
    );

    // O painel e um dialog: fecha antes de mexer nos ajustes atras dele.
    await user.keyboard("{Escape}");
    await user.click(screen.getByLabelText("Metadados"));
    await user.click(await screen.findByRole("button", { name: /Ler destaques de Livro A/i }));

    expect(await screen.findByRole("link", { name: /Página de recorte/i })).toHaveAttribute(
      "href",
      "/clip/analysis-1/book-1?metadata=false",
    );
  });

  it("restores the analysis after a reload without asking for the file again", async () => {
    const user = userEvent.setup();
    const fetchMock = mockApi([() => jsonResponse(analysisPayload())]);
    const first = render(<App />);

    await analyze(user, first.container);
    expect(await screen.findByText("Livro A")).toBeInTheDocument();

    first.unmount();
    render(<App />);

    expect(await screen.findByText("Livro A")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Exportar ZIP/i })).toBeEnabled();
    expect(apiCalls(fetchMock)).toEqual(["/api/analyze"]);
  });

  it("loads the last analysis from the server when the tab has no session", async () => {
    const fetchMock = mockApi([], () => jsonResponse(analysisPayload()));
    render(<App />);

    expect(await screen.findByText("Livro A")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Exportar ZIP/i })).toBeEnabled();
    expect(fetchMock.mock.calls.map((call) => String(call[0]))).toEqual([LATEST_URL]);
  });

  it("does not ask the server for the last analysis when the tab already has one", async () => {
    window.sessionStorage.setItem(
      "kindle-notes-session",
      JSON.stringify({
        version: 1,
        analysis: analysisPayload(),
        selectionMap: { "book-1": true },
        config: DEFAULT_CONFIG,
      }),
    );
    const fetchMock = mockApi([]);
    render(<App />);

    expect(await screen.findByText("Livro A")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("drops the restored session when the backend no longer has the analysis", async () => {
    const user = userEvent.setup();
    window.sessionStorage.setItem(
      "kindle-notes-session",
      JSON.stringify({
        version: 1,
        analysis: analysisPayload(),
        selectionMap: { "book-1": true },
        config: DEFAULT_CONFIG,
      }),
    );
    mockApi([() => jsonResponse({ detail: "Analysis not found." }, 409)]);
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "Baixar Livro A" }));

    expect(toast.error).toHaveBeenCalledWith(
      "A análise expirou no servidor. Envie o arquivo novamente.",
    );
    expect(screen.queryByText("Livro A")).not.toBeInTheDocument();
    expect(window.sessionStorage.getItem("kindle-notes-session")).toBeNull();
  });
});
