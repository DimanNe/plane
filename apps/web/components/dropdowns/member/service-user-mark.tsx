/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { AgentOutline } from "@makeplane/propel/icons";
// plane imports
import { useTranslation } from "@plane/i18n";
import type { IUserLite } from "@plane/types";

type TUser = Pick<IUserLite, "bot_type"> | undefined;

export const isServiceUser = (user: TUser) => user?.bot_type === "SERVICE_USER";

/** Tells a service user from a person where it is shown with its name. Shows nothing for a person. */
export function ServiceUserMark({ user }: { user: TUser }) {
  const { t } = useTranslation();

  if (!isServiceUser(user)) return null;
  return (
    <span role="img" aria-label={t("service_user")} title={t("service_user")} className="shrink-0 text-tertiary">
      <AgentOutline className="size-3.5" />
    </span>
  );
}
