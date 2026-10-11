/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { CSSProperties, PointerEventHandler, MouseEventHandler, ReactNode } from "react";
// plane imports
import { cn } from "@plane/utils";

type TTextProps = {
  ref?: (element: HTMLElement | null) => void;
  // what is wrong with the plan is red
  isDanger?: boolean;
  // what the thing that the text tells of is doing now, for whoever reads the page
  state?: string;
  // where it stands
  className?: string;
  style?: CSSProperties;
  // for a text that is held as a whole while the pointer is on any of its parts
  onPointerEnter?: PointerEventHandler;
  onPointerLeave?: PointerEventHandler;
  onPointerMove?: PointerEventHandler;
  // its parts
  children: ReactNode;
};

/**
 * A small text of the chart that tells a value: a date beside a bar, the days a bar lasts, what an arrow asks.
 * They are one kind of thing and look it. A text may stand on a bar, an arrow or another text, so the chart shows
 * through it: by a ground that is not solid, which costs nothing while bars move under it. And a text is made of
 * parts, because a part may be something to act on by itself: the parts stand side by side as two things, with
 * a line between them and the first of them on a ground a little darker.
 */
export function TimelineText(props: TTextProps) {
  const {
    ref,
    isDanger = false,
    state,
    className,
    style,
    onPointerEnter,
    onPointerLeave,
    onPointerMove,
    children,
  } = props;

  return (
    <div
      ref={ref}
      className={cn(
        "pointer-events-none flex rounded-sm border border-subtle-1 bg-accent-subtle/80 text-11 leading-4 font-medium whitespace-nowrap has-[[data-actionable]:hover,[data-held]]:border-accent-strong",
        isDanger ? "text-danger-primary" : "text-secondary",
        className
      )}
      style={style}
      data-state={state}
      onPointerEnter={onPointerEnter}
      onPointerLeave={onPointerLeave}
      onPointerMove={onPointerMove}
    >
      {children}
    </div>
  );
}

// A part that the wheel turns, under the pointer or where the wheel turns it from beside: it has to be seen at
// once among the parts and texts around it, and to say that the wheel acts there. It grows about its own middle,
// so it pushes nothing and stays under the pointer.
const TURNED_PART_CLASS_NAME = [
  // a tenth larger, on the solid ground of the accent, lifted by a shadow
  "[&:is(:hover,[data-held])]:z-10 [&:is(:hover,[data-held])]:scale-110 [&:is(:hover,[data-held])]:rounded-[3px] [&:is(:hover,[data-held])]:bg-accent-primary [&:is(:hover,[data-held])]:text-on-color [&:is(:hover,[data-held])]:shadow-raised-100",
  // An arrowhead above it and one below it, as on a field whose number is stepped up and down. They take no
  // pointer: beside the part they would be in the way of what is under them.
  "[&:is(:hover,[data-held])]:before:block [&:is(:hover,[data-held])]:after:block",
  "before:pointer-events-none before:absolute before:bottom-full before:left-1/2 before:mb-0.5 before:hidden before:-translate-x-1/2 before:border-x-4 before:border-b-4 before:border-x-transparent before:border-b-accent-strong before:content-['']",
  "after:pointer-events-none after:absolute after:top-full after:left-1/2 after:mt-0.5 after:hidden after:-translate-x-1/2 after:border-x-4 after:border-t-4 after:border-x-transparent after:border-t-accent-strong after:content-['']",
].join(" ");

type TPartProps = {
  ref?: (element: HTMLElement | null) => void;
  // It takes the wheel or a click. Under the pointer it then looks like something to act on; a part that takes
  // nothing stays as it is.
  isActionable?: boolean;
  // the wheel turns it: under the pointer it stands out strongly, and says so
  isTurned?: boolean;
  // the pointer is where the wheel turns this part: on it, or near it
  isHeld?: boolean;
  className?: string;
  onClick?: MouseEventHandler;
  onPointerEnter?: PointerEventHandler;
  onPointerLeave?: PointerEventHandler;
  children: ReactNode;
};

/** A part of a text of the chart. It takes the pointer when it is given something to do with it. */
export function TimelineTextPart(props: TPartProps) {
  const {
    ref,
    isActionable = false,
    isTurned = false,
    isHeld = false,
    className,
    onClick,
    onPointerEnter,
    onPointerLeave,
    children,
  } = props;
  const partProps = {
    ref,
    className: cn(
      "relative px-1.5 py-px not-first:border-l not-first:border-subtle-1 not-last:bg-layer-transparent-hover first:rounded-l-[3px] last:rounded-r-[3px]",
      {
        "pointer-events-auto": isActionable || !!onClick || !!onPointerEnter,
        "hover:bg-accent-subtle hover:text-primary": isActionable && !isTurned,
        [TURNED_PART_CLASS_NAME]: isTurned,
        "cursor-pointer": isActionable && !!onClick,
      },
      className
    ),
    "data-actionable": isActionable || undefined,
    "data-held": isHeld || undefined,
    onPointerEnter,
    onPointerLeave,
  };

  return onClick ? (
    <button type="button" {...partProps} onClick={onClick}>
      {children}
    </button>
  ) : (
    <span {...partProps}>{children}</span>
  );
}
