/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { WorkItemsOutline } from "@makeplane/propel/icons";
// plane imports
import { Logo } from "@plane/blocks/emoji-icon-picker";
import type { TLogoProps } from "@plane/types";

type Props = {
  logoProps: TLogoProps | undefined;
  size?: number;
};

export function WorkItemTypeLogo(props: Props) {
  const { logoProps, size = 16 } = props;
  const iconSize = Math.round(size * 0.7);

  return (
    <span
      className="grid shrink-0 place-items-center rounded-sm bg-layer-2 text-tertiary"
      style={{ height: size, width: size, backgroundColor: logoProps?.icon?.background_color }}
    >
      {logoProps?.in_use ? (
        <Logo logo={logoProps} size={iconSize} type="lucide" />
      ) : (
        <WorkItemsOutline style={{ height: iconSize, width: iconSize }} />
      )}
    </span>
  );
}
