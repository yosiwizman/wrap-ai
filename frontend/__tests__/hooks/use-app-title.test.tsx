import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { useAppTitle } from "#/hooks/use-app-title";
import { useConfig } from "#/hooks/query/use-config";

// Mock the useConfig hook
vi.mock("#/hooks/query/use-config");

const mockUseConfig = vi.mocked(useConfig);

describe("useAppTitle", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should return 'OpenHands' for OSS mode", () => {
    mockUseConfig.mockReturnValue({
      data: { APP_MODE: "oss" },
    } as any);

    const { result } = renderHook(() => useAppTitle());

    expect(result.current).toBe("OpenHands");
  });

  it("should return 'OpenHands Cloud' for SaaS mode", () => {
    mockUseConfig.mockReturnValue({
      data: { APP_MODE: "saas" },
    } as any);

    const { result } = renderHook(() => useAppTitle());

    expect(result.current).toBe("OpenHands Cloud");
  });

  it("should return 'OpenHands' when APP_MODE is undefined", () => {
    mockUseConfig.mockReturnValue({
      data: { APP_MODE: undefined },
    } as any);

    const { result } = renderHook(() => useAppTitle());

    expect(result.current).toBe("OpenHands");
  });

  it("should return 'OpenHands' when config data is null", () => {
    mockUseConfig.mockReturnValue({
      data: null,
    } as any);

    const { result } = renderHook(() => useAppTitle());

    expect(result.current).toBe("OpenHands");
  });
});
