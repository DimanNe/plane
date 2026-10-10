/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { ReactNode } from "react";
import { useState } from "react";
// plane imports
import type { TPlan } from "@plane/blocks/timeline-schedule";
// local imports
import { TimelineText, TimelineTextPart } from "./text";
import type { TWheelTurn } from "./use-wheel-turn";
import { useWheelNotches } from "./wheel";

type TPlace = { className: string; style: { left: number; top: number } };

type Props = {
  // where it stands by its bar
  place: TPlace;
  // What a notch of the wheel changes in the plan, and a name for what is turned. Without it the text only
  // shows its value, and the wheel does there what it does anywhere.
  turn: { key: string; change: (plan: TPlan, direction: 1 | -1) => TPlan } | undefined;
  wheelTurn: TWheelTurn;
  onHover: (isOver: boolean) => void;
  children: ReactNode;
};

/**
 * A text beside a bar whose value the wheel turns: a date of the bar, the days it lasts. Its bar moves when its
 * value is turned, and it would move with it, away from the pointer and from the wheel. So it stays where it
 * was when the pointer came, whatever its bar does, and returns to its bar when the pointer has left.
 */
export function TimelineTurnedText(props: Props) {
  const { place, turn, wheelTurn, onHover, children } = props;
  // states
  const [element, setElement] = useState<HTMLElement | null>(null);
  const [heldPlace, setHeldPlace] = useState<TPlace>();
  // derived values
  const { className, style } = (turn && heldPlace) || place;

  useWheelNotches(element, turn && ((direction) => wheelTurn.turn(turn.key, (plan) => turn.change(plan, direction))));

  return (
    <TimelineText className={className} style={style}>
      <TimelineTextPart
        ref={setElement}
        isActionable={!!turn}
        className={turn && "cursor-ns-resize"}
        onPointerEnter={() => {
          // a text that the wheel does not turn goes with its bar: during a drag the pointer may come over it
          if (turn) setHeldPlace(place);
          onHover(true);
        }}
        onPointerLeave={() => {
          if (turn && wheelTurn.getTurnedKey() === turn.key) wheelTurn.end(false);
          setHeldPlace(undefined);
          onHover(false);
        }}
      >
        {children}
      </TimelineTextPart>
    </TimelineText>
  );
}
