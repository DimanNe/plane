/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useParams } from "next/navigation";
import { AddFilterOutline, FilterOutline } from "@makeplane/propel/icons";
// plane imports
import type { TContextMenuItem } from "@plane/blocks/context-menu";
import { useTranslation } from "@plane/i18n";
import { buildWorkItemFilterExpressionFromConditions } from "@plane/shared-state";
import type { TWorkItemFilterProperty } from "@plane/types";
import { COLLECTION_OPERATOR, FILTER_FIELD_TYPE, LOGICAL_OPERATOR } from "@plane/types";
import { toFilterArray } from "@plane/utils";
// hooks
import { useWorkItemFilterInstance } from "@/hooks/store/work-item-filters/use-work-item-filter-instance";
import { useIssueStoreType } from "@/hooks/use-issue-layout-store";

/** Marks a control of a work item with the values of a filter property that it shows, for the menu entries below. */
export const filterValueProps = (property: TWorkItemFilterProperty, value: string | string[] | null | undefined) => ({
  "data-filter-property": property,
  "data-filter-value": [value ?? []].flat().join(),
});

/**
 * The entries of a work item's right-click menu for the control that was right clicked: two per value the control
 * shows, one that makes the value the whole filter of the list and one that adds it to the filter in force.
 */
export const useFilterMenuItems = () => {
  const { t } = useTranslation();
  const storeType = useIssueStoreType();
  const { projectId, cycleId, moduleId, viewId } = useParams();
  // a list keeps its filter under the id of what it lists: a view, a cycle, a module, else the project
  const filter = useWorkItemFilterInstance(storeType, (viewId ?? cycleId ?? moduleId ?? projectId)?.toString());

  return (target: Element): TContextMenuItem[] => {
    const property = target.closest<HTMLElement>("[data-filter-property]")?.dataset.filterProperty;
    const values = target.closest<HTMLElement>("[data-filter-value]")?.dataset.filterValue?.split(",") ?? [];
    const config = filter?.configManager.getConfigByProperty(property as TWorkItemFilterProperty);
    const fieldConfig = config?.isEnabled ? config.getOperatorConfig(COLLECTION_OPERATOR.IN) : undefined;
    if (!filter || !config || fieldConfig?.type !== FILTER_FIELD_TYPE.MULTI_SELECT) return [];
    const options = typeof fieldConfig.getOptions === "function" ? fieldConfig.getOptions() : fieldConfig.getOptions;
    const condition = filter.findFirstConditionByPropertyAndOperator(config.id, COLLECTION_OPERATOR.IN);
    const conditionValues = toFilterArray(condition?.value).map(String);

    return values.flatMap((value) => {
      const option = Array.isArray(options) ? options.find((item) => item.value === value) : undefined;
      if (!option) return [];
      const names = { property: config.label, value: option.label };
      const onlyThisValue = { property: config.id, operator: COLLECTION_OPERATOR.IN, value: [value] };
      return [
        {
          key: `show-only-${value}`,
          title: t("common.actions.show_only", names),
          icon: FilterOutline,
          action: () => {
            const expression = buildWorkItemFilterExpressionFromConditions({ conditions: [onlyThisValue] });
            if (expression) filter.resetExpression(expression, false);
            filter.toggleVisibility(true);
          },
        },
        {
          key: `add-to-filter-${value}`,
          title: t("common.actions.add_to_filter", names),
          icon: AddFilterOutline,
          disabled: conditionValues.includes(value),
          action: () => {
            if (condition) filter.updateConditionValue(condition.id, [...conditionValues, value]);
            else filter.addCondition(LOGICAL_OPERATOR.AND, onlyThisValue, false);
            filter.toggleVisibility(true);
          },
        },
      ];
    });
  };
};
