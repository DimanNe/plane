/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React from "react";
import { observer } from "mobx-react";
import type { Control, FormState } from "react-hook-form";
import { Controller } from "react-hook-form";
// plane imports
import { Field } from "@makeplane/propel/components/field";
import { Input } from "@makeplane/propel/components/input";
import { ETabIndices } from "@plane/constants";
// types
import { useTranslation } from "@plane/i18n";
import type { EditorRefApi } from "@plane/editor";
import { EmojiMenuInTextField } from "@plane/editor";
import type { TIssue } from "@plane/types";
// ui

// helpers
import { getTabIndex } from "@plane/utils";
// hooks
import { usePlatformOS } from "@/hooks/use-platform-os";
// local imports
import {
  moveCaretToDescriptionOnEnterOrArrowDown,
  useMoveCaretToTitleOnArrowUp,
} from "../../move-caret-between-title-and-description";

type TIssueTitleInputProps = {
  control: Control<TIssue>;
  issueTitleRef: React.MutableRefObject<HTMLInputElement | null>;
  formState: FormState<TIssue>;
  handleFormChange: () => void;
  descriptionEditorRef: React.RefObject<EditorRefApi | null>;
};

export const IssueTitleInput = observer(function IssueTitleInput(props: TIssueTitleInputProps) {
  const {
    control,
    issueTitleRef,
    formState: { errors },
    handleFormChange,
    descriptionEditorRef,
  } = props;
  // store hooks
  const { isMobile } = usePlatformOS();
  const { t } = useTranslation();
  useMoveCaretToTitleOnArrowUp(issueTitleRef, descriptionEditorRef);

  const { getIndex } = getTabIndex(ETabIndices.ISSUE_FORM, isMobile);

  const validateWhitespace = (value: string) => {
    if (value.trim() === "") {
      return t("title_is_required");
    }
    return undefined;
  };
  return (
    <div>
      <Controller
        control={control}
        name="name"
        rules={{
          validate: validateWhitespace,
          required: t("title_is_required"),
          maxLength: {
            value: 255,
            message: t("title_should_be_less_than_255_characters"),
          },
        }}
        render={({ field: { value, onChange, ref } }) => (
          <Field name="name" invalid={Boolean(errors.name)}>
            {/* No frame: the title and the description below it are one text, the title set apart by its size. */}
            <div className="work-item-dialog-title flex w-full">
              <Input
                size="2xl"
                id="name"
                name="name"
                type="text"
                // Chrome keeps what is typed into a field named "name" on any site, people's names and earlier
                // titles, and dropped them down over the title; a title is new text each time, as in the quick add.
                autoComplete="off"
                value={value}
                onChange={(e) => {
                  onChange(e.target.value);
                  handleFormChange();
                }}
                onKeyDown={(e) => moveCaretToDescriptionOnEnterOrArrowDown(e, descriptionEditorRef)}
                ref={issueTitleRef || ref}
                // FOR_REVIEWER: "Work item title", the words of the view's title, in place of "Title".
                placeholder={t("issue.title.label")}
                autoFocus
                tabIndex={getIndex("name")}
              />
              <EmojiMenuInTextField fieldRef={issueTitleRef} />
            </div>
          </Field>
        )}
      />
      <span className="text-caption-sm-medium text-danger-primary">{errors?.name?.message}</span>
    </div>
  );
});
