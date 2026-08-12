import "@testing-library/jest-dom/vitest";

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

globalThis.ResizeObserver = ResizeObserverMock;

// O Node 26 expõe um localStorage nativo que fica inerte sem --localstorage-file
// e acaba sombreando o do jsdom. Instala um Storage em memória quando isso ocorre.
if (!window.localStorage) {
  class MemoryStorage implements Storage {
    private store = new Map<string, string>();

    get length() {
      return this.store.size;
    }

    key(index: number) {
      return [...this.store.keys()][index] ?? null;
    }

    getItem(key: string) {
      return this.store.get(key) ?? null;
    }

    setItem(key: string, value: string) {
      this.store.set(key, String(value));
    }

    removeItem(key: string) {
      this.store.delete(key);
    }

    clear() {
      this.store.clear();
    }
  }

  Object.defineProperty(window, "localStorage", {
    value: new MemoryStorage(),
    configurable: true,
  });
}
