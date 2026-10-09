/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
// plane imports
import { setToast } from "@plane/blocks/toast";
import { useTranslation } from "@plane/i18n";
import type { TWorkItemProperty, TWorkItemPropertyOption } from "@plane/types";
// hooks
import { useWorkItemTypes } from "@/hooks/store/use-work-item-types";
// local imports
import { WorkItemPropertyOptionDeleteModal } from "./property-option-delete-modal";
import { WorkItemPropertyOptionsEditor } from "./property-options-editor";

type Props = {
  workspaceSlug: string;
  projectId: string;
  property: TWorkItemProperty;
  // the option of a cascading property that the listed options are under, and the level they are on
  parent?: TWorkItemPropertyOption;
  levelIndex?: number;
};

/**
 * The options of a saved property, each change saved as it is made: all options of a dropdown, or the options
 * of a cascading property under one option, each of which opens onto the options under it.
 */
export const WorkItemPropertySavedOptions = observer(function WorkItemPropertySavedOptions(props: Props) {
  const { workspaceSlug, projectId, property, parent, levelIndex = 0 } = props;
  // states
  const [optionInUse, setOptionInUse] = useState<TWorkItemPropertyOption | null>(null);
  // plane hooks
  const { t } = useTranslation();
  // store hooks
  const {
    fetchWorkItemPropertyOption,
    createWorkItemPropertyOption,
    updateWorkItemPropertyOption,
    deleteWorkItemPropertyOption,
  } = useWorkItemTypes();
  // derived values
  const options = property.options.filter((option) => option.parent === (parent?.id ?? null));
  const levels = property.settings.levels;

  const showOptionError = () => {
    setToast({
      type: "error",
      title: t("common.errors.default.title"),
      message: t("common.errors.default.message"),
    });
  };

  const handleRemove = async (optionId: string) => {
    try {
      const option = await fetchWorkItemPropertyOption(workspaceSlug, projectId, property.id, optionId);
      // removing an option that work items have selected takes it out of them, so it is confirmed
      if (option.work_item_count) setOptionInUse(option);
      else await deleteWorkItemPropertyOption(workspaceSlug, projectId, property.id, optionId);
    } catch {
      showOptionError();
    }
  };

  return (
    <>
      <WorkItemPropertyOptionsEditor
        label={levels && (parent?.sub_level_label || levels[levelIndex].name)}
        options={options}
        onAdd={(name) =>
          createWorkItemPropertyOption(workspaceSlug, projectId, property.id, {
            name,
            parent: parent?.id ?? null,
          }).catch(showOptionError)
        }
        onUpdate={(index, data) =>
          updateWorkItemPropertyOption(workspaceSlug, projectId, property.id, options[index].id, data).catch(
            showOptionError
          )
        }
        onRemove={(index) => handleRemove(options[index].id)}
        isCascading={!!levels}
        nextLevelName={levels?.[levelIndex + 1]?.name}
        renderOptionsUnder={(index) => (
          <WorkItemPropertySavedOptions
            workspaceSlug={workspaceSlug}
            projectId={projectId}
            property={property}
            parent={options[index]}
            levelIndex={levelIndex + 1}
          />
        )}
      />
      {optionInUse && (
        <WorkItemPropertyOptionDeleteModal
          option={optionInUse}
          onClose={() => setOptionInUse(null)}
          onConfirm={() =>
            deleteWorkItemPropertyOption(workspaceSlug, projectId, property.id, optionInUse.id)
              .then(() => setOptionInUse(null))
              .catch(showOptionError)
          }
        />
      )}
    </>
  );
});
