/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { isEqual, pickBy } from "lodash-es";
// plane imports
import { DESCRIPTION_PREFIX_LENGTH, WORK_ITEM_PROPERTY_KEY_PREFIX } from "@plane/constants";
import { EWorkItemPropertyRelationType, EWorkItemPropertyType } from "@plane/types";
import type { TIssue, TWorkItemProperty, TWorkItemPropertyTypeKey, TWorkItemPropertyValue } from "@plane/types";

export const getWorkItemPropertyTypeKey = (
  property: Pick<TWorkItemProperty, "property_type" | "relation_type">
): TWorkItemPropertyTypeKey =>
  property.property_type === EWorkItemPropertyType.RELATION
    ? `RELATION_${property.relation_type ?? EWorkItemPropertyRelationType.USER}`
    : property.property_type;

export const getWorkItemPropertyKey = (propertyId: string) => `${WORK_ITEM_PROPERTY_KEY_PREFIX}${propertyId}` as const;

export const isWorkItemPropertyKey = (key: string) => key.startsWith(WORK_ITEM_PROPERTY_KEY_PREFIX);

export const isWorkItemPropertyReadOnlyText = (property: Pick<TWorkItemProperty, "property_type" | "settings">) =>
  property.property_type === EWorkItemPropertyType.TEXT && property.settings.display_format === "readonly";

// A formula is computed and a read-only text is fixed in the property, so neither takes a value from the user.
export const isWorkItemPropertyEditable = (property: Pick<TWorkItemProperty, "property_type" | "settings">) =>
  property.property_type !== EWorkItemPropertyType.FORMULA && !isWorkItemPropertyReadOnlyText(property);

// A layout can show a property on its cards and rows and in a column, except rich text, which needs room.
export const isWorkItemPropertyDisplayProperty = (property: Pick<TWorkItemProperty, "is_active" | "relation_type">) =>
  property.is_active && property.relation_type !== EWorkItemPropertyRelationType.RICH_TEXT;

export const isWorkItemPropertyValueEmpty = (value: TWorkItemPropertyValue | undefined) =>
  value === undefined || value === null || value === "" || (Array.isArray(value) && value.length === 0);

/**
 * @description Whether the options chosen on the levels of a cascading property leave a mandatory level
 * empty. A mandatory level needs an option only when the option chosen above it has options under it. The
 * server refuses such a selection, so it is not sent.
 */
export const hasWorkItemPropertyEmptyMandatoryLevel = (
  property: Pick<TWorkItemProperty, "settings" | "options">,
  selectedIds: string[]
) => {
  const parentId = selectedIds[selectedIds.length - 1] ?? null;
  return (
    !!property.settings.levels?.[selectedIds.length]?.is_required &&
    property.options.some((option) => option.parent === parentId)
  );
};

// A cascading property is not mandatory as a whole: it needs a value when its first level is mandatory.
export const isWorkItemPropertyValueRequired = (
  property: Pick<TWorkItemProperty, "is_required" | "settings" | "options">
) => property.is_required || hasWorkItemPropertyEmptyMandatoryLevel(property, []);

// The options chosen on the levels of a cascading property, as the path the server writes into activity.
export const getWorkItemPropertyPath = (
  property: Pick<TWorkItemProperty, "options">,
  value: TWorkItemPropertyValue | undefined
) =>
  (Array.isArray(value) ? value : [])
    .map((optionId) => property.options.find((option) => option.id === optionId)?.name)
    .join(" / ");

/**
 * @description The values a new work item of a type starts with: the server applies the same ones when a
 * request leaves a property out, so the create form shows them and sends what the user made of them.
 */
export const getWorkItemPropertyDefaultValues = (properties: TWorkItemProperty[]) => {
  const values: Record<string, TWorkItemPropertyValue> = {};
  for (const property of properties) {
    if (!property.is_active) continue;
    if (property.property_type === EWorkItemPropertyType.OPTION) {
      const optionIds = property.options.filter((option) => option.is_default).map((option) => option.id);
      if (optionIds.length) values[property.id] = property.is_multi ? optionIds : optionIds[0];
    } else if (property.property_type === EWorkItemPropertyType.DECIMAL && property.default_value.length)
      values[property.id] = Number(property.default_value[0]);
    else if (property.relation_type === EWorkItemPropertyRelationType.USER && property.default_value.length)
      values[property.id] = property.is_multi ? property.default_value : property.default_value[0];
  }
  return values;
};

/**
 * @description The start of a description as the list responses carry it: the text without its tags
 */
export const getDescriptionPrefix = (descriptionHtml: string | undefined) =>
  (descriptionHtml ?? "")
    .replace(/<\/(p|div|li|h[1-6]|blockquote|pre|tr|td|th)>|<br\s*\/?>/g, " ")
    .replace(/<[^>]+>/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, DESCRIPTION_PREFIX_LENGTH);

/**
 * @description The part of a work item update a store applies before the server answers. Property values go
 * over the stored ones, as the server merges them. A new type is left out: it takes effect together with what
 * the server makes of it, the default values of the type and a description that keeps the old type's values.
 * A new description changes its start, which the list shows.
 */
export const getOptimisticWorkItemUpdate = (workItem: TIssue | undefined, data: Partial<TIssue>): Partial<TIssue> => {
  const { type_id: _typeId, custom_properties: customProperties, ...optimisticData } = data;
  if (data.description_html !== undefined)
    optimisticData.description_prefix = getDescriptionPrefix(data.description_html);
  if (!customProperties) return optimisticData;
  return { ...optimisticData, custom_properties: { ...workItem?.custom_properties, ...customProperties } };
};

// The work item form edits a stored work item, unless it creates one or gives a stored one another type.
const isFormOnStoredType = (formData: Partial<TIssue>, storedWorkItem: Partial<TIssue> | undefined) =>
  !!storedWorkItem?.id && storedWorkItem.type_id === formData.type_id;

/**
 * @description The property values the work item form shows. A new work item, and a work item that gets
 * another type, start from the default values of the type, as they do on the server.
 */
export const getWorkItemFormPropertyValues = (
  properties: TWorkItemProperty[],
  formData: Partial<TIssue>,
  storedWorkItem: Partial<TIssue> | undefined
): Record<string, TWorkItemPropertyValue> =>
  isFormOnStoredType(formData, storedWorkItem)
    ? (formData.custom_properties ?? {})
    : { ...getWorkItemPropertyDefaultValues(properties), ...formData.custom_properties };

/**
 * @description The property values the work item form sends. The server merges them into the stored ones and
 * refuses a value of a property that is inactive or of another type, so an update carries only what the form
 * changed: a value another client wrote in the meantime stays.
 */
export const getWorkItemFormPropertyValuesToSubmit = (
  properties: TWorkItemProperty[],
  formData: Partial<TIssue>,
  storedWorkItem: Partial<TIssue> | undefined
): Record<string, TWorkItemPropertyValue> => {
  const isStoredType = isFormOnStoredType(formData, storedWorkItem);
  const editablePropertyIds = new Set(
    properties.filter((property) => property.is_active && isWorkItemPropertyEditable(property)).map(({ id }) => id)
  );
  return pickBy(
    formData.custom_properties,
    (value, propertyId) =>
      editablePropertyIds.has(propertyId) &&
      !(isStoredType && isEqual(value, storedWorkItem?.custom_properties?.[propertyId] ?? null))
  );
};

/**
 * @description The mandatory properties the work item form would send empty, by id. A new work item and one
 * that gets another type need all of them. An update of a stored work item is refused only for those it
 * clears: a mandatory property the type got later does not hold up the other edits of its work items.
 */
export const getWorkItemFormPropertyErrors = (
  properties: TWorkItemProperty[],
  formData: Partial<TIssue>,
  storedWorkItem: Partial<TIssue> | undefined
): Record<string, boolean> => {
  const isStoredType = isFormOnStoredType(formData, storedWorkItem);
  const values = isStoredType
    ? getWorkItemFormPropertyValuesToSubmit(properties, formData, storedWorkItem)
    : getWorkItemFormPropertyValues(properties, formData, storedWorkItem);
  const errors: Record<string, boolean> = {};
  for (const property of properties) {
    if (!property.is_active || !isWorkItemPropertyValueRequired(property) || (isStoredType && !(property.id in values)))
      continue;
    if (isWorkItemPropertyValueEmpty(values[property.id])) errors[property.id] = true;
  }
  return errors;
};

/**
 * @description The message of a response that refuses a property value. The server answers such a save
 * with `{ custom_properties: { <property id>: [message] } }`.
 */
export const getWorkItemPropertyErrorMessage = (error: unknown): string | undefined => {
  const propertyErrors = (error as { custom_properties?: Record<string, string[]> } | null | undefined)
    ?.custom_properties;
  return propertyErrors ? Object.values(propertyErrors)[0]?.[0] : undefined;
};
