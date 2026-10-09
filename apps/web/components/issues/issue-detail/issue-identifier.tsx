/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// plane imports
import type { TIssueIdentifierProps } from "@plane/types";
// hooks
import { useIssueDetail } from "@/hooks/store/use-issue-detail";
import { useProject } from "@/hooks/store/use-project";
import { useWorkItemTypes } from "@/hooks/store/use-work-item-types";
import { IdentifierText } from "@/components/issues/issue-detail/identifier-text";
import { WorkItemTypeLogo } from "@/components/work-item-types/type-logo";

export const IssueIdentifier = observer(function IssueIdentifier(props: TIssueIdentifierProps) {
  const { projectId, variant, size, displayProperties, enableClickToCopyIdentifier = false } = props;
  // store hooks
  const { getProjectIdentifierById } = useProject();
  const {
    issue: { getIssueById },
  } = useIssueDetail();
  const { getWorkItemTypeById } = useWorkItemTypes();
  // Determine if the component is using store data or not
  const isUsingStoreData = "issueId" in props;
  // derived values
  const issue = isUsingStoreData ? getIssueById(props.issueId) : null;
  const projectIdentifier = isUsingStoreData ? getProjectIdentifierById(projectId) : props.projectIdentifier;
  const issueSequenceId = isUsingStoreData ? issue?.sequence_id : props.issueSequenceId;
  const shouldRenderIssueID = displayProperties ? displayProperties.key : true;
  const shouldRenderIssueType = displayProperties ? displayProperties.issue_type : true;
  const issueType = getWorkItemTypeById(projectId, isUsingStoreData ? issue?.type_id : props.issueTypeId);
  const issueTypeLogo =
    shouldRenderIssueType && issueType ? <WorkItemTypeLogo logoProps={issueType.logo_props} /> : null;

  if (!shouldRenderIssueID) return issueTypeLogo;

  return (
    <div className="flex shrink-0 items-center space-x-2">
      {issueTypeLogo}
      <IdentifierText
        identifier={`${projectIdentifier}-${issueSequenceId}`}
        enableClickToCopyIdentifier={enableClickToCopyIdentifier}
        variant={variant}
        size={size}
      />
    </div>
  );
});
