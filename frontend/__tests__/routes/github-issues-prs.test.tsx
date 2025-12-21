import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClientProvider, QueryClient } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router";
import GitHubIssuesPRsPage from "#/routes/github-issues-prs";
import GitHubIssuesPRsService from "#/api/github-service/github-issues-prs.api";
import ConversationService from "#/api/conversation-service/conversation-service.api";
import { useShouldShowUserFeatures } from "#/hooks/use-should-show-user-features";

// Mock the services
vi.mock("#/api/github-service/github-issues-prs.api", () => ({
  default: {
    getGitHubItems: vi.fn(),
    buildItemUrl: vi.fn((provider, repo, number, type) => {
      if (provider === "github") {
        return `https://github.com/${repo}/${type === "issue" ? "issues" : "pull"}/${number}`;
      }
      return "";
    }),
  },
}));

vi.mock("#/api/conversation-service/conversation-service.api", () => ({
  default: {
    searchConversations: vi.fn(),
    createConversation: vi.fn(),
  },
}));

vi.mock("#/hooks/use-should-show-user-features", () => ({
  useShouldShowUserFeatures: vi.fn(),
}));

// Mock react-i18next to return the key as the translation
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: "en" },
  }),
}));

const mockGetGitHubItems = vi.mocked(GitHubIssuesPRsService.getGitHubItems);
const mockSearchConversations = vi.mocked(
  ConversationService.searchConversations,
);
const mockUseShouldShowUserFeatures = vi.mocked(useShouldShowUserFeatures);

const renderGitHubIssuesPRsPage = () =>
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={["/github-issues-prs"]}>
        <Routes>
          <Route path="/github-issues-prs" element={<GitHubIssuesPRsPage />} />
          <Route
            path="/conversations/:conversationId"
            element={<div data-testid="conversation-screen" />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );

const MOCK_GITHUB_ITEMS = [
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
  {
    git_provider: "github" as const,
    item_type: "pr" as const,
    status: "OPEN_PR" as const,
    repo: "test/repo",
    number: 2,
    title: "Test PR",
    author: "testuser",
    assignees: [],
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
    url: "https://github.com/test/repo/pull/2",
  },
];

describe("GitHubIssuesPRsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();

    mockUseShouldShowUserFeatures.mockReturnValue(true);

    mockGetGitHubItems.mockResolvedValue({
      items: MOCK_GITHUB_ITEMS,
      cached_at: new Date().toISOString(),
    });

    mockSearchConversations.mockResolvedValue([]);
  });

  it("should render the page title", async () => {
    renderGitHubIssuesPRsPage();

    await waitFor(() => {
      expect(screen.getByText("GITHUB_ISSUES_PRS$TITLE")).toBeInTheDocument();
    });
  });

  it("should render the view type selector", async () => {
    renderGitHubIssuesPRsPage();

    await waitFor(() => {
      // The view label has a colon after it
      expect(screen.getByText("GITHUB_ISSUES_PRS$VIEW:")).toBeInTheDocument();
      expect(screen.getByRole("combobox")).toBeInTheDocument();
    });
  });

  it("should render filter checkboxes", async () => {
    renderGitHubIssuesPRsPage();

    await waitFor(() => {
      expect(
        screen.getByText("GITHUB_ISSUES_PRS$ASSIGNED_TO_ME"),
      ).toBeInTheDocument();
      expect(
        screen.getByText("GITHUB_ISSUES_PRS$AUTHORED_BY_ME"),
      ).toBeInTheDocument();
    });
  });

  it("should render the refresh button", async () => {
    renderGitHubIssuesPRsPage();

    await waitFor(() => {
      expect(screen.getByText("GITHUB_ISSUES_PRS$REFRESH")).toBeInTheDocument();
    });
  });

  it("should display GitHub items when loaded", async () => {
    renderGitHubIssuesPRsPage();

    await waitFor(() => {
      expect(screen.getByText("Test Issue")).toBeInTheDocument();
      expect(screen.getByText("Test PR")).toBeInTheDocument();
    });
  });

  it("should display item status badges", async () => {
    renderGitHubIssuesPRsPage();

    await waitFor(() => {
      expect(
        screen.getByText("GITHUB_ISSUES_PRS$OPEN_ISSUE"),
      ).toBeInTheDocument();
      expect(screen.getByText("GITHUB_ISSUES_PRS$OPEN_PR")).toBeInTheDocument();
    });
  });

  it("should display Start Session buttons for items without related conversations", async () => {
    renderGitHubIssuesPRsPage();

    await waitFor(() => {
      const startButtons = screen.getAllByText(
        "GITHUB_ISSUES_PRS$START_SESSION",
      );
      expect(startButtons.length).toBe(2);
    });
  });

  it("should filter items when view type is changed to issues", async () => {
    renderGitHubIssuesPRsPage();

    await waitFor(() => {
      expect(screen.getByText("Test Issue")).toBeInTheDocument();
      expect(screen.getByText("Test PR")).toBeInTheDocument();
    });

    // Change view type to issues
    const select = screen.getByRole("combobox");
    await userEvent.selectOptions(select, "issues");

    await waitFor(() => {
      expect(screen.getByText("Test Issue")).toBeInTheDocument();
      expect(screen.queryByText("Test PR")).not.toBeInTheDocument();
    });
  });

  it("should filter items when view type is changed to PRs", async () => {
    renderGitHubIssuesPRsPage();

    await waitFor(() => {
      expect(screen.getByText("Test Issue")).toBeInTheDocument();
      expect(screen.getByText("Test PR")).toBeInTheDocument();
    });

    // Change view type to PRs
    const select = screen.getByRole("combobox");
    await userEvent.selectOptions(select, "prs");

    await waitFor(() => {
      expect(screen.queryByText("Test Issue")).not.toBeInTheDocument();
      expect(screen.getByText("Test PR")).toBeInTheDocument();
    });
  });

  it("should display Resume Session button when a related conversation exists", async () => {
    mockSearchConversations.mockResolvedValue([
      {
        conversation_id: "conv-1",
        title: "Working on #1",
        selected_repository: "test/repo",
        selected_branch: "main",
        git_provider: "github",
        pr_number: [1],
        created_at: "2024-01-01T00:00:00Z",
        last_updated_at: "2024-01-01T00:00:00Z",
        status: "RUNNING",
        runtime_status: null,
        url: null,
        session_api_key: null,
      },
    ]);

    renderGitHubIssuesPRsPage();

    await waitFor(() => {
      expect(
        screen.getByText("GITHUB_ISSUES_PRS$RESUME_SESSION"),
      ).toBeInTheDocument();
    });
  });

  it("should show empty state when no items are found", async () => {
    mockGetGitHubItems.mockResolvedValue({
      items: [],
      cached_at: new Date().toISOString(),
    });

    renderGitHubIssuesPRsPage();

    await waitFor(() => {
      expect(
        screen.getByText("GITHUB_ISSUES_PRS$NO_ITEMS"),
      ).toBeInTheDocument();
    });
  });

  it("should display View on GitHub links", async () => {
    renderGitHubIssuesPRsPage();

    await waitFor(() => {
      const viewLinks = screen.getAllByText("GITHUB_ISSUES_PRS$VIEW_ON_GITHUB");
      expect(viewLinks.length).toBe(2);
    });
  });
});
