import React from "react";
import { SettingsDropdownInput } from "../settings/settings-dropdown-input";
import { useSelectedOrganizationId } from "#/context/use-selected-organization";
import { useOrganizations } from "#/hooks/query/use-organizations";

export function OrgSelector() {
  const { orgId, setOrgId } = useSelectedOrganizationId();
  const { data: organizations, isLoading } = useOrganizations();

  React.useEffect(() => {
    if (!orgId && organizations?.length) {
      setOrgId(organizations[0].id);
    }
  }, [orgId, organizations, setOrgId]);

  return (
    <SettingsDropdownInput
      testId="org-selector"
      name="organization"
      placeholder="Please select an organization"
      selectedKey={orgId || ""}
      isLoading={isLoading}
      items={
        organizations?.map((org) => ({ key: org.id, label: org.name })) || []
      }
      onSelectionChange={(org) => {
        setOrgId(org ? org.toString() : null);
      }}
    />
  );
}
