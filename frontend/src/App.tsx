import { useEffect, useMemo, useRef, useState } from "react";
import {
  CheckCheck,
  Download,
  FileArchive,
  Filter,
  Moon,
  RefreshCw,
  Search,
  Settings2,
  Sun,
  Upload,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";

import { analyzeFile, exportBookFiles, exportBooks, fetchBookEntries } from "@/lib/api";
import {
  DEFAULT_CONFIG,
  DEFAULT_FILTERS,
  activeFormatLabels,
  activeFormatValues,
  applyBatchSelection,
  buildSelectionSummary,
  filterRows,
  markRowsExported,
} from "@/lib/selection";
import type {
  AnalysisResponse,
  AppConfig,
  BookEntriesResponse,
  BookEntry,
  BookRow,
  FilterState,
} from "@/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Slider } from "@/components/ui/slider";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

const FALLBACK_STATUS_OPTIONS = [
  { value: "todos", label: "Todos" },
  { value: "novo", label: "Novo" },
  { value: "nunca_exportado", label: "Pendente" },
  { value: "com_novidades", label: "Alterado" },
  { value: "sem_novidades", label: "Exportado" },
  { value: "selecionados", label: "Selecionado" },
];

const STATUS_DISPLAY_LABELS: Record<string, string> = {
  novo: "Novo",
  nunca_exportado: "Pendente",
  com_novidades: "Alterado",
  sem_novidades: "Exportado",
  selecionados: "Selecionado",
};

function getStatusDisplayLabel(value: string, label?: string) {
  return STATUS_DISPLAY_LABELS[value] ?? label ?? value;
}

const statusVariant: Record<string, "green" | "amber" | "blue" | "gray"> = {
  novo: "green",
  nunca_exportado: "amber",
  com_novidades: "blue",
  sem_novidades: "gray",
};

const THEME_STORAGE_KEY = "kindle-notes-theme";

type Theme = "light" | "dark";

function getInitialTheme(): Theme {
  if (typeof window === "undefined") return "light";
  return window.localStorage.getItem(THEME_STORAGE_KEY) === "dark" ? "dark" : "light";
}

function SettingsPanel({
  config,
  onChange,
}: {
  config: AppConfig;
  onChange: (config: AppConfig) => void;
}) {
  const setValue = <K extends keyof AppConfig>(key: K, value: AppConfig[K]) => {
    onChange({ ...config, [key]: value });
  };

  return (
    <aside className="flex h-full flex-col gap-5 rounded-md border bg-card p-4">
      <div className="flex items-center gap-2">
        <Settings2 className="h-4 w-4 text-primary" />
        <h2 className="text-sm font-semibold">Configurações</h2>
      </div>

      <section className="space-y-3">
        <h3 className="text-xs font-semibold uppercase text-muted-foreground">Formatos</h3>
        <ToggleRow
          id="markdown"
          label="Markdown"
          checked={config.exportMarkdown}
          onCheckedChange={(checked) => setValue("exportMarkdown", checked)}
        />
        <ToggleRow
          id="html"
          label="HTML"
          checked={config.exportHtml}
          onCheckedChange={(checked) => setValue("exportHtml", checked)}
        />
        <ToggleRow
          id="txt"
          label="TXT"
          checked={config.exportTxt}
          onCheckedChange={(checked) => setValue("exportTxt", checked)}
        />
      </section>

      <Separator />

      <section className="space-y-3">
        <h3 className="text-xs font-semibold uppercase text-muted-foreground">Processamento</h3>
        <ToggleRow
          id="dedup"
          label="Remover duplicatas"
          checked={config.removeDuplicates}
          onCheckedChange={(checked) => setValue("removeDuplicates", checked)}
        />
        <ToggleRow
          id="bookmarks"
          label="Marcadores"
          checked={config.includeBookmarks}
          onCheckedChange={(checked) => setValue("includeBookmarks", checked)}
        />
        <ToggleRow
          id="metadata"
          label="Metadados"
          checked={config.includeMetadata}
          onCheckedChange={(checked) => setValue("includeMetadata", checked)}
        />
        <ToggleRow
          id="only-new"
          label="Só novidades"
          hint="Exporta apenas as entradas que ainda não saíram no export anterior de cada livro."
          checked={config.exportOnlyNew}
          onCheckedChange={(checked) => setValue("exportOnlyNew", checked)}
        />
      </section>

      <Separator />

      <section className="space-y-4">
        <h3 className="text-xs font-semibold uppercase text-muted-foreground">Deduplicação</h3>
        <SliderRow
          id="position-overlap"
          label="Sobreposição de posição"
          hint="Quanto duas passagens precisam se sobrepor para contarem como a mesma."
          min={0.3}
          max={1}
          step={0.05}
          disabled={!config.removeDuplicates}
          value={config.dedupPositionOverlapRatio}
          format={(value) => value.toFixed(2)}
          onChange={(value) => setValue("dedupPositionOverlapRatio", value)}
        />
        <SliderRow
          id="token-overlap"
          label="Palavras em comum"
          hint="Fração de palavras compartilhadas exigida quando as posições se sobrepõem."
          min={0.5}
          max={1}
          step={0.05}
          disabled={!config.removeDuplicates}
          value={config.dedupTokenOverlapThreshold}
          format={(value) => value.toFixed(2)}
          onChange={(value) => setValue("dedupTokenOverlapThreshold", value)}
        />
        <SliderRow
          id="session-window"
          label="Janela de sessão"
          hint="Destaques feitos nesse intervalo são tratados como da mesma leitura."
          min={0}
          max={60}
          step={5}
          disabled={!config.removeDuplicates}
          value={config.dedupSessionWindowMinutes}
          format={(value) => `${value} min`}
          onChange={(value) => setValue("dedupSessionWindowMinutes", value)}
        />

        <div className="space-y-4 border-t pt-3">
          <h4 className="text-xs font-medium text-muted-foreground">Avançado</h4>
          <SliderRow
            id="similarity"
            label="Similaridade"
            hint="Só entra em jogo quando falta posição nas entradas comparadas."
            min={0.5}
            max={1}
            step={0.05}
            disabled={!config.removeDuplicates}
            value={config.similarityThreshold}
            format={(value) => value.toFixed(2)}
            onChange={(value) => setValue("similarityThreshold", value)}
          />
        </div>
      </section>
    </aside>
  );
}

function SliderRow({
  id,
  label,
  hint,
  min,
  max,
  step,
  value,
  disabled,
  format,
  onChange,
}: {
  id: string;
  label: string;
  hint: string;
  min: number;
  max: number;
  step: number;
  value: number;
  disabled?: boolean;
  format: (value: number) => string;
  onChange: (value: number) => void;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3">
        <Tooltip>
          <TooltipTrigger asChild>
            <Label htmlFor={id} className="cursor-help text-sm font-normal">
              {label}
            </Label>
          </TooltipTrigger>
          <TooltipContent className="max-w-56">{hint}</TooltipContent>
        </Tooltip>
        <span className="tabular-nums text-sm text-muted-foreground">{format(value)}</span>
      </div>
      <Slider
        id={id}
        min={min}
        max={max}
        step={step}
        disabled={disabled}
        value={[value]}
        onValueChange={([next]) => onChange(next)}
      />
    </div>
  );
}

function ToggleRow({
  id,
  label,
  hint,
  checked,
  onCheckedChange,
}: {
  id: string;
  label: string;
  hint?: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
}) {
  const labelNode = (
    <Label htmlFor={id} className={hint ? "cursor-help text-sm font-normal" : "text-sm font-normal"}>
      {label}
    </Label>
  );

  return (
    <div className="flex min-h-8 items-center justify-between gap-3">
      {hint ? (
        <Tooltip>
          <TooltipTrigger asChild>{labelNode}</TooltipTrigger>
          <TooltipContent className="max-w-56">{hint}</TooltipContent>
        </Tooltip>
      ) : (
        labelNode
      )}
      <Checkbox
        id={id}
        checked={checked}
        onCheckedChange={(value) => onCheckedChange(Boolean(value))}
      />
    </div>
  );
}

function MetricsStrip({
  analysis,
  summary,
  activeFormats,
  onlyNew,
}: {
  analysis: AnalysisResponse | null;
  summary: ReturnType<typeof buildSelectionSummary>;
  activeFormats: string[];
  onlyNew: boolean;
}) {
  const metrics = [
    ["Entradas", analysis?.stats.total_entries ?? "-"],
    ["Livros", analysis?.stats.books_processed ?? "-"],
    ["Selecionado", summary.selectedBooks],
    [onlyNew ? "Highlights novos" : "Highlights", summary.selectedHighlights],
    ["Formatos", activeFormats.length ? activeFormats.join(" / ") : "Nenhum"],
  ];

  return (
    <section className="grid gap-2 sm:grid-cols-2 xl:grid-cols-5">
      {metrics.map(([label, value]) => (
        <div className="metric-cell" key={label}>
          <div className="text-xs font-medium text-muted-foreground">{label}</div>
          <div className="mt-1 truncate text-lg font-semibold">{value}</div>
        </div>
      ))}
    </section>
  );
}

const ENTRY_TYPE_TABS = [
  { value: "all", label: "Tudo" },
  { value: "highlight", label: "Destaques" },
  { value: "note", label: "Notas" },
  { value: "bookmark", label: "Marcadores" },
] as const;

type EntryTypeFilter = (typeof ENTRY_TYPE_TABS)[number]["value"];

function entryLocation(entry: BookEntry) {
  const parts: string[] = [];
  if (entry.page !== null) parts.push(`Página ${entry.page}`);
  if (entry.start_pos !== null && entry.end_pos !== null) {
    parts.push(
      entry.start_pos === entry.end_pos
        ? `Posição ${entry.start_pos}`
        : `Posição ${entry.start_pos}-${entry.end_pos}`,
    );
  }
  if (entry.date_formatted) parts.push(entry.date_formatted);
  return parts.join(" · ");
}

function BookEntriesPanel({
  book,
  isLoading,
  onOpenChange,
}: {
  book: BookEntriesResponse | null;
  isLoading: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<EntryTypeFilter>("all");

  useEffect(() => {
    setSearch("");
    setTypeFilter("all");
  }, [book?.book_key]);

  const entries = book?.entries ?? [];
  const visibleEntries = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return entries.filter((entry) => {
      if (typeFilter !== "all" && entry.type !== typeFilter) return false;
      if (needle && !entry.content.toLowerCase().includes(needle)) return false;
      return true;
    });
  }, [entries, search, typeFilter]);

  return (
    <Sheet open={Boolean(book) || isLoading} onOpenChange={onOpenChange}>
      <SheetContent className="flex w-full flex-col gap-4 sm:max-w-2xl">
        <SheetHeader>
          <SheetTitle className="pr-6 text-left">{book?.title ?? "Carregando…"}</SheetTitle>
          {book ? (
            <p className="text-left text-sm text-muted-foreground">{book.author}</p>
          ) : null}
        </SheetHeader>

        <div className="space-y-3">
          <Input
            placeholder="Buscar no texto dos destaques…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          <Tabs value={typeFilter} onValueChange={(value) => setTypeFilter(value as EntryTypeFilter)}>
            <TabsList className="w-full">
              {ENTRY_TYPE_TABS.map((tab) => (
                <TabsTrigger key={tab.value} value={tab.value} className="flex-1">
                  {tab.label}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
          <p className="text-xs text-muted-foreground">
            {visibleEntries.length} de {entries.length}
          </p>
        </div>

        <div className="-mr-2 flex-1 space-y-3 overflow-y-auto pr-2">
          {isLoading ? <p className="text-sm text-muted-foreground">Carregando…</p> : null}

          {!isLoading && !visibleEntries.length ? (
            <p className="text-sm text-muted-foreground">Nada encontrado.</p>
          ) : null}

          {visibleEntries.map((entry, index) => (
            <article
              key={`${entry.start_pos}-${entry.end_pos}-${index}`}
              className={
                entry.type === "note"
                  ? "rounded-md border-l-4 border-l-amber-400 bg-muted/40 p-3"
                  : "rounded-md border-l-4 border-l-transparent bg-muted/40 p-3"
              }
            >
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                {entry.type !== "highlight" ? (
                  <Badge variant="gray">
                    {entry.type === "note" ? "Nota" : entry.type === "bookmark" ? "Marcador" : "?"}
                  </Badge>
                ) : null}
                <span>{entryLocation(entry)}</span>
              </div>
              {entry.content ? (
                <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed">{entry.content}</p>
              ) : null}
            </article>
          ))}
        </div>
      </SheetContent>
    </Sheet>
  );
}

function BookTable({
  rows,
  visibleRows,
  selectionMap,
  onSelectionChange,
  onBookDownload,
  onBookOpen,
  downloadingBookKey,
  canDownload,
}: {
  rows: BookRow[];
  visibleRows: BookRow[];
  selectionMap: Record<string, boolean>;
  onSelectionChange: (selectionMap: Record<string, boolean>) => void;
  onBookDownload: (row: BookRow) => void;
  onBookOpen: (row: BookRow) => void;
  downloadingBookKey: string | null;
  canDownload: boolean;
}) {
  const visibleSelected = visibleRows.filter((row) => selectionMap[row.book_key]).length;
  const allVisibleSelected = visibleRows.length > 0 && visibleSelected === visibleRows.length;
  const headerChecked = allVisibleSelected ? true : visibleSelected > 0 ? "indeterminate" : false;

  const toggleVisible = (checked: boolean) => {
    const next = { ...selectionMap };
    for (const row of visibleRows) next[row.book_key] = checked;
    onSelectionChange(next);
  };

  if (!rows.length) {
    return (
      <div className="rounded-md border bg-card p-5 text-sm text-muted-foreground">
        Sem análise.
      </div>
    );
  }

  return (
    <div className="max-w-full overflow-hidden rounded-md border bg-card">
      <Table className="table-fixed">
        <colgroup>
          <col className="w-[40px]" />
          <col />
          <col className="w-[104px]" />
          <col className="w-[86px]" />
          <col className="w-[58px]" />
          <col className="w-[92px]" />
          <col className="w-[58px]" />
          <col className="w-[112px]" />
          <col className="w-[48px]" />
        </colgroup>
        <TableHeader>
          <TableRow>
            <TableHead>
              <Checkbox
                checked={headerChecked}
                aria-label="Selecionar visíveis"
                onCheckedChange={(checked) => toggleVisible(Boolean(checked))}
              />
            </TableHead>
            <TableHead>Livro</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Destaques</TableHead>
            <TableHead className="text-right">Notas</TableHead>
            <TableHead className="text-right">Marcadores</TableHead>
            <TableHead className="text-right">Novos</TableHead>
            <TableHead>Data Export</TableHead>
            <TableHead className="px-1" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {visibleRows.map((row) => (
            <TableRow key={row.book_key}>
              <TableCell>
                <Checkbox
                  checked={Boolean(selectionMap[row.book_key])}
                  aria-label={`Selecionar ${row.title}`}
                  onCheckedChange={(checked) =>
                    onSelectionChange({ ...selectionMap, [row.book_key]: Boolean(checked) })
                  }
                />
              </TableCell>
              <TableCell className="max-w-0">
                <button
                  type="button"
                  className="min-w-0 max-w-full text-left hover:underline"
                  onClick={() => onBookOpen(row)}
                  aria-label={`Ler destaques de ${row.title}`}
                >
                  <div className="truncate font-medium">{row.title}</div>
                  <div className="truncate text-xs text-muted-foreground">{row.author}</div>
                </button>
              </TableCell>
              <TableCell>
                <Badge variant={statusVariant[row.status] ?? "gray"}>
                  {getStatusDisplayLabel(row.status, row.status_label)}
                </Badge>
              </TableCell>
              <TableCell className="text-right tabular-nums">{row.highlights}</TableCell>
              <TableCell className="text-right tabular-nums">{row.notes}</TableCell>
              <TableCell className="text-right tabular-nums">{row.bookmarks}</TableCell>
              <TableCell className="text-right tabular-nums">{row.new_highlights_count}</TableCell>
              <TableCell className="text-muted-foreground">
                {row.last_export_display}
              </TableCell>
              <TableCell className="px-1 text-right">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`Baixar ${row.title}`}
                      disabled={!canDownload || downloadingBookKey === row.book_key}
                      onClick={() => onBookDownload(row)}
                    >
                      <Download className="h-4 w-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Baixar arquivos</TooltipContent>
                </Tooltip>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function downloadBlob(blob: Blob) {
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  const timestamp = new Date()
    .toISOString()
    .slice(0, 19)
    .split("-")
    .join("")
    .split(":")
    .join("")
    .replace("T", "");
  anchor.download = `kindle_destaques_${timestamp}.zip`;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
}

function downloadNamedBlob(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
}

function blobFromBase64(contentBase64: string, mimeType: string) {
  const binary = window.atob(contentBase64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return new Blob([bytes], { type: mimeType });
}

function formatLocalDateTime(date: Date) {
  const pad = (value: number) => String(value).padStart(2, "0");
  return [
    date.getFullYear(),
    pad(date.getMonth() + 1),
    pad(date.getDate()),
  ].join("-") + ` ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export default function App() {
  const [config, setConfig] = useState<AppConfig>(DEFAULT_CONFIG);
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [selectionMap, setSelectionMap] = useState<Record<string, boolean>>({});
  const [file, setFile] = useState<File | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [downloadingBookKey, setDownloadingBookKey] = useState<string | null>(null);
  const [theme, setTheme] = useState<Theme>(getInitialTheme);
  const [openBook, setOpenBook] = useState<BookEntriesResponse | null>(null);
  const [isLoadingBook, setIsLoadingBook] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  const activeFormats = activeFormatLabels(config);
  const activeFormatKeys = activeFormatValues(config);
  const visibleRows = useMemo(
    () => filterRows(analysis?.rows ?? [], selectionMap, filters),
    [analysis?.rows, filters, selectionMap],
  );
  const summary = useMemo(
    () => buildSelectionSummary(analysis?.rows ?? [], selectionMap, config),
    [analysis?.rows, config, selectionMap],
  );
  const selectedBookKeys = useMemo(
    () => Object.entries(selectionMap).filter(([, selected]) => selected).map(([key]) => key),
    [selectionMap],
  );

  const statusOptions = analysis?.statusOptions ?? FALLBACK_STATUS_OPTIONS;
  const authorOptions = ["Todos", ...(analysis?.authorOptions ?? [])];

  const runAnalyze = async (forceReprocess: boolean) => {
    if (!file) return;
    if (!activeFormats.length) {
      toast.error("Ative ao menos um formato.");
      return;
    }
    setIsAnalyzing(true);
    try {
      const result = await analyzeFile(file, config, forceReprocess);
      setAnalysis(result);
      setSelectionMap(result.selectionMap);
      setFilters(DEFAULT_FILTERS);
      toast.success("Análise concluída.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Falha na análise.");
    } finally {
      setIsAnalyzing(false);
    }
  };

  const applyExportedRows = (exportedKeys: string[]) => {
    const lastExportDisplay = formatLocalDateTime(new Date());
    setAnalysis((currentAnalysis) => {
      if (!currentAnalysis) return currentAnalysis;
      return {
        ...currentAnalysis,
        rows: markRowsExported(
          currentAnalysis.rows,
          exportedKeys,
          activeFormatKeys,
          lastExportDisplay,
        ),
      };
    });
  };

  const runExport = async () => {
    if (!analysis || !selectedBookKeys.length || !activeFormats.length) return;
    setIsExporting(true);
    try {
      const blob = await exportBooks(analysis.analysisId, selectedBookKeys, config);
      downloadBlob(blob);
      applyExportedRows(selectedBookKeys);
      toast.success("ZIP gerado.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Falha na exportação.");
    } finally {
      setIsExporting(false);
    }
  };

  const runBookDownload = async (row: BookRow) => {
    if (!analysis || !activeFormats.length) return;
    setDownloadingBookKey(row.book_key);
    try {
      const payload = await exportBookFiles(analysis.analysisId, row.book_key, config);
      for (const filePayload of payload.files) {
        downloadNamedBlob(
          blobFromBase64(filePayload.contentBase64, filePayload.mimeType),
          filePayload.filename,
        );
      }
      applyExportedRows([row.book_key]);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Falha no download.");
    } finally {
      setDownloadingBookKey(null);
    }
  };

  const openBookEntries = async (row: BookRow) => {
    if (!analysis) return;
    setIsLoadingBook(true);
    try {
      setOpenBook(await fetchBookEntries(analysis.analysisId, row.book_key));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Falha ao carregar destaques.");
    } finally {
      setIsLoadingBook(false);
    }
  };

  const applyBatch = (action: "recommended" | "select_visible" | "clear_visible") => {
    if (!analysis) return;
    setSelectionMap(applyBatchSelection(analysis.rows, selectionMap, visibleRows, action));
  };

  return (
    <TooltipProvider>
      <div className="min-h-screen bg-background">
        <div className="mx-auto grid w-full max-w-[1480px] gap-4 px-4 py-4 lg:grid-cols-[240px_minmax(0,1fr)]">
          <div className="hidden lg:block">
            <SettingsPanel config={config} onChange={setConfig} />
          </div>

          <main className="min-w-0 space-y-4">
            <header className="flex flex-wrap items-center justify-between gap-3 border-b pb-3">
              <div>
                <h1 className="text-xl font-semibold">Kindle Highlights</h1>
                <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                  <FileArchive className="h-4 w-4" />
                  <span className="max-w-[34rem] truncate">{file?.name ?? "Nenhum arquivo"}</span>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <Sheet>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <SheetTrigger asChild>
                        <Button variant="outline" size="icon" className="lg:hidden">
                          <Settings2 className="h-4 w-4" />
                        </Button>
                      </SheetTrigger>
                    </TooltipTrigger>
                    <TooltipContent>Configurações</TooltipContent>
                  </Tooltip>
                  <SheetContent>
                    <SheetHeader>
                      <SheetTitle>Configurações</SheetTitle>
                    </SheetHeader>
                    <SettingsPanel config={config} onChange={setConfig} />
                  </SheetContent>
                </Sheet>

                <input
                  ref={fileInputRef}
                  className="hidden"
                  type="file"
                  accept=".txt,text/plain"
                  onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                />
                <Button variant="outline" onClick={() => fileInputRef.current?.click()}>
                  <Upload className="h-4 w-4" />
                  Arquivo
                </Button>
                <Button onClick={() => runAnalyze(false)} disabled={!file || isAnalyzing}>
                  <Search className="h-4 w-4" />
                  Analisar
                </Button>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => runAnalyze(true)}
                      disabled={!file || isAnalyzing}
                    >
                      <RefreshCw className="h-4 w-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Reanalisar</TooltipContent>
                </Tooltip>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="outline"
                      size="icon"
                      aria-label="Alternar tema"
                      onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
                    >
                      {theme === "dark" ? (
                        <Sun className="h-4 w-4" />
                      ) : (
                        <Moon className="h-4 w-4" />
                      )}
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>{theme === "dark" ? "Tema claro" : "Tema escuro"}</TooltipContent>
                </Tooltip>
              </div>
            </header>

            {(isAnalyzing || isExporting || downloadingBookKey) && (
              <Progress value={isAnalyzing ? 62 : 86} />
            )}

            <MetricsStrip
              analysis={analysis}
              summary={summary}
              activeFormats={activeFormats}
              onlyNew={config.exportOnlyNew}
            />

            <section className="rounded-md border bg-card p-3">
              <div className="grid gap-3 xl:grid-cols-[1fr_160px_220px_auto]">
                <div className="relative">
                  <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                  <Input
                    aria-label="Busca"
                    className="pl-9"
                    style={
                      theme === "dark"
                        ? {
                          backgroundColor: "oklch(0.2603 0 0)",
                          color: "oklch(0.9288 0.0126 255.5078)",
                        }
                        : undefined
                    }
                    placeholder="Título ou autor"
                    value={filters.search}
                    onChange={(event) => setFilters({ ...filters, search: event.target.value })}
                  />
                </div>
                <Select
                  value={filters.status}
                  onValueChange={(status) => setFilters({ ...filters, status })}
                >
                  <SelectTrigger aria-label="Status">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {statusOptions.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.value === "todos" ? "Status" : getStatusDisplayLabel(option.value, option.label)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Select
                  value={filters.author}
                  onValueChange={(author) => setFilters({ ...filters, author })}
                >
                  <SelectTrigger aria-label="Autor">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {authorOptions.map((author) => (
                      <SelectItem key={author} value={author}>
                        {author === "Todos" ? "Autor" : author}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Tabs
                  value={filters.selectedOnly ? "selecionados" : "todos"}
                  onValueChange={(value) =>
                    setFilters({ ...filters, selectedOnly: value === "selecionados" })
                  }
                >
                  <TabsList className="w-full">
                    <TabsTrigger value="todos" className="flex-1">
                      Todos
                    </TabsTrigger>
                    <TabsTrigger value="selecionados" className="flex-1">
                      Marcados
                    </TabsTrigger>
                  </TabsList>
                </Tabs>
              </div>

              <div className="mt-3 grid gap-2 md:grid-cols-[1fr_auto] md:items-center">
                <div className="grid gap-2 sm:grid-cols-3 md:flex md:flex-wrap md:items-center">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => applyBatch("recommended")}
                    disabled={!analysis || !visibleRows.length}
                  >
                    <CheckCheck className="h-4 w-4" />
                    Recomendados
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => applyBatch("select_visible")}
                    disabled={!analysis || !visibleRows.length}
                  >
                    <Filter className="h-4 w-4" />
                    Visíveis
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => applyBatch("clear_visible")}
                    disabled={!analysis || !visibleRows.length}
                  >
                    <XCircle className="h-4 w-4" />
                    Limpar
                  </Button>
                </div>
                <Button
                  className="w-full md:w-auto"
                  onClick={runExport}
                  disabled={!analysis || !selectedBookKeys.length || !activeFormats.length || isExporting}
                >
                  <Download className="h-4 w-4" />
                  Exportar ZIP
                </Button>
              </div>
            </section>

            <BookTable
              rows={analysis?.rows ?? []}
              visibleRows={visibleRows}
              selectionMap={selectionMap}
              onSelectionChange={setSelectionMap}
              onBookDownload={runBookDownload}
              onBookOpen={openBookEntries}
              downloadingBookKey={downloadingBookKey}
              canDownload={Boolean(analysis && activeFormats.length && !isExporting)}
            />
          </main>
        </div>

        <BookEntriesPanel
          book={openBook}
          isLoading={isLoadingBook}
          onOpenChange={(open) => {
            if (!open) setOpenBook(null);
          }}
        />
      </div>
    </TooltipProvider>
  );
}
