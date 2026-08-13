import type { AnalysisResponse, AppConfig } from "@/types";
import { DEFAULT_CONFIG } from "@/lib/selection";

/**
 * A analise vive na memoria do backend (ANALYSIS_CACHE), indexada pelo hash do
 * arquivo. O F5 so perdia o lado do navegador: guardando a resposta aqui, a
 * mesma aba volta com a tabela e a selecao, e os links /clip continuam validos.
 *
 * O arquivo em si nao e guardado -- File nao serializa e o `My Clippings.txt`
 * passa facil dos limites do sessionStorage. Reanalisar exige escolhe-lo de novo.
 *
 * Os filtros ficam de fora de proposito: gravar a cada tecla da busca
 * serializaria a analise inteira no meio da digitacao.
 */
const SESSION_STORAGE_KEY = "kindle-notes-session";
const SESSION_VERSION = 1;

export type PersistedSession = {
  analysis: AnalysisResponse;
  selectionMap: Record<string, boolean>;
  config: AppConfig;
};

type StoredSession = PersistedSession & { version: number };

function getStorage(): Storage | null {
  try {
    return window.sessionStorage ?? null;
  } catch {
    return null;
  }
}

export function loadSession(): PersistedSession | null {
  const storage = getStorage();
  if (!storage) return null;

  const raw = storage.getItem(SESSION_STORAGE_KEY);
  if (!raw) return null;

  try {
    const stored = JSON.parse(raw) as StoredSession;
    if (stored.version !== SESSION_VERSION) return null;
    if (!stored.analysis?.analysisId || !Array.isArray(stored.analysis.rows)) return null;

    return {
      analysis: stored.analysis,
      selectionMap: stored.selectionMap ?? {},
      // Merge com o default: uma versao antiga da config nao pode faltar chave.
      config: { ...DEFAULT_CONFIG, ...(stored.config ?? {}) },
    };
  } catch {
    return null;
  }
}

export function saveSession(session: PersistedSession): void {
  const storage = getStorage();
  if (!storage) return;

  try {
    storage.setItem(
      SESSION_STORAGE_KEY,
      JSON.stringify({ version: SESSION_VERSION, ...session }),
    );
  } catch {
    // Cota estourada: seguir sem persistir e melhor que derrubar a analise.
  }
}

export function clearSession(): void {
  const storage = getStorage();
  if (!storage) return;

  try {
    storage.removeItem(SESSION_STORAGE_KEY);
  } catch {
    // Ignorado: limpar e best-effort.
  }
}
