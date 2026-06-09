import { expect, test } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const fixturePath = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../../tests/fixtures/my_clippings_excerpt.txt",
);

test("upload analyze select and export", async ({ page }) => {
  await page.route("**/api/analyze", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        analysisId: "analysis-1",
        uploadedName: "my_clippings_excerpt.txt",
        stats: {
          total_entries: 4,
          duplicates_removed: 0,
          books_processed: 3,
          errors: 0,
          files_generated: { markdown: 0, html: 0, txt: 0 },
        },
        rows: [
          {
            book_key: "blade",
            title: "Blade Runner",
            author: "Dick, Philip K.",
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
          {
            book_key: "ivan",
            title: "A Morte de Ivan Ilitch",
            author: "Tolstoi, Leon",
            highlights: 1,
            notes: 0,
            bookmarks: 0,
            status: "sem_novidades",
            status_label: "Exportado",
            new_highlights_count: 0,
            default_selected: false,
            last_analysis_display: "-",
            last_export_display: "-",
          },
        ],
        selectionMap: { blade: true, ivan: false },
        statusOptions: [
          { value: "todos", label: "Todos" },
          { value: "novo", label: "Novo" },
          { value: "sem_novidades", label: "Exportado" },
          { value: "selecionados", label: "Selecionado" },
        ],
        authorOptions: ["Dick, Philip K.", "Tolstoi, Leon"],
      }),
    });
  });

  await page.route("**/api/export", async (route) => {
    await route.fulfill({
      contentType: "application/zip",
      body: "zip",
    });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Arquivo" }).click();
  await page.locator("input[type=file]").setInputFiles(fixturePath);
  await page.getByRole("button", { name: "Analisar" }).click();
  await expect(page.getByText("Blade Runner")).toBeVisible();
  await page.getByLabel("Busca").fill("ivan");
  await expect(page.getByText("A Morte de Ivan Ilitch")).toBeVisible();
  await page.getByRole("button", { name: "Visíveis" }).click();
  await page.getByRole("button", { name: "Exportar ZIP" }).click();
  await expect(page.getByText("ZIP gerado.")).toBeVisible();
});
