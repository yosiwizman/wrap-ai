import React from "react";
import { useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import { I18nKey } from "#/i18n/declaration";
import {
  useGitHubIssuesPRs,
  useRefreshGitHubIssuesPRs,
} from "#/hooks/query/use-github-issues-prs";
import { useSearchConversations } from "#/hooks/query/use-search-conversations";
import { useCreateConversation } from "#/hooks/mutation/use-create-conversation";
import { LoadingSpinner } from "#/components/shared/loading-spinner";
import {
  GitHubItem,
  GitHubItemsFilter,
} from "#/api/github-service/github-issues-prs.api";
import { Conversation } from "#/api/open-hands.types";
import { cn } from "#/utils/utils";

type ViewType = "all" | "issues" | "prs";

interface GitHubItemCardProps {
  item: GitHubItem;
  relatedConversation?: Conversation;
  onStartSession: () => void;
  onResumeSession: () => void;
  isStarting: boolean;
}

function GitHubItemCard({
  item,
  relatedConversation,
  onStartSession,
  onResumeSession,
  isStarting,
}: GitHubItemCardProps) {
  const { t } = useTranslation();

  const getStatusBadge = () => {
    switch (item.status) {
      case "MERGE_CONFLICTS":
        return (
          <span className="px-2 py-1 text-xs rounded bg-red-500/20 text-red-400">
            {t(I18nKey.GITHUB_ISSUES_PRS$MERGE_CONFLICTS)}
          </span>
        );
      case "FAILING_CHECKS":
        return (
          <span className="px-2 py-1 text-xs rounded bg-orange-500/20 text-orange-400">
            {t(I18nKey.GITHUB_ISSUES_PRS$FAILING_CHECKS)}
          </span>
        );
      case "UNRESOLVED_COMMENTS":
        return (
          <span className="px-2 py-1 text-xs rounded bg-yellow-500/20 text-yellow-400">
            {t(I18nKey.GITHUB_ISSUES_PRS$UNRESOLVED_COMMENTS)}
          </span>
        );
      case "OPEN_ISSUE":
        return (
          <span className="px-2 py-1 text-xs rounded bg-green-500/20 text-green-400">
            {t(I18nKey.GITHUB_ISSUES_PRS$OPEN_ISSUE)}
          </span>
        );
      case "OPEN_PR":
        return (
          <span className="px-2 py-1 text-xs rounded bg-blue-500/20 text-blue-400">
            {t(I18nKey.GITHUB_ISSUES_PRS$OPEN_PR)}
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <div className="p-4 border border-[#525252] rounded-lg bg-[#25272D] hover:bg-[#2D2F36] transition-colors">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-xs text-neutral-400">
              {item.repo}#{item.number}
            </span>
            {getStatusBadge()}
          </div>
          <h3 className="text-sm font-medium text-white truncate mb-2">
            {item.title}
          </h3>
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-blue-400 hover:underline"
          >
            {t(I18nKey.GITHUB_ISSUES_PRS$VIEW_ON_GITHUB)}
          </a>
        </div>
        <div className="flex flex-col gap-2">
          {relatedConversation ? (
            <button
              type="button"
              onClick={onResumeSession}
              className="px-3 py-1.5 text-xs font-medium rounded bg-blue-600 hover:bg-blue-700 text-white transition-colors"
            >
              {t(I18nKey.GITHUB_ISSUES_PRS$RESUME_SESSION)}
            </button>
          ) : (
            <button
              type="button"
              onClick={onStartSession}
              disabled={isStarting}
              className={cn(
                "px-3 py-1.5 text-xs font-medium rounded transition-colors",
                isStarting
                  ? "bg-neutral-600 text-neutral-400 cursor-not-allowed"
                  : "bg-green-600 hover:bg-green-700 text-white",
              )}
            >
              {isStarting ? (
                <LoadingSpinner size="small" />
              ) : (
                t(I18nKey.GITHUB_ISSUES_PRS$START_SESSION)
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function GitHubIssuesPRsPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();

  // Filter state
  const [viewType, setViewType] = React.useState<ViewType>("all");
  const [assignedToMe, setAssignedToMe] = React.useState(true);
  const [authoredByMe, setAuthoredByMe] = React.useState(true);

  // Build filter object
  const filter: GitHubItemsFilter = React.useMemo(
    () => ({
      itemType: viewType,
      assignedToMe,
      authoredByMe,
    }),
    [viewType, assignedToMe, authoredByMe],
  );

  // Fetch GitHub items
  const {
    data: githubData,
    isLoading,
    error,
    isFetching,
  } = useGitHubIssuesPRs(filter);
  const refreshData = useRefreshGitHubIssuesPRs();

  // Fetch conversations to find related ones
  const { data: conversations } = useSearchConversations(
    undefined,
    undefined,
    100,
  );

  // Create conversation mutation
  const { mutate: createConversation, isPending: isCreating } =
    useCreateConversation();

  // Track which item is being started
  const [startingItemKey, setStartingItemKey] = React.useState<string | null>(
    null,
  );

  // Find conversation related to a GitHub item
  const findRelatedConversation = React.useCallback(
    (item: GitHubItem): Conversation | undefined => {
      if (!conversations) return undefined;

      // Look for conversations that match the repository and have the PR number
      return conversations.find((conv) => {
        // Check if the conversation is for the same repository
        if (conv.selected_repository !== item.repo) return false;

        // Check if the conversation has the same PR/issue number in metadata
        if (conv.pr_number?.includes(item.number)) {
          return true;
        }

        // Check if the conversation title contains the issue/PR number
        if (conv.title.includes(`#${item.number}`)) {
          return true;
        }

        return false;
      });
    },
    [conversations],
  );

  // Handle starting a new session
  const handleStartSession = React.useCallback(
    (item: GitHubItem) => {
      const itemKey = `${item.repo}-${item.number}`;
      setStartingItemKey(itemKey);

      // Build the initial message based on item type
      let initialMessage: string;
      if (item.item_type === "issue") {
        initialMessage = `Please help me resolve issue #${item.number} in the ${item.repo} repository. 

First, understand the issue context by reading the issue description and any comments. Then, work on resolving the issue. If you successfully resolve it, please open a draft PR with the fix.

Issue: ${item.url}`;
      } else {
        initialMessage = `Please help me with PR #${item.number} in the ${item.repo} repository.

First, read the PR description, comments, and check the CI results. Then, address any issues found:
- Fix failing CI checks
- Resolve merge conflicts if any
- Address review comments

PR: ${item.url}`;
      }

      createConversation(
        {
          query: initialMessage,
          repository: {
            name: item.repo,
            gitProvider: item.git_provider,
          },
        },
        {
          onSuccess: (response) => {
            setStartingItemKey(null);
            navigate(`/conversations/${response.conversation_id}`);
          },
          onError: () => {
            setStartingItemKey(null);
          },
        },
      );
    },
    [createConversation, navigate],
  );

  // Handle resuming an existing session
  const handleResumeSession = React.useCallback(
    (conversation: Conversation) => {
      navigate(`/conversations/${conversation.conversation_id}`);
    },
    [navigate],
  );

  // Filter items based on view type
  const filteredItems = React.useMemo(() => {
    if (!githubData?.items) return [];

    let { items } = githubData;

    if (viewType === "issues") {
      items = items.filter((item) => item.item_type === "issue");
    } else if (viewType === "prs") {
      items = items.filter((item) => item.item_type === "pr");
    }

    return items;
  }, [githubData?.items, viewType]);

  return (
    <div className="h-full flex flex-col bg-transparent overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-[#525252]">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-xl font-semibold text-white">
            {t(I18nKey.GITHUB_ISSUES_PRS$TITLE)}
          </h1>
          <button
            type="button"
            onClick={refreshData}
            disabled={isFetching}
            className={cn(
              "px-3 py-1.5 text-sm font-medium rounded transition-colors",
              isFetching
                ? "bg-neutral-600 text-neutral-400 cursor-not-allowed"
                : "bg-neutral-700 hover:bg-neutral-600 text-white",
            )}
          >
            {isFetching ? (
              <LoadingSpinner size="small" />
            ) : (
              t(I18nKey.GITHUB_ISSUES_PRS$REFRESH)
            )}
          </button>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-4">
          {/* View type selector */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-neutral-400">
              {t(I18nKey.GITHUB_ISSUES_PRS$VIEW)}:
            </span>
            <select
              value={viewType}
              onChange={(e) => setViewType(e.target.value as ViewType)}
              className="px-3 py-1.5 text-sm rounded bg-[#25272D] border border-[#525252] text-white focus:outline-none focus:border-blue-500"
            >
              <option value="all">{t(I18nKey.GITHUB_ISSUES_PRS$ALL)}</option>
              <option value="issues">
                {t(I18nKey.GITHUB_ISSUES_PRS$ISSUES)}
              </option>
              <option value="prs">{t(I18nKey.GITHUB_ISSUES_PRS$PRS)}</option>
            </select>
          </div>

          {/* Checkboxes */}
          <label className="flex items-center gap-2 text-sm text-neutral-300 cursor-pointer">
            <input
              type="checkbox"
              checked={assignedToMe}
              onChange={(e) => setAssignedToMe(e.target.checked)}
              className="w-4 h-4 rounded border-[#525252] bg-[#25272D] text-blue-500 focus:ring-blue-500 focus:ring-offset-0"
            />
            {t(I18nKey.GITHUB_ISSUES_PRS$ASSIGNED_TO_ME)}
          </label>

          <label className="flex items-center gap-2 text-sm text-neutral-300 cursor-pointer">
            <input
              type="checkbox"
              checked={authoredByMe}
              onChange={(e) => setAuthoredByMe(e.target.checked)}
              className="w-4 h-4 rounded border-[#525252] bg-[#25272D] text-blue-500 focus:ring-blue-500 focus:ring-offset-0"
            />
            {t(I18nKey.GITHUB_ISSUES_PRS$AUTHORED_BY_ME)}
          </label>
        </div>

        {/* Cache info */}
        {githubData?.cached_at && (
          <div className="mt-2 text-xs text-neutral-500">
            {t(I18nKey.GITHUB_ISSUES_PRS$LAST_UPDATED)}:{" "}
            {new Date(githubData.cached_at).toLocaleTimeString()}
          </div>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6 custom-scrollbar">
        {isLoading && !githubData && (
          <div className="flex items-center justify-center h-full">
            <LoadingSpinner size="large" />
          </div>
        )}
        {!isLoading && error && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <p className="text-red-400 mb-2">
              {t(I18nKey.GITHUB_ISSUES_PRS$ERROR_LOADING)}
            </p>
            <button
              type="button"
              onClick={refreshData}
              className="px-4 py-2 text-sm font-medium rounded bg-blue-600 hover:bg-blue-700 text-white transition-colors"
            >
              {t(I18nKey.GITHUB_ISSUES_PRS$TRY_AGAIN)}
            </button>
          </div>
        )}
        {!isLoading && !error && filteredItems.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <p className="text-neutral-400">
              {t(I18nKey.GITHUB_ISSUES_PRS$NO_ITEMS)}
            </p>
          </div>
        )}
        {!isLoading && !error && filteredItems.length > 0 && (
          <div className="grid gap-4 max-w-4xl mx-auto">
            {filteredItems.map((item) => {
              const itemKey = `${item.repo}-${item.number}`;
              const relatedConversation = findRelatedConversation(item);

              return (
                <GitHubItemCard
                  key={itemKey}
                  item={item}
                  relatedConversation={relatedConversation}
                  onStartSession={() => handleStartSession(item)}
                  onResumeSession={() =>
                    relatedConversation &&
                    handleResumeSession(relatedConversation)
                  }
                  isStarting={isCreating && startingItemKey === itemKey}
                />
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default GitHubIssuesPRsPage;
