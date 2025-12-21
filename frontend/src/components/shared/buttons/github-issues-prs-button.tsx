import { useTranslation } from "react-i18next";
import { I18nKey } from "#/i18n/declaration";
import { TooltipButton } from "./tooltip-button";
import PRIcon from "#/icons/u-pr.svg?react";

interface GitHubIssuesPRsButtonProps {
  disabled?: boolean;
}

export function GitHubIssuesPRsButton({
  disabled = false,
}: GitHubIssuesPRsButtonProps) {
  const { t } = useTranslation();

  const tooltip = t(I18nKey.SIDEBAR$GITHUB_ISSUES_PRS);

  return (
    <TooltipButton
      tooltip={tooltip}
      ariaLabel={tooltip}
      navLinkTo="/github-issues-prs"
      testId="github-issues-prs-button"
      disabled={disabled}
    >
      <PRIcon width={28} height={28} />
    </TooltipButton>
  );
}
