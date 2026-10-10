/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { TPlan } from "@plane/blocks/timeline-schedule";

/** The functions of the schedule store that run an operation, for the project of the timeline. */
export type TTimelineOperation = {
  /** The plan for the gesture to change. Nothing while the operation before it is being saved. */
  begin: () => TPlan | undefined;
  /** Shows a changed copy of the plan that `begin` gave. */
  preview: (plan: TPlan) => void;
  commit: () => void;
  abort: () => void;
};

/** An operation of one step: a click that places a task, a choice that changes an arrow. */
export const runOperation = (operation: TTimelineOperation, change: (plan: TPlan) => TPlan) => {
  const plan = operation.begin();
  if (!plan) return;
  operation.preview(change(plan));
  operation.commit();
};
