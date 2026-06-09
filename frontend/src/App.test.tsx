import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import App from "./App";

describe("App shell", () => {
  it("renders controls and keeps export disabled before analysis", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: /Extrator de Destaques Kindle/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Analisar/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Exportar ZIP/i })).toBeDisabled();
    expect(screen.getByLabelText("Busca")).toBeInTheDocument();
  });

  it("updates format controls", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByLabelText("HTML"));

    expect(screen.getByText("Markdown / HTML")).toBeInTheDocument();
  });
});
