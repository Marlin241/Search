import { describe, it, expect } from "vitest";
import config from "./tailwind.config";

describe("tailwind.config", () => {
  it("enables media-based dark mode", () => {
    expect(config.darkMode).toBe("media");
  });

  it("defines the ink color scale used for dark surfaces", () => {
    const colors = config.theme?.extend?.colors as Record<string, Record<string, string>> | undefined;
    expect(colors?.ink).toEqual({
      800: "#232b3a",
      900: "#131924",
      950: "#0b0f16",
    });
  });
});
