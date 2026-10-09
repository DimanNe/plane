/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useMemo } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import useSWR from "swr";
// plane imports
import { MilestoneOutline } from "@makeplane/propel/icons";
import { PROJECT_MILESTONES } from "@plane/constants";
import { Select } from "@plane/blocks/select";
import type { SelectPaginationParams, SelectTooltip, SelectVariant } from "@plane/blocks/select";
import { useTranslation } from "@plane/i18n";
import type { TMilestone, TPaginatedResponse } from "@plane/types";
// hooks
import { useMilestone } from "@/hooks/store/use-milestone";
import { useUserPermissions } from "@/hooks/store/user";
// local imports
import { MilestoneStateIcon } from "./progress";

/** The "No milestone" row has no milestone behind it. */
type TMilestoneOption = { id: string; title: string; milestone?: TMilestone };

type Props = {
  projectId: string | undefined;
  value: string | null | undefined;
  onChange: (milestoneId: string | null) => void;
  variant: SelectVariant;
  disabled?: boolean;
  placeholder?: string;
  onClose?: () => void;
  /** Adds a "No milestone" row that clears the selection. Defaults to `true`. */
  clearable?: boolean;
  className?: string;
  tooltip?: SelectTooltip;
};

const toOption = (milestone: TMilestone): TMilestoneOption => ({
  id: milestone.id,
  title: milestone.title,
  milestone,
});

const getOptionIcon = (option: TMilestoneOption | undefined, className: string) =>
  option?.milestone ? (
    <MilestoneStateIcon milestone={option.milestone} className={className} />
  ) : (
    <MilestoneOutline className={className} />
  );

/**
 * Milestone picker of a work item. Resolves the project's milestones from the milestone store (fetched on
 * first open when the project has not been loaded yet) and filters them by the search query.
 */
export const MilestoneSelect = observer(function MilestoneSelect(props: Props) {
  const {
    projectId,
    value,
    onChange,
    variant,
    disabled = false,
    placeholder = "",
    onClose,
    clearable = true,
    className,
    tooltip,
  } = props;
  // router params
  const { workspaceSlug } = useParams();
  // store hooks
  const { getProjectMilestones, getMilestoneById, fetchMilestones } = useMilestone();
  const { getProjectRoleByWorkspaceSlugAndProjectId } = useUserPermissions();
  // translation
  const { t } = useTranslation();
  // derived values
  const clearLabel = t("project_milestones.no_milestone");
  const clearOption = useMemo<TMilestoneOption>(() => ({ id: "", title: clearLabel }), [clearLabel]);
  // Resolved in the observer render (not in a memo) so MobX re-renders when the milestone loads.
  const milestone = value ? getMilestoneById(value) : null;
  const selected = milestone ? toOption(milestone) : null;

  // workspace level layouts show work items of projects whose milestones are not loaded yet
  useSWR(
    workspaceSlug && projectId && value && !milestone
      ? PROJECT_MILESTONES(projectId, getProjectRoleByWorkspaceSlugAndProjectId(workspaceSlug.toString(), projectId))
      : null,
    workspaceSlug && projectId ? () => fetchMilestones(workspaceSlug.toString(), projectId) : null,
    { revalidateIfStale: false, revalidateOnFocus: false }
  );

  const getValues = useCallback(
    async ({ search }: SelectPaginationParams): Promise<TPaginatedResponse<TMilestoneOption[]>> => {
      if (!workspaceSlug || !projectId) return { results: [] };
      const milestones =
        getProjectMilestones(projectId) ?? (await fetchMilestones(workspaceSlug.toString(), projectId));
      const query = search?.trim().toLowerCase();
      const results = milestones.filter((m) => !query || m.title.toLowerCase().includes(query)).map(toOption);
      return { results, next_page_results: false };
    },
    [workspaceSlug, projectId, getProjectMilestones, fetchMilestones]
  );

  return (
    <Select<TMilestoneOption>
      infinite
      getValues={getValues}
      value={selected}
      onChange={(milestoneId) => onChange(milestoneId || null)}
      disabled={disabled}
      placeholder={placeholder}
      onClose={onClose}
      headerItems={clearable ? [clearOption] : undefined}
      getOptionValue={(option) => option.id}
      getOptionLabel={(option) => option.title}
      getOptionIcon={(option) => getOptionIcon(option, "size-4 shrink-0")}
    >
      <Select.Trigger<TMilestoneOption>
        disabled={disabled}
        variant={variant}
        className={className}
        prependIcon={(options) => getOptionIcon(options[0], "size-3.5 shrink-0")}
        label={(options) => options[0]?.title ?? placeholder}
        tooltip={tooltip === true ? { heading: t("common.milestone") } : tooltip}
      >
        {(options) => {
          const label = options[0]?.title ?? placeholder;
          return <>{!!label && <span className="min-w-0 grow truncate text-left">{label}</span>}</>;
        }}
      </Select.Trigger>
    </Select>
  );
});
