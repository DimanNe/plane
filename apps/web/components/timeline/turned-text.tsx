/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useRef, useState } from "react";
// plane imports
import { cn } from "@plane/utils";
// local imports
import type { TTextPart } from "./arrow-parts";
import { TimelineText, TimelineTextPart } from "./text";
import { getNearestPartIndex, usePartAnchor } from "./use-part-anchor";
import type { TWheelTurn } from "./use-wheel-turn";
import { useWheelNotches } from "./wheel";

type TPlace = { className: string; style: { left: number; top: number } };

type Props = {
  // where it stands by its bar
  place: TPlace;
  // What it says, and what a notch of the wheel changes on each part. A part without that only shows its value;
  // on a text of such parts alone the wheel does what it does anywhere.
  parts: TTextPart[];
  // a name for the text among everything the wheel turns: the turns of its parts are one operation
  turnKey: string;
  wheelTurn: TWheelTurn;
  // the pointer came onto the text, or left it
  onHover: (isOver: boolean) => void;
};

/**
 * A text beside a bar whose values the wheel turns: a date of the bar, the days it lasts, what the arrow to it
 * is. Its bar moves when a value is turned, and it would move with it, away from the pointer and from the wheel.
 * So it stays where it was when the pointer came, whatever its bar does, and returns to its bar when the pointer
 * has left.
 */
export function TimelineTurnedText(props: Props) {
  const { place, parts, turnKey, wheelTurn, onHover } = props;
  // refs
  // The part the pointer is on, and where the pointer was when it came there. A turn changes the text under a
  // pointer that rests, and another part may come under it: the wheel stays with its part until the pointer moves.
  const pointedRef = useRef<{ index: number; x: number; y: number }>(undefined);
  // states
  const [element, setElement] = useState<HTMLElement | null>(null);
  const [heldPlace, setHeldPlace] = useState<TPlace>();
  // derived values
  const isTurned = parts.some((part) => part.turn);
  const { className, style } = (isTurned && heldPlace) || place;
  const getPointedIndex = () => Math.min(pointedRef.current?.index ?? 0, parts.length - 1);
  const partAnchor = usePartAnchor(
    () => (isTurned && heldPlace ? element?.children[getPointedIndex()] : undefined),
    (distance) =>
      setHeldPlace((held) => held && { ...held, style: { ...held.style, left: held.style.left + distance } })
  );

  const point = (event: React.PointerEvent) => {
    const pointed = pointedRef.current;
    if (pointed?.x === event.clientX && pointed.y === event.clientY) return;
    partAnchor.release();
    const index = getNearestPartIndex(event.currentTarget, event.clientX);
    pointedRef.current = { index, x: event.clientX, y: event.clientY };
  };

  useWheelNotches(
    element,
    isTurned
      ? (direction, event) => {
          const turn = parts[getPointedIndex()].turn;
          const part = element?.children[getPointedIndex()];
          if (!turn || !part) return;
          partAnchor.hold(part, event.clientX);
          wheelTurn.turn(turnKey, (plan) => turn(plan, direction));
        }
      : undefined
  );

  return (
    <TimelineText
      ref={setElement}
      className={cn("pointer-events-auto", className)}
      style={style}
      onPointerEnter={(e) => {
        // a text that the wheel does not turn goes with its bar: during a drag the pointer may come over it
        if (isTurned) setHeldPlace(place);
        point(e);
        onHover(true);
      }}
      onPointerMove={point}
      onPointerLeave={() => {
        if (wheelTurn.getTurnedKey() === turnKey) wheelTurn.end(false);
        partAnchor.release();
        setHeldPlace(undefined);
        pointedRef.current = undefined;
        onHover(false);
      }}
    >
      {parts.map((part) => (
        <TimelineTextPart key={part.key} isActionable={!!part.turn} className={part.turn && "cursor-ns-resize"}>
          {part.label}
        </TimelineTextPart>
      ))}
    </TimelineText>
  );
}
