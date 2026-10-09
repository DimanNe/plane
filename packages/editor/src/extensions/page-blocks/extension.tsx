/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { NodeSelection } from "@tiptap/pm/state";
import { ReactNodeViewRenderer, NodeViewWrapper } from "@tiptap/react";
import type { NodeViewProps } from "@tiptap/react";
// types
import type { TLinkPagesBlockAttributes, TLinkPagesBlockConfig, TNestedPageBlockConfig } from "@/types";
// local imports
import { LinkPagesExtensionConfig, NestedPageExtensionConfig } from "./extension-config";

type TNestedPageBlock = {
  getPos: NodeViewProps["getPos"];
  requestDelete: () => void;
};

type TNestedPageExtensionStorage = {
  // the editable blocks on screen: Backspace and Delete on a selected block ask it instead of removing it
  blocks: Set<TNestedPageBlock>;
};

type TNestedPageNodeViewProps = NodeViewProps & Pick<TNestedPageBlockConfig, "widgetCallback">;

function NestedPageNodeView(props: TNestedPageNodeViewProps) {
  const { deleteNode, editor, extension, getPos, node, widgetCallback } = props;
  // states
  const [isDeleteRequested, setIsDeleteRequested] = useState(false);
  // derived values
  const storage: TNestedPageExtensionStorage = extension.storage;

  useEffect(() => {
    if (!editor.isEditable) return;
    const block: TNestedPageBlock = { getPos, requestDelete: () => setIsDeleteRequested(true) };
    storage.blocks.add(block);
    return () => {
      storage.blocks.delete(block);
    };
  }, [editor.isEditable, getPos, storage]);

  return (
    <NodeViewWrapper>
      {widgetCallback({
        pageId: node.attrs.pageId,
        isEditable: editor.isEditable,
        isDeleteRequested,
        toggleDeleteRequest: setIsDeleteRequested,
        deleteBlock: deleteNode,
      })}
    </NodeViewWrapper>
  );
}

export function NestedPageExtension(props: TNestedPageBlockConfig) {
  return NestedPageExtensionConfig.extend<unknown, TNestedPageExtensionStorage>({
    addStorage() {
      return {
        blocks: new Set(),
      };
    },

    addKeyboardShortcuts() {
      const handleDelete = () => {
        // a block inside a wider selection is deleted with the selection
        const { selection } = this.editor.state;
        if (!(selection instanceof NodeSelection) || selection.node.type.name !== this.name) return false;
        const selectedBlock = [...this.storage.blocks].find((block) => block.getPos() === selection.from);
        if (!selectedBlock) return false;
        selectedBlock.requestDelete();
        return true;
      };

      return {
        Backspace: handleDelete,
        Delete: handleDelete,
      };
    },

    addNodeView() {
      return ReactNodeViewRenderer((nodeViewProps: NodeViewProps) => (
        <NestedPageNodeView {...nodeViewProps} widgetCallback={props.widgetCallback} />
      ));
    },
  });
}

export function LinkPagesExtension(props: TLinkPagesBlockConfig) {
  return LinkPagesExtensionConfig.extend({
    addNodeView() {
      return ReactNodeViewRenderer((nodeViewProps: NodeViewProps) => (
        <NodeViewWrapper>
          {props.widgetCallback({
            attributes: nodeViewProps.node.attrs as TLinkPagesBlockAttributes,
            isEditable: nodeViewProps.editor.isEditable,
            updateAttributes: nodeViewProps.updateAttributes,
          })}
        </NodeViewWrapper>
      ));
    },
  });
}
