import { useConfig } from "#/hooks/query/use-config";

/**
 * Hook that returns the appropriate app title based on the APP_MODE.
 * Returns "OpenHands Cloud" for SaaS mode, "OpenHands" for OSS mode.
 */
export function useAppTitle() {
  const config = useConfig();
  const isSaasMode = config.data?.APP_MODE === "saas";

  return isSaasMode ? "OpenHands Cloud" : "OpenHands";
}
