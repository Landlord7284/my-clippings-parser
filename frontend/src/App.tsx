import { useMemo, useRef, useState } from "react";
import {
  CheckCheck,
  Download,
  FileArchive,
  Filter,
  RefreshCw,
  Search,
  Settings2,
  Upload,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";

import { analyzeFile, exportBooks } from "@/lib/api";
import {
  DEFAULT_CONFIG,
  DEFAULT_FILTERS,
  activeFormatLabels,
  applyBatchSelection,
  buildSelectionSummary,
  filterRows,
} from "@/lib/selection";
import type { AnalysisResponse, AppConfig, BookRow, FilterState } from "@/types";
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
  { value: "nunca_exportado", label: "Nunca exportado" },
  { value: "com_novidades", label: "Com novidades" },
  { value: "sem_novidades", label: "Sem novidades" },
  { value: "selecionados", label: "Selecionados" },
];

const statusVariant: Record<string, "green" | "amber" | "blue" | "gray"> = {
  novo: "green",
  nunca_exportado: "amber",
  com_novidades: "blue",
  sem_novidades: "gray",
};

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
      </section>

      <section className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <Label htmlFor="similarity">Similaridade</Label>
          <span className="tabular-nums text-sm text-muted-foreground">
            {config.similarityThreshold.toFixed(1)}
          </span>
        </div>
        <Slider
          id="similarity"
          min={0.5}
          max={1}
          step={0.1}
          value={[config.similarityThreshold]}
          onValueChange={([value]) => setValue("similarityThreshold", value)}
        />
      </section>
    </aside>
  );
}

function ToggleRow({
  id,
  label,
  checked,
  onCheckedChange,
}: {
  id: string;
  label: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
}) {
  return (
    <div className="flex min-h-8 items-center justify-between gap-3">
      <Label htmlFor={id} className="text-sm font-normal">
        {label}
      </Label>
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
}: {
  analysis: AnalysisResponse | null;
  summary: ReturnType<typeof buildSelectionSummary>;
  activeFormats: string[];
}) {
  const metrics = [
    ["Entradas", analysis?.stats.total_entries ?? "-"],
    ["Livros", analysis?.stats.books_processed ?? "-"],
    ["Selecionados", summary.selectedBooks],
    ["Highlights", summary.selectedHighlights],
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

function BookTable({
  rows,
  visibleRows,
  selectionMap,
  onSelectionChange,
}: {
  rows: BookRow[];
  visibleRows: BookRow[];
  selectionMap: Record<string, boolean>;
  onSelectionChange: (selectionMap: Record<string, boolean>) => void;
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
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-10">
              <Checkbox
                checked={headerChecked}
                aria-label="Selecionar visíveis"
                onCheckedChange={(checked) => toggleVisible(Boolean(checked))}
              />
            </TableHead>
            <TableHead className="min-w-[16rem]">Livro</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Destaques</TableHead>
            <TableHead className="text-right">Notas</TableHead>
            <TableHead className="text-right">Marcadores</TableHead>
            <TableHead className="text-right">Novos</TableHead>
            <TableHead>Última exportação</TableHead>
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
              <TableCell>
                <div className="max-w-[32rem]">
                  <div className="truncate font-medium">{row.title}</div>
                  <div className="truncate text-xs text-muted-foreground">{row.author}</div>
                </div>
              </TableCell>
              <TableCell>
                <Badge variant={statusVariant[row.status] ?? "gray"}>{row.status_label}</Badge>
              </TableCell>
              <TableCell className="text-right tabular-nums">{row.highlights}</TableCell>
              <TableCell className="text-right tabular-nums">{row.notes}</TableCell>
              <TableCell className="text-right tabular-nums">{row.bookmarks}</TableCell>
              <TableCell className="text-right tabular-nums">{row.new_highlights_count}</TableCell>
              <TableCell className="min-w-36 text-muted-foreground">
                {row.last_export_display}
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

export default function App() {
  const [config, setConfig] = useState<AppConfig>(DEFAULT_CONFIG);
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [selectionMap, setSelectionMap] = useState<Record<string, boolean>>({});
  const [file, setFile] = useState<File | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const activeFormats = activeFormatLabels(config);
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

  const runExport = async () => {
    if (!analysis || !selectedBookKeys.length || !activeFormats.length) return;
    setIsExporting(true);
    try {
      const blob = await exportBooks(analysis.analysisId, selectedBookKeys, config);
      downloadBlob(blob);
      toast.success("ZIP gerado.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Falha na exportação.");
    } finally {
      setIsExporting(false);
    }
  };

  const applyBatch = (action: "recommended" | "select_visible" | "clear_visible") => {
    if (!analysis) return;
    setSelectionMap(applyBatchSelection(analysis.rows, selectionMap, visibleRows, action));
  };

  return (
    <TooltipProvider>
      <div className="min-h-screen bg-background">
        <div className="mx-auto grid w-full max-w-[1480px] gap-4 px-4 py-4 lg:grid-cols-[280px_minmax(0,1fr)]">
          <div className="hidden lg:block">
            <SettingsPanel config={config} onChange={setConfig} />
          </div>

          <main className="min-w-0 space-y-4">
            <header className="flex flex-wrap items-center justify-between gap-3 border-b pb-3">
              <div>
                <h1 className="text-xl font-semibold">Extrator de Destaques Kindle</h1>
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
              </div>
            </header>

            {(isAnalyzing || isExporting) && <Progress value={isAnalyzing ? 62 : 86} />}

            <MetricsStrip analysis={analysis} summary={summary} activeFormats={activeFormats} />

            <section className="rounded-md border bg-card p-3">
              <div className="grid gap-3 xl:grid-cols-[1fr_160px_220px_auto]">
                <div className="relative">
                  <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                  <Input
                    aria-label="Busca"
                    className="pl-9"
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
                        {option.label}
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
                        {author}
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
            />
          </main>
        </div>
      </div>
    </TooltipProvider>
  );
}
