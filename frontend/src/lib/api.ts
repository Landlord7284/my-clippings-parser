import type {
  AnalysisResponse,
  AppConfig,
  BookEntriesResponse,
  ExportBookFilesResponse,
} from "@/types";

const API_BASE = "";

/** Carrega o status para o App distinguir 409 (analise expirada) do resto. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** O backend perdeu a analise em memoria -- so um novo upload resolve. */
export function isAnalysisExpired(error: unknown): boolean {
  return error instanceof ApiError && error.status === 409;
}

async function buildError(response: Response) {
  if (response.status === 405) {
    return new ApiError(405, "Servidor desatualizado. Reinicie a API e tente novamente.");
  }

  try {
    const payload = await response.json();
    return new ApiError(response.status, payload.detail || "Falha na requisicao.");
  } catch {
    return new ApiError(response.status, "Falha na requisicao.");
  }
}

export async function analyzeFile(
  file: File,
  config: AppConfig,
  forceReprocess: boolean,
): Promise<AnalysisResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("config", JSON.stringify(config));
  formData.append("forceReprocess", String(forceReprocess));

  const response = await fetch(`${API_BASE}/api/analyze`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    throw await buildError(response);
  }
  return response.json();
}

/** Ultima analise guardada no servidor. `null` quando ainda nao ha nenhuma. */
export async function fetchLatestAnalysis(): Promise<AnalysisResponse | null> {
  const response = await fetch(`${API_BASE}/api/analysis/latest`);
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw await buildError(response);
  }
  return response.json();
}

export async function fetchBookEntries(
  analysisId: string,
  bookKey: string,
): Promise<BookEntriesResponse> {
  const response = await fetch(
    `${API_BASE}/api/analysis/${encodeURIComponent(analysisId)}/books/${encodeURIComponent(bookKey)}/entries`,
  );
  if (!response.ok) {
    throw await buildError(response);
  }
  return response.json();
}

export async function exportBooks(
  analysisId: string,
  selectedBookKeys: string[],
  config: AppConfig,
): Promise<Blob> {
  const response = await fetch(`${API_BASE}/api/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      analysisId,
      selectedBookKeys,
      config,
    }),
  });
  if (!response.ok) {
    throw await buildError(response);
  }
  return response.blob();
}

export async function exportBookFiles(
  analysisId: string,
  bookKey: string,
  config: AppConfig,
): Promise<ExportBookFilesResponse> {
  const response = await fetch(`${API_BASE}/api/export/book`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      analysisId,
      bookKey,
      config,
    }),
  });
  if (!response.ok) {
    throw await buildError(response);
  }
  return response.json();
}
