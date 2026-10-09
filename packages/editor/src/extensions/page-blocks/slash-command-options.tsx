/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { LinkPageOutline, PagesOutline } from "@makeplane/propel/icons";
// constants
import { ADDITIONAL_EXTENSIONS } from "@/constants/extensions";
// extensions
import type { TSlashCommandAdditionalOption } from "@/extensions";
// types
import type { IEditorPropsExtended } from "@/types";

export const getPageBlocksSlashCommandOptions = (props: IEditorPropsExtended): TSlashCommandAdditionalOption[] => {
  const { nestedPage, linkPages } = props;
  const createPage = nestedPage?.createPage;
  const options: TSlashCommandAdditionalOption[] = [];

  if (createPage) {
    options.push({
      commandKey: "page",
      key: "page",
      title: "Page",
      description: "Create a page nested in this page.",
      searchTerms: ["nested", "subpage", "child"],
      icon: <PagesOutline className="size-3.5" />,
      command: ({ editor, range }) => {
        editor.chain().focus().deleteRange(range).run();
        void createPage().then((pageId) => {
          if (!pageId || editor.isDestroyed) return;
          editor.chain().focus().insertContent({ type: ADDITIONAL_EXTENSIONS.NESTED_PAGE, attrs: { pageId } }).run();
          return;
        });
      },
      section: "general",
      pushAfter: "code",
    });
  }

  if (linkPages) {
    options.push({
      commandKey: "link-pages",
      key: "link-pages",
      title: "Link pages",
      description: "List the pages nested under a page or created by a member.",
      searchTerms: ["list", "index", "toc"],
      icon: <LinkPageOutline className="size-3.5" />,
      command: ({ editor, range }) =>
        editor.chain().focus().deleteRange(range).insertContent({ type: ADDITIONAL_EXTENSIONS.LINK_PAGES }).run(),
      section: "general",
      pushAfter: "page",
    });
  }

  return options;
};
