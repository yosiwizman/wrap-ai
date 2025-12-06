import { useEffect, useRef } from "react";
import { useActiveConversation } from "./query/use-active-conversation";
import { useAppTitle } from "./use-app-title";

/**
 * Hook that updates the document title based on the current conversation.
 * This ensures that any changes to the conversation title are reflected in the document title.
 * The suffix is automatically determined based on the APP_MODE (SaaS vs OSS).
 *
 * @param suffixOverride Optional suffix to override the default app title
 */
export function useDocumentTitleFromState(suffixOverride?: string) {
  const { data: conversation } = useActiveConversation();
  const appTitle = useAppTitle();
  const suffix = suffixOverride ?? appTitle;
  const lastValidTitleRef = useRef<string | null>(null);

  useEffect(() => {
    if (conversation?.title) {
      lastValidTitleRef.current = conversation.title;
      document.title = `${conversation.title} | ${suffix}`;
    } else {
      document.title = suffix;
    }

    return () => {
      document.title = suffix;
    };
  }, [conversation?.title, suffix]);
}
