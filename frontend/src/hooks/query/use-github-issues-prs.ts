import { useQuery, useQueryClient } from "@tanstack/react-query";
import React from "react";
import GitHubIssuesPRsService, {
  GitHubItemsFilter,
  GitHubItemsResponse,
} from "#/api/github-service/github-issues-prs.api";
import { useShouldShowUserFeatures } from "../use-should-show-user-features";

const CACHE_KEY = "github-issues-prs-cache";
const CACHE_DURATION_MS = 60 * 1000; // 1 minute

interface CachedData {
  data: GitHubItemsResponse;
  timestamp: number;
}

/**
 * Get cached data from localStorage
 */
function getCachedData(): CachedData | null {
  try {
    const cached = localStorage.getItem(CACHE_KEY);
    if (cached) {
      const parsed = JSON.parse(cached) as CachedData;
      return parsed;
    }
  } catch {
    // Ignore parse errors
  }
  return null;
}

/**
 * Save data to localStorage cache
 */
function setCachedData(data: GitHubItemsResponse): void {
  try {
    const cacheEntry: CachedData = {
      data,
      timestamp: Date.now(),
    };
    localStorage.setItem(CACHE_KEY, JSON.stringify(cacheEntry));
  } catch {
    // Ignore storage errors
  }
}

/**
 * Check if cached data is still valid
 */
function isCacheValid(cached: CachedData | null): boolean {
  if (!cached) return false;
  return Date.now() - cached.timestamp < CACHE_DURATION_MS;
}

/**
 * Hook to fetch GitHub issues and PRs with local storage caching
 */
export const useGitHubIssuesPRs = (filter?: GitHubItemsFilter) => {
  const shouldShowUserFeatures = useShouldShowUserFeatures();
  const queryClient = useQueryClient();

  // Set up auto-refresh interval
  React.useEffect(() => {
    if (!shouldShowUserFeatures) return undefined;

    const interval = setInterval(() => {
      queryClient.invalidateQueries({ queryKey: ["github-issues-prs"] });
    }, CACHE_DURATION_MS);

    return () => clearInterval(interval);
  }, [shouldShowUserFeatures, queryClient]);

  return useQuery({
    queryKey: ["github-issues-prs", filter],
    queryFn: async () => {
      // Check localStorage cache first
      const cached = getCachedData();
      if (isCacheValid(cached)) {
        // Return cached data but still fetch in background
        return cached!.data;
      }

      // Fetch fresh data
      const response = await GitHubIssuesPRsService.getGitHubItems(filter);

      // Save to localStorage
      setCachedData(response);

      return response;
    },
    enabled: shouldShowUserFeatures,
    staleTime: CACHE_DURATION_MS,
    gcTime: CACHE_DURATION_MS * 5,
    // Use cached data as initial data for faster loading
    initialData: () => {
      const cached = getCachedData();
      if (cached) {
        return cached.data;
      }
      return undefined;
    },
    initialDataUpdatedAt: () => {
      const cached = getCachedData();
      if (cached) {
        return cached.timestamp;
      }
      return undefined;
    },
  });
};

/**
 * Hook to manually refresh GitHub issues and PRs data
 */
export const useRefreshGitHubIssuesPRs = () => {
  const queryClient = useQueryClient();

  return React.useCallback(() => {
    // Clear localStorage cache
    localStorage.removeItem(CACHE_KEY);
    // Invalidate React Query cache
    queryClient.invalidateQueries({ queryKey: ["github-issues-prs"] });
  }, [queryClient]);
};
