import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import {
  useGitHubIssuesPRs,
  useRefreshGitHubIssuesPRs,
} from "../src/hooks/query/use-github-issues-prs";
import { useShouldShowUserFeatures } from "../src/hooks/use-should-show-user-features";
import GitHubIssuesPRsService from "../src/api/github-service/github-issues-prs.api";

// Mock the dependencies
vi.mock("../src/hooks/use-should-show-user-features");
vi.mock("../src/api/github-service/github-issues-prs.api", () => ({
  default: {
    getGitHubItems: vi.fn(),
    buildItemUrl: vi.fn(),
  },
}));

const mockUseShouldShowUserFeatures = vi.mocked(useShouldShowUserFeatures);
const mockGetGitHubItems = vi.mocked(GitHubIssuesPRsService.getGitHubItems);

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
};

describe("useGitHubIssuesPRs", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    mockUseShouldShowUserFeatures.mockReturnValue(false);
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("should be disabled when useShouldShowUserFeatures returns false", () => {
    mockUseShouldShowUserFeatures.mockReturnValue(false);

    const { result } = renderHook(() => useGitHubIssuesPRs(), {
      wrapper: createWrapper(),
    });

    expect(result.current.isLoading).toBe(false);
    expect(result.current.isFetching).toBe(false);
  });

  it("should be enabled when useShouldShowUserFeatures returns true", () => {
    mockUseShouldShowUserFeatures.mockReturnValue(true);
    mockGetGitHubItems.mockResolvedValue({
      items: [],
      cached_at: new Date().toISOString(),
    });

    const { result } = renderHook(() => useGitHubIssuesPRs(), {
      wrapper: createWrapper(),
    });

    // When enabled, the query should be loading/fetching
    expect(result.current.isLoading).toBe(true);
  });

  it("should fetch and return GitHub items", async () => {
    mockUseShouldShowUserFeatures.mockReturnValue(true);
    const mockItems = [
      {
        git_provider: "github" as const,
        item_type: "issue" as const,
        status: "OPEN_ISSUE" as const,
        repo: "test/repo",
        number: 1,
        title: "Test Issue",
        author: "testuser",
        assignees: ["testuser"],
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-01-01T00:00:00Z",
        url: "https://github.com/test/repo/issues/1",
      },
    ];
    mockGetGitHubItems.mockResolvedValue({
      items: mockItems,
      cached_at: new Date().toISOString(),
    });

    const { result } = renderHook(() => useGitHubIssuesPRs(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data?.items).toEqual(mockItems);
  });

  it("should filter by item type", async () => {
    mockUseShouldShowUserFeatures.mockReturnValue(true);
    const mockItems = [
      {
        git_provider: "github" as const,
        item_type: "issue" as const,
        status: "OPEN_ISSUE" as const,
        repo: "test/repo",
        number: 1,
        title: "Test Issue",
        author: "testuser",
        assignees: ["testuser"],
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-01-01T00:00:00Z",
        url: "https://github.com/test/repo/issues/1",
      },
    ];
    mockGetGitHubItems.mockResolvedValue({
      items: mockItems,
      cached_at: new Date().toISOString(),
    });

    const { result } = renderHook(
      () => useGitHubIssuesPRs({ itemType: "issues" }),
      {
        wrapper: createWrapper(),
      },
    );

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockGetGitHubItems).toHaveBeenCalledWith({ itemType: "issues" });
  });
});

describe("useRefreshGitHubIssuesPRs", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("should clear localStorage cache when called", () => {
    // Set up some cached data
    localStorage.setItem(
      "github-issues-prs-cache",
      JSON.stringify({
        data: { items: [], cached_at: new Date().toISOString() },
        timestamp: Date.now(),
      }),
    );

    const { result } = renderHook(() => useRefreshGitHubIssuesPRs(), {
      wrapper: createWrapper(),
    });

    // Call the refresh function
    result.current();

    // Check that localStorage was cleared
    expect(localStorage.getItem("github-issues-prs-cache")).toBeNull();
  });
});


