/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// plane imports
import { StateGroupIcon } from "@plane/blocks/icons";
// hooks
import { useProjectState } from "@/hooks/store/use-project-state";

type TStateCircleProps = {
  stateId: string | null | undefined;
  className?: string;
};

/**
 * Draws a state so that its progress reads at a glance in a list of work items. The sector of a
 * started state is position / (count + 1) among the project's started states: a project with one
 * started state shows it half filled, and a full disc is kept for completed and cancelled states.
 */
export const StateCircle = observer(function StateCircle(props: TStateCircleProps) {
  const { stateId, className = "size-4 shrink-0" } = props;
  // store hooks
  const { getStateById, getProjectStates } = useProjectState();
  // derived values
  const state = getStateById(stateId);
  const group = state?.group ?? "backlog";
  const color = state?.color ?? "currentColor";
  const startedStates = getProjectStates(state?.project_id)?.filter((s) => s.group === "started") ?? [];
  // a state outside the started group has position 0, so it gets no sector
  const position = startedStates.findIndex((s) => s.id === stateId) + 1;
  const sector = position / (startedStates.length + 1);

  if (group === "completed" || group === "cancelled")
    return <StateGroupIcon stateGroup={group} color={color} className={className} />;

  return (
    <svg viewBox="0 0 16 16" fill="none" stroke={color} className={className}>
      <circle cx="8" cy="8" r="6" strokeWidth="2" strokeDasharray={group === "backlog" ? "1.4 1.74" : undefined} />
      {sector > 0 && (
        <circle
          cx="8"
          cy="8"
          r="2"
          strokeWidth="4"
          pathLength="1"
          strokeDasharray={`${sector} 1`}
          transform="rotate(-90 8 8)"
        />
      )}
    </svg>
  );
});
