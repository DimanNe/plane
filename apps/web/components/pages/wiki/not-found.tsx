/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import Link from "next/link";
import { useParams } from "next/navigation";
// plane imports
import { Button } from "@makeplane/propel/elements/button";
import { useTranslation } from "@plane/i18n";

export function WikiNotFound() {
  // params
  const { workspaceSlug } = useParams();
  // plane hooks
  const { t } = useTranslation();

  return (
    <div className="flex h-full w-full flex-col items-center justify-center">
      <h3 className="text-center text-16 font-semibold">{t("wiki.not_found.title")}</h3>
      <p className="mt-3 text-center text-13 text-secondary">{t("wiki.not_found.description")}</p>
      <Button
        variant="secondary"
        size="sm"
        stretch="auto"
        render={<Link href={`/${workspaceSlug}/wiki`} className="mt-5" />}
      >
        {t("wiki.not_found.cta")}
      </Button>
    </div>
  );
}
