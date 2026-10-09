/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export type IEditorExtensionOptions = unknown;

export type TNestedPageBlockConfig = {
  // creates a page nested under the page being edited and resolves to its id; an editor that only shows a document
  // has none
  createPage?: () => Promise<string | undefined>;
  widgetCallback: (props: {
    pageId: string;
    isEditable: boolean;
    isDeleteRequested: boolean;
    toggleDeleteRequest: (value: boolean) => void;
    deleteBlock: () => void;
  }) => React.ReactNode;
};

export type TLinkPagesBlockAttributes = {
  source: "parent_pages" | "created_by";
  parent_id: string | undefined;
  creator_ids: string[];
  depth: string;
};

export type TLinkPagesBlockConfig = {
  widgetCallback: (props: {
    attributes: TLinkPagesBlockAttributes;
    isEditable: boolean;
    updateAttributes: (attributes: Partial<TLinkPagesBlockAttributes>) => void;
  }) => React.ReactNode;
};

export type IEditorPropsExtended = {
  nestedPage?: TNestedPageBlockConfig;
  linkPages?: TLinkPagesBlockConfig;
};

export type ICollaborativeDocumentEditorPropsExtended = unknown;

export type TExtendedEditorCommands = "page" | "link-pages";

export type TExtendedCommandExtraProps = unknown;

export type TExtendedEditorRefApi = unknown;
