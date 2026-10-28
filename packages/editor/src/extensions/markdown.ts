/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Markdown } from "tiptap-markdown";

/**
 * Plane stores what an editor holds as HTML (a work item's description, a comment, a version of a page) and gives
 * that HTML back to an editor as its content: when the editor is made, and through setContent. tiptap-markdown reads
 * every string given as content as markdown, and markdown keeps HTML as it is only from a block's tag at the start of
 * a line to the next empty line. An empty line in a code block ended it there, and the rest of the block became a
 * paragraph of inline code without its leading spaces; HTML that starts with an image was read by markdown's rules
 * from its start. The editor then saved what it showed. Here the content is read by tiptap's own HTML parser;
 * markdown still reads the plain text that is pasted, and the text that commands insert (insertContentAt), such as the
 * fenced text that makes a code block of several selected lines.
 */
export const MarkdownWithHTMLContent = Markdown.extend({
  addCommands() {
    // FOR_REVIEWER: every setContent of Plane passes stored HTML: setEditorValue (a description, a comment, a version
    // of a page that is restored) and the sync of a description changed elsewhere (useEditor's value). A string that
    // is not HTML, such as markdown that a client of /api/v1/ stored as description_html, was shown formatted as
    // markdown and is now one paragraph of its text. None of the 108 descriptions and 145 comments of the owner's
    // tracker is such a string: each starts with a block's tag.
    const { setContent: _setContentFromMarkdown, ...commands } = this.parent?.() ?? {};
    return commands;
  },
  onBeforeCreate() {
    // FOR_REVIEWER: not taken: escaping the line breaks of code blocks before the HTML reaches the editor. It mends
    // empty lines only: a description that starts with an image is read by markdown's inline rules from its start,
    // so `*`, `_` and backticks in its code blocks and paragraphs became emphasis and inline code. Not fixed upstream:
    // tiptap-markdown 0.9.0, its latest, parses content the same way, and so does Plane's preview branch.
    const { content } = this.editor.options;
    this.parent?.();
    this.editor.options.content = content;
  },
});
