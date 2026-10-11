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
 * parts, because a part may be something to act on by itself.
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
        "pointer-events-none flex overflow-hidden rounded-sm border border-subtle-1 bg-accent-subtle/80 text-11 leading-4 font-medium whitespace-nowrap has-[[data-actionable]:hover,[data-held]]:border-accent-strong",
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

type TPartProps = {
  ref?: (element: HTMLElement | null) => void;
  // It takes the wheel or a click. Under the pointer it then looks like something to act on; a part that takes
  // nothing stays as it is.
  isActionable?: boolean;
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
      "px-1.5 py-px",
      {
        "pointer-events-auto": isActionable || !!onClick || !!onPointerEnter,
        "hover:bg-accent-subtle hover:text-primary data-held:bg-accent-subtle data-held:text-primary": isActionable,
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
