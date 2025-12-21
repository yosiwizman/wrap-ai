import { openHands } from "../open-hands-axios";
import { Provider } from "#/types/settings";

export type GitHubItemType = "issue" | "pr";

export type GitHubItemStatus =
  | "MERGE_CONFLICTS"
  | "FAILING_CHECKS"
  | "UNRESOLVED_COMMENTS"
  | "OPEN_ISSUE"
  | "OPEN_PR";

export interface GitHubItem {
  git_provider: Provider;
  item_type: GitHubItemType;
  status: GitHubItemStatus;
  repo: string;
  number: number;
  title: string;
  author: string;
  assignees: string[];
  created_at: string;
  updated_at: string;
  url: string;
}

export interface GitHubItemsFilter {
  itemType?: "issues" | "prs" | "all";
  assignedToMe?: boolean;
  authoredByMe?: boolean;
}

export interface GitHubItemsResponse {
  items: GitHubItem[];
  cached_at?: string;
}

/**
 * GitHub Issues/PRs Service - Handles fetching GitHub issues and pull requests
 */
class GitHubIssuesPRsService {
  /**
   * Get GitHub issues and PRs for the authenticated user
   * This uses the existing suggested-tasks endpoint and transforms the data
   */
  static async getGitHubItems(
    filter?: GitHubItemsFilter,
  ): Promise<GitHubItemsResponse> {
    const { data } = await openHands.get<
      Array<{
        git_provider: Provider;
        task_type: GitHubItemStatus;
        repo: string;
        issue_number: number;
        title: string;
      }>
    >("/api/user/suggested-tasks");

    // Transform the suggested tasks into GitHubItems
    const items: GitHubItem[] = data.map((task) => ({
      git_provider: task.git_provider,
      item_type: task.task_type === "OPEN_ISSUE" ? "issue" : "pr",
      status: task.task_type,
      repo: task.repo,
      number: task.issue_number,
      title: task.title,
      author: "", // Not available from suggested-tasks endpoint
      assignees: [], // Not available from suggested-tasks endpoint
      created_at: new Date().toISOString(), // Not available from suggested-tasks endpoint
      updated_at: new Date().toISOString(), // Not available from suggested-tasks endpoint
      url: GitHubIssuesPRsService.buildItemUrl(
        task.git_provider,
        task.repo,
        task.issue_number,
        task.task_type === "OPEN_ISSUE" ? "issue" : "pr",
      ),
    }));

    // Apply filters
    let filteredItems = items;

    if (filter?.itemType === "issues") {
      filteredItems = filteredItems.filter(
        (item) => item.item_type === "issue",
      );
    } else if (filter?.itemType === "prs") {
      filteredItems = filteredItems.filter((item) => item.item_type === "pr");
    }

    // Note: assignedToMe and authoredByMe filters would require additional API data
    // For now, the suggested-tasks endpoint already returns:
    // - PRs authored by the user
    // - Issues assigned to the user
    // So these filters are implicitly applied by the backend

    return {
      items: filteredItems,
      cached_at: new Date().toISOString(),
    };
  }

  /**
   * Build the URL for a GitHub item
   */
  static buildItemUrl(
    provider: Provider,
    repo: string,
    number: number,
    itemType: GitHubItemType,
  ): string {
    if (provider === "github") {
      return `https://github.com/${repo}/${itemType === "issue" ? "issues" : "pull"}/${number}`;
    }
    if (provider === "gitlab") {
      return `https://gitlab.com/${repo}/-/${itemType === "issue" ? "issues" : "merge_requests"}/${number}`;
    }
    if (provider === "bitbucket") {
      return `https://bitbucket.org/${repo}/${itemType === "issue" ? "issues" : "pull-requests"}/${number}`;
    }
    return "";
  }
}

export default GitHubIssuesPRsService;
