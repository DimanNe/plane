/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useRef } from "react";
import { observer } from "mobx-react";
// plane imports
import { Input, InputGroup } from "@makeplane/propel/components/input";
import { ETabIndices } from "@plane/constants";
import { EmojiMenuInTextField } from "@plane/editor";
import { useTranslation } from "@plane/i18n";
import type { TIssue } from "@plane/types";

// helpers
import { getTabIndex } from "@plane/utils";
// hooks
import { usePlatformOS } from "@/hooks/use-platform-os";

type TInboxIssueTitle = {
  data: Partial<TIssue>;
  handleData: (issueKey: keyof Partial<TIssue>, issueValue: Partial<TIssue>[keyof Partial<TIssue>]) => void;
  isTitleLengthMoreThan255Character?: boolean;
};

export const InboxIssueTitle = observer(function InboxIssueTitle(props: TInboxIssueTitle) {
  const { data, handleData, isTitleLengthMoreThan255Character } = props;
  // hooks
  const { isMobile } = usePlatformOS();

  const { getIndex } = getTabIndex(ETabIndices.INTAKE_ISSUE_FORM, isMobile);
  const { t } = useTranslation();
  const titleRef = useRef<HTMLInputElement>(null);
  return (
    <div className="space-y-1">
      <InputGroup size="2xl">
        <Input
          size="2xl"
          id="name"
          name="name"
          type="text"
          // no earlier entries of fields named "name" offered over the title (see the dialog of a new work item)
          autoComplete="off"
          value={data?.name}
          onChange={(e) => handleData("name", e.target.value)}
          placeholder={t("title")}
          tabIndex={getIndex("name")}
          required
          ref={titleRef}
        />
        <EmojiMenuInTextField fieldRef={titleRef} />
      </InputGroup>
      {isTitleLengthMoreThan255Character && (
        <span className="text-11 text-danger-primary">{t("title_should_be_less_than_255_characters")}</span>
      )}
    </div>
  );
});
