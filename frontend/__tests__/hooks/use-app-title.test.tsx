import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { useAppTitle } from "#/hooks/use-app-title";
import { useConfig } from "#/hooks/query/use-config";

vi.mock("#/hooks/query/use-config");

const mockUseConfig = vi.mocked(useConfig);

describe("useAppTitle", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it.each([
    ["saas", "OpenHands Cloud"],
    ["oss", "OpenHands"],
    [undefined, "OpenHands"],
  ])(
    "should return '%s' when APP_MODE is '%s'",
    (appMode, expectedTitle) => {
      mockUseConfig.mockReturnValue({
        data: { APP_MODE: appMode },
      } as any);

      const { result } = renderHook(() => useAppTitle());

      expect(result.current).toBe(expectedTitle);
    },
  );

  it("should return 'OpenHands' when config data is null", () => {
    mockUseConfig.mockReturnValue({ data: null } as any);

    const { result } = renderHook(() => useAppTitle());

    expect(result.current).toBe("OpenHands");
  });
});
