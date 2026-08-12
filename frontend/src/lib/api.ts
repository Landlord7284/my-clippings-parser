import type {
  AnalysisResponse,
  AppConfig,
  BookEntriesResponse,
  ExportBookFilesResponse,
} from "@/types";

const API_BASE = "";

async function parseError(response: Response) {
  if (response.status === 405) {
    return "Servidor desatualizado. Reinicie a API e tente novamente.";
  }

  try {
    const payload = await response.json();
    return payload.detail || "Falha na requisicao.";
  } catch {
    return "Falha na requisicao.";
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
    throw new Error(await parseError(response));
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
    throw new Error(await parseError(response));
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
    throw new Error(await parseError(response));
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
    throw new Error(await parseError(response));
  }
  return response.json();
}
