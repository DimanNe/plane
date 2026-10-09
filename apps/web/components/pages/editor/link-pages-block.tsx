/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import Link from "next/link";
import { useParams } from "next/navigation";
// plane imports
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
  ComboboxSearch,
  ComboboxTrigger,
  useFilter,
} from "@makeplane/propel/components/combobox";
import { Select, SelectContent, SelectItem, SelectList, SelectTrigger } from "@makeplane/propel/components/select";
import { LinkPageOutline, PagesOutline } from "@makeplane/propel/icons";
import { Logo } from "@plane/blocks/emoji-icon-picker";
import type { TLinkPagesBlockAttributes } from "@plane/editor";
import { useTranslation } from "@plane/i18n";
import { getPageName } from "@plane/utils";
// components
import { MemberSelect } from "@/components/dropdowns/member/member-select";
// hooks
import { EPageStoreType, usePageStore } from "@/hooks/store";

const storeType = EPageStoreType.WORKSPACE;

const NESTING_LEVELS = ["all", "1", "2", "3", "4", "5", "6"];

type TOptionSelectProps = {
  label: string;
  options: { value: string; label: string }[];
  value: string;
  onChange: (value: string) => void;
};

function OptionSelect(props: TOptionSelectProps) {
  const { label, options, value, onChange } = props;

  return (
    <Select<string>
      items={options}
      value={value}
      onValueChange={(nextValue) => {
        if (nextValue) onChange(nextValue);
      }}
    >
      <SelectTrigger size="md" aria-label={label} />
      <SelectContent side="bottom" align="start">
        <SelectList>
          {options.map((option) => (
            <SelectItem key={option.value} value={option.value} size="md" label={option.label} />
          ))}
        </SelectList>
      </SelectContent>
    </Select>
  );
}

type TPageLinkProps = {
  pageId: string;
  level: number;
};

const PageLink = observer(function PageLink(props: TPageLinkProps) {
  const { pageId, level } = props;
  // store hooks
  const { getPageById } = usePageStore(storeType);
  // derived values
  const page = getPageById(pageId);

  if (!page) return null;

  return (
    <Link href={page.getRedirectionLink()} className="block" draggable={false}>
      {/* the editor opens the links it finds between a click and the closest div in a new tab */}
      <div
        className="flex items-center gap-2 rounded-sm px-2 py-1 text-13 text-primary hover:bg-layer-1-hover"
        style={{ paddingLeft: 8 + (level - 1) * 16 }}
      >
        <span className="grid size-4 flex-shrink-0 place-items-center">
          {page.logo_props?.in_use ? (
            <Logo logo={page.logo_props} size={14} type="lucide" />
          ) : (
            <PagesOutline className="size-3.5 text-tertiary" />
          )}
        </span>
        <span className="truncate">{getPageName(page.name)}</span>
      </div>
    </Link>
  );
});

type TNestedPageLinksProps = {
  parentPageId: string;
  level: number;
  maxLevel: number;
};

const NestedPageLinks = observer(function NestedPageLinks(props: TNestedPageLinksProps) {
  const { parentPageId, level, maxLevel } = props;
  // store hooks
  const { getChildPageIds } = usePageStore(storeType);

  return (
    <>
      {getChildPageIds(parentPageId).map((pageId) => (
        <div key={pageId}>
          <PageLink pageId={pageId} level={level} />
          {level < maxLevel && <NestedPageLinks parentPageId={pageId} level={level + 1} maxLevel={maxLevel} />}
        </div>
      ))}
    </>
  );
});

type Props = {
  attributes: TLinkPagesBlockAttributes;
  isEditable: boolean;
  updateAttributes: (attributes: Partial<TLinkPagesBlockAttributes>) => void;
};

export const LinkPagesBlock = observer(function LinkPagesBlock(props: Props) {
  const { attributes, isEditable, updateAttributes } = props;
  const { source, creator_ids: creatorIds } = attributes;
  // params
  const { pageId: currentPageId } = useParams();
  // plane hooks
  const { t } = useTranslation();
  const { contains } = useFilter();
  // store hooks
  const { sortedPages, getPageById, getChildPageIds } = usePageStore(storeType);
  // derived values
  // the pages nested under the page of the block until another page is picked
  const parentPageId = attributes.parent_id ?? currentPageId;
  const depth = String(attributes.depth);
  const parentPage = parentPageId ? getPageById(parentPageId) : undefined;
  const pages = sortedPages.filter((page) => !page.archived_at);
  const sourceOptions = [
    { value: "parent_pages", label: t("link_pages.sources.parent_pages") },
    { value: "created_by", label: t("link_pages.sources.created_by") },
  ];
  const nestingLevelOptions = NESTING_LEVELS.map((level) => ({
    value: level,
    label:
      level === "all"
        ? t("link_pages.nesting_level.all")
        : t("link_pages.nesting_level.count", { count: Number(level) }),
  }));
  const createdPageIds = pages
    .filter((page) => !!page.created_by && creatorIds.includes(page.created_by))
    .map((page) => page.id as string);
  const hasPages =
    source === "created_by" ? createdPageIds.length > 0 : !!parentPageId && getChildPageIds(parentPageId).length > 0;

  return (
    <div className="not-prose my-2 rounded-md border border-subtle p-3">
      <div className="flex flex-wrap items-center gap-2">
        <LinkPageOutline className="size-4 flex-shrink-0 text-tertiary" />
        <span className="text-13 font-medium text-secondary">{t("link_pages.title")}</span>
        {isEditable && (
          <>
            <OptionSelect
              label={t("link_pages.source")}
              options={sourceOptions}
              value={source}
              onChange={(value) => updateAttributes({ source: value as TLinkPagesBlockAttributes["source"] })}
            />
            {source === "created_by" ? (
              <MemberSelect
                multiple
                variant="select-md"
                value={creatorIds}
                onChange={(ids) => updateAttributes({ creator_ids: ids })}
                placeholder={t("link_pages.members_placeholder")}
              />
            ) : (
              <>
                <Combobox
                  items={pages}
                  value={parentPage ?? null}
                  onValueChange={(page) => {
                    if (page?.id) updateAttributes({ parent_id: page.id });
                  }}
                  itemToStringLabel={(page) => getPageName(page.name)}
                  itemToStringValue={(page) => page.id ?? ""}
                  isItemEqualToValue={(page, selectedPage) => page.id === selectedPage.id}
                  filter={(page, query) => contains(getPageName(page.name), query)}
                >
                  <ComboboxTrigger size="md" placeholder={t("link_pages.parent_page_placeholder")} />
                  <ComboboxContent
                    sizing="auto"
                    aria-label={t("link_pages.parent_page_placeholder")}
                    search={
                      <ComboboxSearch placeholder={t("common.search.label")} aria-label={t("common.search.label")} />
                    }
                  >
                    <ComboboxEmpty>{t("common.search.no_matches_found")}</ComboboxEmpty>
                    <ComboboxList aria-label={t("link_pages.parent_page_placeholder")}>
                      {(page: (typeof pages)[number]) => (
                        <ComboboxItem key={page.id} value={page} label={getPageName(page.name)} />
                      )}
                    </ComboboxList>
                  </ComboboxContent>
                </Combobox>
                <OptionSelect
                  label={t("link_pages.nesting_level.label")}
                  options={nestingLevelOptions}
                  value={depth}
                  onChange={(value) => updateAttributes({ depth: value })}
                />
              </>
            )}
          </>
        )}
      </div>
      <div className="mt-2">
        {source === "created_by"
          ? createdPageIds.map((pageId) => <PageLink key={pageId} pageId={pageId} level={1} />)
          : parentPageId && (
              <NestedPageLinks
                parentPageId={parentPageId}
                level={1}
                maxLevel={depth === "all" ? Infinity : Number(depth)}
              />
            )}
        {!hasPages && <p className="px-2 py-1 text-13 text-placeholder">{t("link_pages.empty")}</p>}
      </div>
    </div>
  );
});
