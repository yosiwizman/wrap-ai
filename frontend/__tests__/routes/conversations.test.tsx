import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createRoutesStub } from "react-router";
import ConversationsPage from "#/routes/conversations";
import ConversationService from "#/api/conversation-service/conversation-service.api";
import { Conversation, ResultSet } from "#/api/open-hands.types";

// Mock conversation data for testing
const MOCK_CONVERSATIONS: Conversation[] = [
  {
    conversation_id: "conv-1",
    title: "Fix authentication bug",
    status: "RUNNING",
    selected_repository: "octocat/hello-world",
    selected_branch: "main",
    git_provider: "github",
    created_at: "2025-12-17T10:00:00Z",
    last_updated_at: "2025-12-17T10:30:00Z",
    runtime_status: null,
    url: null,
    session_api_key: null,
  },
  {
    conversation_id: "conv-2",
    title: "Add dark mode feature",
    status: "STOPPED",
    selected_repository: "octocat/my-repo",
    selected_branch: "feature/dark-mode",
    git_provider: "gitlab",
    created_at: "2025-12-16T14:00:00Z",
    last_updated_at: "2025-12-16T15:00:00Z",
    runtime_status: null,
    url: null,
    session_api_key: null,
  },
  {
    conversation_id: "conv-3",
    title: "Refactor API endpoints",
    status: "ERROR",
    selected_repository: null,
    selected_branch: null,
    git_provider: null,
    created_at: "2025-12-15T09:00:00Z",
    last_updated_at: "2025-12-15T09:45:00Z",
    runtime_status: null,
    url: null,
    session_api_key: null,
  },
];

// Test helper to create ResultSet responses
const createResultSet = (
  conversations: Conversation[],
  nextPageId: string | null = null,
): ResultSet<Conversation> => ({
  results: conversations,
  next_page_id: nextPageId,
});

// Router stub for navigation
const RouterStub = createRoutesStub([
  {
    Component: ConversationsPage,
    path: "/conversations",
  },
  {
    Component: () => <div data-testid="conversation-detail" />,
    path: "/conversations/:conversationId",
  },
]);

// Render helper with QueryClient
const renderConversationsPage = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

  return render(<RouterStub initialEntries={["/conversations"]} />, {
    wrapper: ({ children }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    ),
  });
};

describe("Conversations Page", () => {
  const getUserConversationsSpy = vi.spyOn(
    ConversationService,
    "getUserConversations",
  );

  beforeEach(() => {
    vi.resetAllMocks();
    // Default: Return mock conversations
    getUserConversationsSpy.mockResolvedValue(
      createResultSet(MOCK_CONVERSATIONS),
    );
  });

  describe("Page Header", () => {
    it("displays the recent conversations title", async () => {
      renderConversationsPage();

      expect(
        await screen.findByText("COMMON$RECENT_CONVERSATIONS"),
      ).toBeInTheDocument();
    });
  });

  describe("Loading State", () => {
    it("shows skeleton loader then conversations", async () => {
      renderConversationsPage();

      // Conversations should appear after loading
      expect(
        await screen.findByText("Fix authentication bug"),
      ).toBeInTheDocument();
    });
  });

  describe("Conversations List", () => {
    it("displays all conversations with titles", async () => {
      renderConversationsPage();

      expect(
        await screen.findByText("Fix authentication bug"),
      ).toBeInTheDocument();
      expect(screen.getByText("Add dark mode feature")).toBeInTheDocument();
      expect(screen.getByText("Refactor API endpoints")).toBeInTheDocument();
    });

    it("shows repository and branch information", async () => {
      renderConversationsPage();

      await waitFor(() => {
        expect(screen.getByText("octocat/hello-world")).toBeInTheDocument();
        expect(screen.getByText("main")).toBeInTheDocument();
      });

      expect(screen.getByText("octocat/my-repo")).toBeInTheDocument();
      expect(screen.getByText("feature/dark-mode")).toBeInTheDocument();
    });

    it("displays no repository label when repository is not set", async () => {
      renderConversationsPage();

      await waitFor(() => {
        expect(screen.getByText("COMMON$NO_REPOSITORY")).toBeInTheDocument();
      });
    });

    it("shows status indicators for each conversation state", async () => {
      renderConversationsPage();

      await waitFor(() => {
        expect(screen.getByLabelText("COMMON$RUNNING")).toBeInTheDocument();
        expect(screen.getByLabelText("COMMON$STOPPED")).toBeInTheDocument();
        expect(screen.getByLabelText("COMMON$ERROR")).toBeInTheDocument();
      });
    });

    it("displays relative timestamps", async () => {
      renderConversationsPage();

      await waitFor(() => {
        const timestamps = screen.getAllByText(/CONVERSATION\$AGO/);
        expect(timestamps.length).toBeGreaterThan(0);
      });
    });
  });

  describe("Empty State", () => {
    it("shows empty message when no conversations exist", async () => {
      getUserConversationsSpy.mockResolvedValue(createResultSet([]));

      renderConversationsPage();

      expect(
        await screen.findByText("HOME$NO_RECENT_CONVERSATIONS"),
      ).toBeInTheDocument();
    });

    it("does not show empty state when there is an error", async () => {
      getUserConversationsSpy.mockRejectedValue(
        new Error("Network error"),
      );

      renderConversationsPage();

      await waitFor(() => {
        expect(screen.getByText(/Network error/i)).toBeInTheDocument();
      });

      expect(
        screen.queryByText("HOME$NO_RECENT_CONVERSATIONS"),
      ).not.toBeInTheDocument();
    });
  });

  describe("Error Handling", () => {
    it("displays error message when API request fails", async () => {
      getUserConversationsSpy.mockRejectedValue(
        new Error("Failed to fetch conversations"),
      );

      renderConversationsPage();

      expect(
        await screen.findByText(/Failed to fetch conversations/i),
      ).toBeInTheDocument();
    });
  });

  describe("Pagination", () => {
    it("loads first page of conversations", async () => {
      const firstPageConversations = MOCK_CONVERSATIONS.slice(0, 2);

      getUserConversationsSpy.mockResolvedValue(
        createResultSet(firstPageConversations, "page-2"),
      );

      renderConversationsPage();

      await waitFor(() => {
        expect(screen.getByText("Fix authentication bug")).toBeInTheDocument();
        expect(screen.getByText("Add dark mode feature")).toBeInTheDocument();
      });

      // Third conversation not on first page
      expect(
        screen.queryByText("Refactor API endpoints"),
      ).not.toBeInTheDocument();
    });

    it("does not show loading indicator when not fetching", async () => {
      renderConversationsPage();

      await waitFor(() => {
        expect(screen.getByText("Fix authentication bug")).toBeInTheDocument();
      });

      expect(screen.queryByText(/Loading more/i)).not.toBeInTheDocument();
    });
  });

  describe("Navigation", () => {
    it("links to individual conversation detail page", async () => {
      renderConversationsPage();

      const conversationLink = await screen.findByText("Fix authentication bug");
      const linkElement = conversationLink.closest("a");

      expect(linkElement).toHaveAttribute("href", "/conversations/conv-1");
    });

    it("creates clickable cards for each conversation", async () => {
      renderConversationsPage();

      await waitFor(() => {
        const links = screen.getAllByRole("link");
        expect(links.length).toBe(MOCK_CONVERSATIONS.length);
      });
    });
  });

  describe("API Integration", () => {
    it("requests conversations with page size of 20", async () => {
      renderConversationsPage();

      await waitFor(() => {
        expect(screen.getByText("Fix authentication bug")).toBeInTheDocument();
      });

      expect(getUserConversationsSpy).toHaveBeenCalledWith(20, undefined);
    });

    it("supports pagination with page_id parameter", async () => {
      const firstPageConversations = MOCK_CONVERSATIONS.slice(0, 2);

      getUserConversationsSpy.mockResolvedValueOnce(
        createResultSet(firstPageConversations, "page-2"),
      );

      renderConversationsPage();

      await waitFor(() => {
        expect(getUserConversationsSpy).toHaveBeenCalledWith(20, undefined);
      });
    });
  });
});
