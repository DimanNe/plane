/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useCallback, useMemo } from "react";
import {
  AtOutline,
  CalendarOutline,
  CyclesOutline,
  DueDateOutline,
  LabelsOutline,
  MembersOutline,
  MilestoneOutline,
  ModuleOutline,
  PriorityOutline,
  ProjectsOutline,
  StartDateOutline,
  StateOutline,
  UserOutline,
} from "@makeplane/propel/icons";
// plane imports
import { Avatar } from "@makeplane/propel/components/avatar";
import { Logo } from "@plane/blocks/emoji-icon-picker";
import { CycleGroupIcon, PriorityIcon, StateGroupIcon } from "@plane/blocks/icons";
import { useTranslation } from "@plane/i18n";
import type {
  ICycle,
  IState,
  IUserLite,
  TFilterConfig,
  IIssueLabel,
  IModule,
  IProject,
  TWorkItemFilterProperty,
} from "@plane/types";
import { COLLECTION_OPERATOR, EQUALITY_OPERATOR } from "@plane/types";

import {
  createFilterConfig,
  createOperatorConfigEntry,
  getAssigneeFilterConfig,
  getCreatedAtFilterConfig,
  getCreatedByFilterConfig,
  getCycleFilterConfig,
  getDatePropertyFilterConfig,
  getFileURL,
  getLabelFilterConfig,
  getMemberMultiSelectConfig,
  getMentionFilterConfig,
  getModuleFilterConfig,
  getMultiSelectConfig,
  getPriorityFilterConfig,
  getProjectFilterConfig,
  getSingleSelectConfig,
  getStartDateFilterConfig,
  getStateFilterConfig,
  getStateGroupFilterConfig,
  getSubscriberFilterConfig,
  getTargetDateFilterConfig,
  getUpdatedAtFilterConfig,
  getWorkItemPropertyTypeKey,
  isLoaderReady,
} from "@plane/utils";
// components
import { WORK_ITEM_PROPERTY_TYPE_ICONS } from "@/components/work-item-types/property-icon";
// store hooks
import { useCycle } from "@/hooks/store/use-cycle";
import { useLabel } from "@/hooks/store/use-label";
import { useMember } from "@/hooks/store/use-member";
import { useMilestone } from "@/hooks/store/use-milestone";
import { useModule } from "@/hooks/store/use-module";
import { useProject } from "@/hooks/store/use-project";
import { useProjectState } from "@/hooks/store/use-project-state";
import { useWorkItemTypes } from "@/hooks/store/use-work-item-types";
// plane web imports
import { useFiltersOperatorConfigs } from "@/hooks/rich-filters/use-filters-operator-configs";

export type TWorkItemFiltersEntityProps = {
  workspaceSlug: string;
  cycleIds?: string[];
  labelIds?: string[];
  memberIds?: string[];
  moduleIds?: string[];
  projectId?: string;
  projectIds?: string[];
  stateIds?: string[];
};

export type TUseWorkItemFiltersConfigProps = {
  allowedFilters: TWorkItemFilterProperty[];
} & TWorkItemFiltersEntityProps;

export type TWorkItemFiltersConfig = {
  areAllConfigsInitialized: boolean;
  configs: TFilterConfig<TWorkItemFilterProperty>[];
  configMap: {
    [key in TWorkItemFilterProperty]?: TFilterConfig<TWorkItemFilterProperty>;
  };
  isFilterEnabled: (key: TWorkItemFilterProperty) => boolean;
  members: IUserLite[];
};

export const useWorkItemFiltersConfig = (props: TUseWorkItemFiltersConfigProps): TWorkItemFiltersConfig => {
  const { allowedFilters, cycleIds, labelIds, memberIds, moduleIds, projectId, projectIds, stateIds, workspaceSlug } =
    props;
  // store hooks
  const { loader: projectLoader, getProjectById } = useProject();
  const { getCycleById } = useCycle();
  const { getLabelById } = useLabel();
  const { getModuleById } = useModule();
  const { getProjectMilestones } = useMilestone();
  const { getStateById } = useProjectState();
  const { getUserDetails } = useMember();
  const { getProjectWorkItemProperties } = useWorkItemTypes();
  // translation
  const { t } = useTranslation();
  // derived values
  const operatorConfigs = useFiltersOperatorConfigs({ workspaceSlug });
  const filtersToShow = useMemo(() => new Set(allowedFilters), [allowedFilters]);
  const project = useMemo(() => getProjectById(projectId), [projectId, getProjectById]);
  const members: IUserLite[] | undefined = useMemo(
    () =>
      memberIds
        ? (memberIds.map((memberId) => getUserDetails(memberId)).filter((member) => member) as IUserLite[])
        : undefined,
    [memberIds, getUserDetails]
  );
  const workItemStates: IState[] | undefined = useMemo(
    () =>
      stateIds ? (stateIds.map((stateId) => getStateById(stateId)).filter((state) => state) as IState[]) : undefined,
    [stateIds, getStateById]
  );
  const workItemLabels: IIssueLabel[] | undefined = useMemo(
    () =>
      labelIds
        ? (labelIds.map((labelId) => getLabelById(labelId)).filter((label) => label) as IIssueLabel[])
        : undefined,
    [labelIds, getLabelById]
  );
  const cycles = useMemo(
    () => (cycleIds ? (cycleIds.map((cycleId) => getCycleById(cycleId)).filter((cycle) => cycle) as ICycle[]) : []),
    [cycleIds, getCycleById]
  );
  const modules = useMemo(
    () =>
      moduleIds ? (moduleIds.map((moduleId) => getModuleById(moduleId)).filter((module) => module) as IModule[]) : [],
    [moduleIds, getModuleById]
  );
  const projects = useMemo(
    () =>
      projectIds
        ? (projectIds.map((projectId) => getProjectById(projectId)).filter((project) => project) as IProject[])
        : [],
    [projectIds, getProjectById]
  );
  const milestones = projectId ? getProjectMilestones(projectId) : null;
  const milestoneLabel = t("common.milestone");
  const workItemProperties = getProjectWorkItemProperties(projectId);
  const areAllConfigsInitialized = useMemo(() => isLoaderReady(projectLoader), [projectLoader]);

  /**
   * Checks if a filter is enabled based on the filters to show.
   * @param key - The filter key.
   * @param level - The level of the filter.
   * @returns True if the filter is enabled, false otherwise.
   */
  const isFilterEnabled = useCallback((key: TWorkItemFilterProperty) => filtersToShow.has(key), [filtersToShow]);

  // state group filter config
  const stateGroupFilterConfig = useMemo(
    () =>
      getStateGroupFilterConfig<TWorkItemFilterProperty>("state_group")({
        isEnabled: isFilterEnabled("state_group"),
        filterIcon: StateOutline,
        getOptionIcon: (stateGroupKey) => <StateGroupIcon stateGroup={stateGroupKey} />,
        ...operatorConfigs,
      }),
    [isFilterEnabled, operatorConfigs]
  );

  // state filter config
  const stateFilterConfig = useMemo(
    () =>
      getStateFilterConfig<TWorkItemFilterProperty>("state_id")({
        isEnabled: isFilterEnabled("state_id") && workItemStates !== undefined,
        filterIcon: StateOutline,
        getOptionIcon: (state) => <StateGroupIcon stateGroup={state.group} color={state.color} />,
        states: workItemStates ?? [],
        ...operatorConfigs,
      }),
    [isFilterEnabled, workItemStates, operatorConfigs]
  );

  // label filter config
  const labelFilterConfig = useMemo(
    () =>
      getLabelFilterConfig<TWorkItemFilterProperty>("label_id")({
        isEnabled: isFilterEnabled("label_id") && workItemLabels !== undefined,
        filterIcon: LabelsOutline,
        labels: workItemLabels ?? [],
        getOptionIcon: (color) => (
          <span className="flex size-2.5 flex-shrink-0 rounded-full" style={{ backgroundColor: color }} />
        ),
        ...operatorConfigs,
      }),
    [isFilterEnabled, workItemLabels, operatorConfigs]
  );

  // cycle filter config
  const cycleFilterConfig = useMemo(
    () =>
      getCycleFilterConfig<TWorkItemFilterProperty>("cycle_id")({
        isEnabled: isFilterEnabled("cycle_id") && project?.cycle_view === true && cycles !== undefined,
        filterIcon: CyclesOutline,
        getOptionIcon: (cycleGroup) => <CycleGroupIcon cycleGroup={cycleGroup} className="h-3.5 w-3.5 flex-shrink-0" />,
        cycles: cycles ?? [],
        ...operatorConfigs,
      }),
    [isFilterEnabled, project?.cycle_view, cycles, operatorConfigs]
  );

  // module filter config
  const moduleFilterConfig = useMemo(
    () =>
      getModuleFilterConfig<TWorkItemFilterProperty>("module_id")({
        isEnabled: isFilterEnabled("module_id") && project?.module_view === true && modules !== undefined,
        filterIcon: ModuleOutline,
        getOptionIcon: () => <ModuleOutline className="h-3 w-3 flex-shrink-0" />,
        modules: modules ?? [],
        ...operatorConfigs,
      }),
    [isFilterEnabled, project?.module_view, modules, operatorConfigs]
  );

  // milestone filter config
  const milestoneFilterConfig = useMemo(
    () =>
      createFilterConfig<TWorkItemFilterProperty>({
        id: "milestone_id",
        label: milestoneLabel,
        isEnabled: isFilterEnabled("milestone_id") && project?.milestone_view === true && !!milestones,
        icon: MilestoneOutline,
        supportedOperatorConfigsMap: new Map([
          createOperatorConfigEntry(COLLECTION_OPERATOR.IN, { isEnabled: true, ...operatorConfigs }, (params) =>
            getMultiSelectConfig<{ id: string; title: string }, string, undefined>(
              {
                items: milestones ?? [],
                getId: (milestone) => milestone.id,
                getLabel: (milestone) => milestone.title,
                getValue: (milestone) => milestone.id,
                getIconData: () => undefined,
              },
              { singleValueOperator: EQUALITY_OPERATOR.EXACT, ...params },
              { getOptionIcon: () => <MilestoneOutline className="h-3 w-3 flex-shrink-0" /> }
            )
          ),
        ]),
      }),
    [isFilterEnabled, project?.milestone_view, milestones, milestoneLabel, operatorConfigs]
  );

  // assignee filter config
  const assigneeFilterConfig = useMemo(
    () =>
      getAssigneeFilterConfig<TWorkItemFilterProperty>("assignee_id")({
        isEnabled: isFilterEnabled("assignee_id") && members !== undefined,
        filterIcon: MembersOutline,
        members: members ?? [],
        getOptionIcon: (memberDetails) => (
          <Avatar
            alt={memberDetails.display_name}
            fallback={memberDetails.display_name?.[0]?.toUpperCase()}
            src={getFileURL(memberDetails.avatar_url)}
            size="2xs"
          />
        ),
        ...operatorConfigs,
      }),
    [isFilterEnabled, members, operatorConfigs]
  );

  // mention filter config
  const mentionFilterConfig = useMemo(
    () =>
      getMentionFilterConfig<TWorkItemFilterProperty>("mention_id")({
        isEnabled: isFilterEnabled("mention_id") && members !== undefined,
        filterIcon: AtOutline,
        members: members ?? [],
        getOptionIcon: (memberDetails) => (
          <Avatar
            alt={memberDetails.display_name}
            fallback={memberDetails.display_name?.[0]?.toUpperCase()}
            src={getFileURL(memberDetails.avatar_url)}
            size="2xs"
          />
        ),
        ...operatorConfigs,
      }),
    [isFilterEnabled, members, operatorConfigs]
  );

  // created by filter config
  const createdByFilterConfig = useMemo(
    () =>
      getCreatedByFilterConfig<TWorkItemFilterProperty>("created_by_id")({
        isEnabled: isFilterEnabled("created_by_id") && members !== undefined,
        filterIcon: UserOutline,
        members: members ?? [],
        getOptionIcon: (memberDetails) => (
          <Avatar
            alt={memberDetails.display_name}
            fallback={memberDetails.display_name?.[0]?.toUpperCase()}
            src={getFileURL(memberDetails.avatar_url)}
            size="2xs"
          />
        ),
        ...operatorConfigs,
      }),
    [isFilterEnabled, members, operatorConfigs]
  );

  // subscriber filter config
  const subscriberFilterConfig = useMemo(
    () =>
      getSubscriberFilterConfig<TWorkItemFilterProperty>("subscriber_id")({
        isEnabled: isFilterEnabled("subscriber_id") && members !== undefined,
        filterIcon: MembersOutline,
        members: members ?? [],
        getOptionIcon: (memberDetails) => (
          <Avatar
            alt={memberDetails.display_name}
            fallback={memberDetails.display_name?.[0]?.toUpperCase()}
            src={getFileURL(memberDetails.avatar_url)}
            size="2xs"
          />
        ),
        ...operatorConfigs,
      }),
    [isFilterEnabled, members, operatorConfigs]
  );

  // priority filter config
  const priorityFilterConfig = useMemo(
    () =>
      getPriorityFilterConfig<TWorkItemFilterProperty>("priority")({
        isEnabled: isFilterEnabled("priority"),
        filterIcon: PriorityOutline,
        getOptionIcon: (priority) => <PriorityIcon priority={priority} />,
        ...operatorConfigs,
      }),
    [isFilterEnabled, operatorConfigs]
  );

  // start date filter config
  const startDateFilterConfig = useMemo(
    () =>
      getStartDateFilterConfig<TWorkItemFilterProperty>("start_date")({
        isEnabled: true,
        filterIcon: StartDateOutline,
        ...operatorConfigs,
      }),
    [operatorConfigs]
  );

  // target date filter config
  const targetDateFilterConfig = useMemo(
    () =>
      getTargetDateFilterConfig<TWorkItemFilterProperty>("target_date")({
        isEnabled: true,
        filterIcon: DueDateOutline,
        ...operatorConfigs,
      }),
    [operatorConfigs]
  );

  // created at filter config
  const createdAtFilterConfig = useMemo(
    () =>
      getCreatedAtFilterConfig<TWorkItemFilterProperty>("created_at")({
        isEnabled: true,
        filterIcon: CalendarOutline,
        ...operatorConfigs,
      }),
    [operatorConfigs]
  );

  // updated at filter config
  const updatedAtFilterConfig = useMemo(
    () =>
      getUpdatedAtFilterConfig<TWorkItemFilterProperty>("updated_at")({
        isEnabled: true,
        filterIcon: CalendarOutline,
        ...operatorConfigs,
      }),
    [operatorConfigs]
  );

  // project filter config
  const projectFilterConfig = useMemo(
    () =>
      getProjectFilterConfig<TWorkItemFilterProperty>("project_id")({
        isEnabled: isFilterEnabled("project_id") && projects !== undefined,
        filterIcon: ProjectsOutline,
        projects: projects,
        getOptionIcon: (project) => <Logo logo={project.logo_props} size={12} />,
        ...operatorConfigs,
      }),
    [isFilterEnabled, projects, operatorConfigs]
  );

  // custom property filter configs
  const workItemPropertyFilterConfigs = useMemo(
    () =>
      workItemProperties.flatMap((property) => {
        const id: TWorkItemFilterProperty = `customproperty_${property.id}`;
        const propertyTypeKey = getWorkItemPropertyTypeKey(property);
        const params = {
          isEnabled: property.is_active,
          filterIcon: WORK_ITEM_PROPERTY_TYPE_ICONS[propertyTypeKey],
          ...operatorConfigs,
        };
        const getSelectFilterConfig = (operatorConfigEntry: ReturnType<typeof createOperatorConfigEntry>) =>
          createFilterConfig<TWorkItemFilterProperty>({
            id,
            label: property.display_name,
            isEnabled: params.isEnabled,
            icon: params.filterIcon,
            supportedOperatorConfigsMap: new Map([operatorConfigEntry]),
          });
        switch (propertyTypeKey) {
          case "OPTION":
            return getSelectFilterConfig(
              createOperatorConfigEntry(COLLECTION_OPERATOR.IN, params, (updatedParams) =>
                getMultiSelectConfig(
                  {
                    items: property.options,
                    getId: (option) => option.id,
                    getLabel: (option) => option.name,
                    getValue: (option) => option.id,
                  },
                  { singleValueOperator: EQUALITY_OPERATOR.EXACT, ...updatedParams }
                )
              )
            );
          case "RELATION_USER":
            return getSelectFilterConfig(
              createOperatorConfigEntry(
                COLLECTION_OPERATOR.IN,
                {
                  ...params,
                  members: members ?? [],
                  getOptionIcon: (memberDetails: IUserLite) => (
                    <Avatar
                      alt={memberDetails.display_name}
                      fallback={memberDetails.display_name?.[0]?.toUpperCase()}
                      src={getFileURL(memberDetails.avatar_url)}
                      size="2xs"
                    />
                  ),
                },
                (updatedParams) => getMemberMultiSelectConfig(updatedParams, EQUALITY_OPERATOR.EXACT)
              )
            );
          case "BOOLEAN":
            return getSelectFilterConfig(
              createOperatorConfigEntry(EQUALITY_OPERATOR.EXACT, params, (updatedParams) =>
                getSingleSelectConfig(
                  {
                    items: [
                      { value: "true", label: t("common.yes") },
                      { value: "false", label: t("common.no") },
                    ],
                    getId: (item) => item.value,
                    getLabel: (item) => item.label,
                    getValue: (item) => item.value,
                  },
                  updatedParams
                )
              )
            );
          case "DATETIME":
            return getDatePropertyFilterConfig<TWorkItemFilterProperty>(id)({
              ...params,
              propertyDisplayName: property.display_name,
            });
          default:
            return [];
        }
      }),
    [workItemProperties, members, operatorConfigs, t]
  );

  return {
    areAllConfigsInitialized,
    configs: [
      stateFilterConfig,
      stateGroupFilterConfig,
      assigneeFilterConfig,
      priorityFilterConfig,
      projectFilterConfig,
      mentionFilterConfig,
      labelFilterConfig,
      cycleFilterConfig,
      moduleFilterConfig,
      milestoneFilterConfig,
      startDateFilterConfig,
      targetDateFilterConfig,
      createdAtFilterConfig,
      updatedAtFilterConfig,
      createdByFilterConfig,
      subscriberFilterConfig,
      ...workItemPropertyFilterConfigs,
    ],
    configMap: {
      project_id: projectFilterConfig,
      state_group: stateGroupFilterConfig,
      state_id: stateFilterConfig,
      label_id: labelFilterConfig,
      cycle_id: cycleFilterConfig,
      module_id: moduleFilterConfig,
      milestone_id: milestoneFilterConfig,
      assignee_id: assigneeFilterConfig,
      mention_id: mentionFilterConfig,
      created_by_id: createdByFilterConfig,
      subscriber_id: subscriberFilterConfig,
      priority: priorityFilterConfig,
      start_date: startDateFilterConfig,
      target_date: targetDateFilterConfig,
      created_at: createdAtFilterConfig,
      updated_at: updatedAtFilterConfig,
    },
    isFilterEnabled,
    members: members ?? [],
  };
};
