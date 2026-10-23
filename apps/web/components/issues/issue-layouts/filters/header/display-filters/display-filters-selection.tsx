/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React from "react";
import { isEmpty } from "lodash-es";
import { observer } from "mobx-react";
import type {
  IIssueDisplayFilterOptions,
  IIssueDisplayProperties,
  ILayoutDisplayFiltersOptions,
  TIssueGroupByOptions,
} from "@plane/types";
// components
import {
  FilterDisplayProperties,
  FilterExtraOptions,
  FilterGroupBy,
  FilterOrderBy,
  FilterSubGroupBy,
} from "@/components/issues/issue-layouts/filters";
import { FilterHideClosedWorkItems } from "./hide-closed-work-items";
// hooks
import { useProject } from "@/hooks/store/use-project";

type Props = {
  displayFilters: IIssueDisplayFilterOptions | undefined;
  displayProperties: IIssueDisplayProperties;
  handleDisplayFiltersUpdate: (updatedDisplayFilter: Partial<IIssueDisplayFilterOptions>) => void;
  handleDisplayPropertiesUpdate: (updatedDisplayProperties: Partial<IIssueDisplayProperties>) => void;
  layoutDisplayFiltersOptions: ILayoutDisplayFiltersOptions | undefined;
  ignoreGroupedFilters?: Partial<TIssueGroupByOptions>[];
  cycleViewDisabled?: boolean;
  moduleViewDisabled?: boolean;
  isEpic?: boolean;
};

export const DisplayFiltersSelection = observer(function DisplayFiltersSelection(props: Props) {
  const {
    displayFilters,
    displayProperties,
    handleDisplayFiltersUpdate,
    handleDisplayPropertiesUpdate,
    layoutDisplayFiltersOptions,
    ignoreGroupedFilters = [],
    cycleViewDisabled = false,
    moduleViewDisabled = false,
    isEpic = false,
  } = props;
  // store hooks
  const { currentProjectDetails } = useProject();

  const isDisplayFilterEnabled = (displayFilter: keyof IIssueDisplayFilterOptions) =>
    Object.keys(layoutDisplayFiltersOptions?.display_filters ?? {}).includes(displayFilter);

  const computedIgnoreGroupedFilters: Partial<TIssueGroupByOptions>[] = [];
  if (cycleViewDisabled) {
    ignoreGroupedFilters.push("cycle");
  }
  if (moduleViewDisabled) {
    ignoreGroupedFilters.push("module");
  }
  if (!currentProjectDetails?.milestone_view) {
    ignoreGroupedFilters.push("milestone");
  }

  return (
    <div className="vertical-scrollbar relative scrollbar-sm flex h-full w-full flex-col gap-2 overflow-hidden overflow-y-auto px-2.5">
      {/* display properties */}
      {layoutDisplayFiltersOptions?.display_properties && layoutDisplayFiltersOptions.display_properties.length > 0 && (
        <div className="py-2">
          <FilterDisplayProperties
            displayProperties={displayProperties}
            displayPropertiesToRender={layoutDisplayFiltersOptions.display_properties}
            handleUpdate={handleDisplayPropertiesUpdate}
            cycleViewDisabled={cycleViewDisabled}
            moduleViewDisabled={moduleViewDisabled}
            isEpic={isEpic}
          />
        </div>
      )}

      {/* group by */}
      {isDisplayFilterEnabled("group_by") && (
        <div className="py-2">
          <FilterGroupBy
            displayFilters={displayFilters}
            groupByOptions={layoutDisplayFiltersOptions?.display_filters.group_by ?? []}
            handleUpdate={(val) =>
              handleDisplayFiltersUpdate({
                group_by: val,
              })
            }
            ignoreGroupedFilters={[...ignoreGroupedFilters, ...computedIgnoreGroupedFilters]}
          />
        </div>
      )}

      {/* sub-group by */}
      {isDisplayFilterEnabled("sub_group_by") &&
        displayFilters?.group_by !== null &&
        displayFilters?.layout === "kanban" && (
          <div className="py-2">
            <FilterSubGroupBy
              displayFilters={displayFilters}
              handleUpdate={(val) =>
                handleDisplayFiltersUpdate({
                  sub_group_by: val,
                })
              }
              subGroupByOptions={layoutDisplayFiltersOptions?.display_filters.sub_group_by ?? []}
              ignoreGroupedFilters={[...ignoreGroupedFilters, ...computedIgnoreGroupedFilters]}
            />
          </div>
        )}

      {/* order by */}
      {isDisplayFilterEnabled("order_by") && !isEmpty(layoutDisplayFiltersOptions?.display_filters?.order_by) && (
        <div className="py-2">
          <FilterOrderBy
            selectedOrderBy={displayFilters?.order_by}
            handleUpdate={(val) =>
              handleDisplayFiltersUpdate({
                order_by: val,
              })
            }
            orderByOptions={layoutDisplayFiltersOptions?.display_filters.order_by ?? []}
          />
        </div>
      )}

      {/* Options */}
      {layoutDisplayFiltersOptions?.extra_options.access && (
        <div className="py-2">
          <FilterExtraOptions
            selectedExtraOptions={{
              show_empty_groups: displayFilters?.show_empty_groups ?? true,
              sub_issue: displayFilters?.sub_issue ?? true,
            }}
            handleUpdate={(key, val) =>
              handleDisplayFiltersUpdate({
                [key]: val,
              })
            }
            enabledExtraOptions={layoutDisplayFiltersOptions?.extra_options.values}
          />
        </div>
      )}

      {/* closed work items */}
      {isDisplayFilterEnabled("hide_closed_for_more_than_days") && (
        <div className="py-2">
          <FilterHideClosedWorkItems
            hideClosedForMoreThanDays={displayFilters?.hide_closed_for_more_than_days}
            handleUpdate={(hide_closed_for_more_than_days) =>
              handleDisplayFiltersUpdate({ hide_closed_for_more_than_days })
            }
          />
        </div>
      )}
    </div>
  );
});
