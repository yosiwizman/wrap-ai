import { describe, it, expect } from "vitest";
import GitHubIssuesPRsService from "../../src/api/github-service/github-issues-prs.api";

describe("GitHubIssuesPRsService", () => {
  describe("buildItemUrl", () => {
    it("should build correct GitHub issue URL", () => {
      const url = GitHubIssuesPRsService.buildItemUrl(
        "github",
        "owner/repo",
        123,
        "issue",
      );
      expect(url).toBe("https://github.com/owner/repo/issues/123");
    });

    it("should build correct GitHub PR URL", () => {
      const url = GitHubIssuesPRsService.buildItemUrl(
        "github",
        "owner/repo",
        456,
        "pr",
      );
      expect(url).toBe("https://github.com/owner/repo/pull/456");
    });

    it("should build correct GitLab issue URL", () => {
      const url = GitHubIssuesPRsService.buildItemUrl(
        "gitlab",
        "owner/repo",
        123,
        "issue",
      );
      expect(url).toBe("https://gitlab.com/owner/repo/-/issues/123");
    });

    it("should build correct GitLab MR URL", () => {
      const url = GitHubIssuesPRsService.buildItemUrl(
        "gitlab",
        "owner/repo",
        456,
        "pr",
      );
      expect(url).toBe("https://gitlab.com/owner/repo/-/merge_requests/456");
    });

    it("should build correct Bitbucket issue URL", () => {
      const url = GitHubIssuesPRsService.buildItemUrl(
        "bitbucket",
        "owner/repo",
        123,
        "issue",
      );
      expect(url).toBe("https://bitbucket.org/owner/repo/issues/123");
    });

    it("should build correct Bitbucket PR URL", () => {
      const url = GitHubIssuesPRsService.buildItemUrl(
        "bitbucket",
        "owner/repo",
        456,
        "pr",
      );
      expect(url).toBe("https://bitbucket.org/owner/repo/pull-requests/456");
    });

    it("should return empty string for unknown provider", () => {
      const url = GitHubIssuesPRsService.buildItemUrl(
        "unknown" as any,
        "owner/repo",
        123,
        "issue",
      );
      expect(url).toBe("");
    });
  });
});
