import { describe, it, expect } from "vitest";
import config from "./tailwind.config";

describe("tailwind.config", () => {
  it("enables media-based dark mode", () => {
    expect(config.darkMode).toBe("media");
  });

  it("maps the design tokens to CSS custom properties", () => {
    const colors = config.theme?.extend?.colors as Record<string, string> | undefined;
    expect(colors?.ink).toBe("var(--ink)");
    expect(colors?.surface).toBe("var(--surface)");
    expect(colors?.accent).toBe("var(--accent)");
  });
});
