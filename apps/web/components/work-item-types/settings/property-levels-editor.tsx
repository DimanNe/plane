/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Button } from "@makeplane/propel/components/button";
import { Icon } from "@makeplane/propel/components/icon";
import { IconButton } from "@makeplane/propel/components/icon-button";
import { Input, InputGroup } from "@makeplane/propel/components/input";
import { Switch } from "@makeplane/propel/components/switch";
import { AddOutline, CloseOutline } from "@makeplane/propel/icons";
// plane imports
import { WORK_ITEM_PROPERTY_MAX_LEVELS, WORK_ITEM_PROPERTY_MIN_LEVELS } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import type { TWorkItemPropertyLevel } from "@plane/types";

type Props = {
  levels: TWorkItemPropertyLevel[];
  onChange: (levels: TWorkItemPropertyLevel[]) => void;
  // how many levels the saved property has; a new property has none
  savedLevelCount: number;
};

/** The levels of a cascading property: their names from the first level down, and which of them are mandatory. */
export function WorkItemPropertyLevelsEditor(props: Props) {
  const { levels, onChange, savedLevelCount } = props;
  // plane hooks
  const { t } = useTranslation();
  // derived values
  const i18nPrefix = "work_item_types.settings.properties.attributes.cascading";

  return (
    <div className="flex flex-col gap-2">
      <span className="text-caption-md-medium text-tertiary">
        {t(`${i18nPrefix}.${savedLevelCount ? "manage_levels" : "levels"}`)}
      </span>
      {levels.map((level, index) => (
        // oxlint-disable-next-line react/no-array-index-key -- levels keep their order and leave from the end
        <div key={index} className="flex items-center gap-2">
          <div className="grow">
            <InputGroup size="md">
              <Input
                size="md"
                maxLength={100}
                aria-label={t(`${i18nPrefix}.level_name`, { number: index + 1 })}
                value={level.name}
                onChange={(event) =>
                  onChange(
                    levels.map((other, otherIndex) =>
                      otherIndex === index ? { ...other, name: event.target.value } : other
                    )
                  )
                }
              />
            </InputGroup>
          </div>
          <label className="flex cursor-pointer items-center gap-1.5 text-caption-md-regular text-secondary">
            <Switch
              size="sm"
              aria-label={t("common.mandatory")}
              checked={level.is_required}
              // a mandatory level makes every level above it mandatory, so an optional one makes those below it optional
              onCheckedChange={(checked) =>
                onChange(
                  levels.map((other, otherIndex) =>
                    (checked ? otherIndex <= index : otherIndex >= index) ? { ...other, is_required: checked } : other
                  )
                )
              }
            />
            <span>{t("common.mandatory")}</span>
          </label>
          <IconButton
            variant="ghost"
            size="sm"
            icon={<Icon icon={CloseOutline} />}
            aria-label={t("common.remove")}
            disabled={index < WORK_ITEM_PROPERTY_MIN_LEVELS}
            // a level is deleted together with the levels below it
            onClick={() => onChange(levels.slice(0, index))}
          />
        </div>
      ))}
      {levels.length < WORK_ITEM_PROPERTY_MAX_LEVELS && (
        <div>
          <Button
            variant="secondary"
            size="sm"
            stretch="auto"
            icon={<Icon icon={AddOutline} />}
            label={t(`${i18nPrefix}.add_level`)}
            onClick={() =>
              onChange([
                ...levels,
                { name: t(`${i18nPrefix}.level_name`, { number: levels.length + 1 }), is_required: false },
              ])
            }
          />
        </div>
      )}
      {levels.length < savedLevelCount && (
        <p className="text-caption-sm-regular text-danger-primary">{t(`${i18nPrefix}.delete_level_warning`)}</p>
      )}
    </div>
  );
}
