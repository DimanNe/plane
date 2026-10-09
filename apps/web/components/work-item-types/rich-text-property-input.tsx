/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useRef } from "react";
import { useParams } from "next/navigation";
// plane imports
import type { EditorRefApi } from "@plane/editor";
import { EFileAssetType } from "@plane/types";
// components
import { RichTextEditor } from "@/components/editor/rich-text";
// hooks
import { useEditorAsset } from "@/hooks/store/use-editor-asset";
import { useWorkspace } from "@/hooks/store/use-workspace";
// services
import { WorkspaceService } from "@/services/workspace.service";

const workspaceService = new WorkspaceService();

type Props = {
  id: string;
  value: string | undefined;
  onChange: (value: string) => void;
  projectId: string;
  placeholder: string;
  disabled: boolean;
  workItemId?: string;
  isDraft?: boolean;
  onAssetUpload?: (assetId: string) => void;
};

export function RichTextPropertyInput(props: Props) {
  const { id, value, onChange, projectId, placeholder, disabled, workItemId, isDraft, onAssetUpload } = props;
  // router
  const workspaceSlug = useParams().workspaceSlug?.toString() ?? "";
  // refs
  const editorRef = useRef<EditorRefApi>(null);
  const editedValue = useRef(value);
  // store hooks
  const { getWorkspaceBySlug } = useWorkspace();
  const { uploadEditorAsset, duplicateEditorAsset } = useEditorAsset();
  // derived values
  const workspaceId = getWorkspaceBySlug(workspaceSlug)?.id;
  const entityType = isDraft ? EFileAssetType.DRAFT_ISSUE_DESCRIPTION : EFileAssetType.ISSUE_DESCRIPTION;

  // The editor takes its content when it mounts. The same editor then serves the next work item of the
  // list or of the form, so a value that is not what was typed here is put into it.
  useEffect(() => {
    if (value === editedValue.current) return;
    editedValue.current = value;
    editorRef.current?.setEditorValue(value ?? "<p></p>");
  }, [value]);

  if (!workspaceId) return null;

  return (
    <div
      className="w-full rounded-md border-[0.5px] border-subtle"
      onBlur={(event) => {
        if (event.currentTarget.contains(event.relatedTarget)) return;
        if (editedValue.current !== undefined && editedValue.current !== value) onChange(editedValue.current);
      }}
    >
      <RichTextEditor
        ref={editorRef}
        id={id}
        initialValue={value ?? "<p></p>"}
        workspaceSlug={workspaceSlug}
        workspaceId={workspaceId}
        projectId={projectId}
        placeholder={placeholder}
        containerClassName="min-h-20 pt-3"
        {...(disabled
          ? { editable: false }
          : {
              editable: true,
              onChange: (_json: object, html: string) => {
                editedValue.current = html;
              },
              searchMentionCallback: async (payload) =>
                await workspaceService.searchEntity(workspaceSlug, { ...payload, project_id: projectId }),
              uploadFile: async (blockId, file) => {
                const { asset_id } = await uploadEditorAsset({
                  blockId,
                  data: { entity_identifier: workItemId ?? "", entity_type: entityType },
                  file,
                  projectId,
                  workspaceSlug,
                });
                onAssetUpload?.(asset_id);
                return asset_id;
              },
              duplicateFile: async (assetId) => {
                const { asset_id } = await duplicateEditorAsset({
                  assetId,
                  entityId: workItemId,
                  entityType,
                  projectId,
                  workspaceSlug,
                });
                onAssetUpload?.(asset_id);
                return asset_id;
              },
            })}
      />
    </div>
  );
}
