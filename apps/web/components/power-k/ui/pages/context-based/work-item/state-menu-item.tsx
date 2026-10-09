/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import type { IState } from "@plane/types";
// components
import { PowerKModalCommandItem } from "@/components/power-k/ui/modal/command-item";
import { StateCircle } from "@/components/project-states/state-circle";

export type TPowerKProjectStatesMenuItemsProps = {
  handleSelect: (stateId: string) => void;
  projectId: string | undefined;
  selectedStateId: string | undefined;
  states: IState[];
  workspaceSlug: string;
};

export const PowerKProjectStatesMenuItems = observer(function PowerKProjectStatesMenuItems(
  props: TPowerKProjectStatesMenuItemsProps
) {
  const { handleSelect, selectedStateId, states } = props;

  return (
    <>
      {states.map((state) => (
        <PowerKModalCommandItem
          key={state.id}
          iconNode={<StateCircle stateId={state.id} className="size-3.5 shrink-0" />}
          label={state.name}
          isSelected={state.id === selectedStateId}
          onSelect={() => handleSelect(state.id)}
        />
      ))}
    </>
  );
});
