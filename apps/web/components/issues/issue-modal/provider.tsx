/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React, { useState } from "react";
import { isEmpty } from "lodash-es";
import { observer } from "mobx-react";
// plane imports
import type { ISearchIssueResponse, TIssue, TIssuePropertyValueErrors } from "@plane/types";
import { getWorkItemFormPropertyErrors } from "@plane/utils";
// components
import { IssueModalContext } from "@/components/issues/issue-modal/context";
// hooks
import { useWorkItemTypes } from "@/hooks/store/use-work-item-types";
import { useUser } from "@/hooks/store/user/user-user";

export type TIssueModalProviderProps = {
  templateId?: string;
  dataForPreload?: Partial<TIssue>;
  allowedProjectIds?: string[];
  children: React.ReactNode;
};

export const IssueModalProvider = observer(function IssueModalProvider(props: TIssueModalProviderProps) {
  const { children, allowedProjectIds, dataForPreload } = props;
  // states
  const [selectedParentIssue, setSelectedParentIssue] = useState<ISearchIssueResponse | null>(null);
  const [issuePropertyValueErrors, setIssuePropertyValueErrors] = useState<TIssuePropertyValueErrors>({});
  // store hooks
  const { projectsWithCreatePermissions } = useUser();
  const { getProjectWorkItemTypes, getWorkItemTypeProperties } = useWorkItemTypes();
  // derived values
  const projectIdsWithCreatePermissions = Object.keys(projectsWithCreatePermissions ?? {});

  return (
    <IssueModalContext.Provider
      // oxlint-disable-next-line react/jsx-no-constructed-context-values
      value={{
        allowedProjectIds: allowedProjectIds ?? projectIdsWithCreatePermissions,
        workItemTemplateId: null,
        setWorkItemTemplateId: () => {},
        isApplyingTemplate: false,
        setIsApplyingTemplate: () => {},
        selectedParentIssue,
        setSelectedParentIssue,
        issuePropertyValues: {},
        setIssuePropertyValues: () => {},
        issuePropertyValueErrors,
        setIssuePropertyValueErrors,
        // a new work item starts with the default type of its project; a stored one keeps the type it has
        getIssueTypeIdOnProjectChange: (projectId) =>
          dataForPreload?.id ? null : (getProjectWorkItemTypes(projectId)?.find((type) => type.is_default)?.id ?? null),
        getActiveAdditionalPropertiesLength: () => 0,
        handlePropertyValuesValidation: ({ watch }) => {
          const formData = watch();
          const errors = getWorkItemFormPropertyErrors(
            getWorkItemTypeProperties(formData.type_id),
            formData,
            dataForPreload
          );
          setIssuePropertyValueErrors(errors);
          return isEmpty(errors);
        },
        handleCreateUpdatePropertyValues: () => Promise.resolve(),
        handleProjectEntitiesFetch: () => Promise.resolve(),
        handleTemplateChange: () => Promise.resolve(),
        handleConvert: () => Promise.resolve(),
        handleCreateSubWorkItem: () => Promise.resolve(),
      }}
    >
      {children}
    </IssueModalContext.Provider>
  );
});
