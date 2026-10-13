/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { minBy, sortBy } from "lodash-es";
import { memo, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
// plane imports
import { getArrowMode, getDelayDays } from "@plane/blocks/timeline-schedule";
import type { TPlan, TSchedule, TScheduleArrow } from "@plane/blocks/timeline-schedule";
import { useLatestCallback } from "@plane/hooks";
import { useTranslation } from "@plane/i18n";
import { cn } from "@plane/utils";
// components
import { BLOCK_HEIGHT, HEADER_HEIGHT, SIDEBAR_WIDTH } from "@/components/gantt-chart/constants";
// local imports
import { getArrowModeParts } from "./arrow-parts";
import type { TTextPart } from "./arrow-parts";
import { ARROW_TEXT_CLASS_NAMES, getArrowState, getShownArrowState } from "./arrow-state";
import type { TArrowState, TArrowStates } from "./arrow-state";
import type { TArrowEnd, TArrowWaysProps, TDrawnArrow, TPoint } from "./arrows";
import { getArrowLayerStyle, STUB } from "./arrows";
import { BAR_HEIGHT, BAR_TOP, DATE_DISTANCE, DATE_WIDTH } from "./bar";
import type { TTimelineView } from "./scale";
import { getDayDistance, getDayOfDate, MIN_BAR_WIDTH } from "./scale";
import { TimelineText, TimelineTextPart } from "./text";
import { getNearestPartIndex, usePartAnchor } from "./use-part-anchor";
import type { TWheelTurn } from "./use-wheel-turn";
import { useWheelNotches } from "./wheel";

type TRect = { left: number; top: number; right: number; bottom: number };

type TPosition = { clientX: number; clientY: number; target?: EventTarget | null };

type TArrowText = { isDanger: boolean; parts: TTextPart[] };

/**
 * Where a text stands on its arrow: on a stretch of the way of the arrow, a distance from the corner that stretch
 * begins at; or beside the bar at an end of the arrow, a distance out from that end. A text that keeps its place
 * goes as far as that corner or that end goes, and no further.
 */
type TPlaceOnArrow = { stretch: number; distance: number } | { end: TArrowEnd; distance: number };

type TTextPlace = { on: TPlaceOnArrow; point: TPoint };

type TTranslate = (key: string, params?: Record<string, unknown>) => string;

type Props = Omit<TArrowWaysProps, "arrows"> & {
  drawnArrows: TDrawnArrow[];
  plan: TPlan;
  schedule: TSchedule;
  arrowStates: TArrowStates;
  // an operation is going on: the plan that is drawn is its preview
  isOperationGoingOn: boolean;
  // the fixed tasks that show the date of their start beside their bar
  datedTaskIds: Set<string>;
  // the task whose bar is dragged: both its dates show, and the arrows whose days count tell them beside those
  draggedTaskId: string | undefined;
  // the lines in view, in pixels from the top of the first line
  viewTop: number;
  viewBottom: number;
  wheelTurn: TWheelTurn;
  isEditable: boolean;
  // the element that scrolls the lines of the timeline
  scroll: HTMLElement | null;
  onClick: (arrow: TScheduleArrow, click: React.MouseEvent) => void;
  onHover: (arrow: TScheduleArrow | undefined) => void;
  // what an arrow has to explain while the pointer is over it, for the layer to show at the text of the arrow
  renderCard: (arrow: TScheduleArrow, text: HTMLElement) => ReactNode;
};

// The size a text takes on the timeline, for finding it a free place. A little less than it is drawn with, so
// that a text may touch a bar; and the height it is drawn with.
const TEXT_HEIGHT = 16;
const DRAWN_TEXT_HEIGHT = 20;
const CHARACTER_WIDTH = 6;
// how far along its arrow from the middle a text goes for a free place, and in what steps
const TEXT_REACH = 240;
const TEXT_STEP = 4;
// How far around a text that the wheel turns the wheel still turns it: about a centimetre, by which a hand that
// aims at a small text misses it.
const WHEEL_MARGIN = 36;

/**
 * What an arrow says over itself, always: what it is, "linked" or "in n d", in the parts that the wheel turns.
 * What the plan does not keep is red: a link whose edges are apart tells by how many days, and an arrow whose
 * fixed next task is too early for it tells that. An arrow that is kept by a task fixed on its day says nothing
 * over itself, because that day stands beside the bar of the task. Only while the pointer holds the text of an
 * arrow that the wheel has turned to "on" does that text stay, as "on" and the day, so that the wheel can turn on.
 */
const getArrowText = (
  arrow: TScheduleArrow,
  plan: TPlan,
  schedule: TSchedule,
  isHeldForWheel: boolean,
  t: TTranslate
): TArrowText | undefined => {
  const gap = schedule.gaps[arrow.id];
  if (gap === undefined) return;
  const mode = getArrowMode(plan, arrow);
  const modeParts = getArrowModeParts(arrow, mode, getDayOfDate(schedule.dates[arrow.nextId].start), t);
  if (mode === "on") {
    const isConflict = schedule.conflicts.some((conflict) => conflict.arrowId === arrow.id);
    if (isHeldForWheel) return { isDanger: isConflict, parts: modeParts };
    if (!isConflict) return;
    return {
      isDanger: true,
      parts: [{ key: "value", label: t("timeline.arrow.too_early", { days: getDelayDays(arrow.delay) - gap }) }],
    };
  }
  const apartLink = schedule.apartLinks.find((link) => link.arrowId === arrow.id);
  if (!apartLink) return { isDanger: false, parts: modeParts };
  return {
    isDanger: true,
    parts: [modeParts[0], { key: "value", label: t("timeline.arrow.apart", { days: apartLink.days }) }],
  };
};

const getDistance = ([x, y]: TPoint, [toX, toY]: TPoint) => Math.abs(toX - x) + Math.abs(toY - y);

/** The place on a way through the points that is at a distance from its start. */
const getPlaceAt = (points: TPoint[], distance: number): TTextPlace => {
  let rest = distance;
  let stretch = 0;
  // the last stretch has what the others leave
  while (stretch < points.length - 2 && rest > getDistance(points[stretch], points[stretch + 1])) {
    rest -= getDistance(points[stretch], points[stretch + 1]);
    stretch += 1;
  }
  const [x, y] = points[stretch];
  const [nextX, nextY] = points[stretch + 1];
  const length = getDistance(points[stretch], points[stretch + 1]) || 1;
  return {
    on: { stretch, distance: rest },
    point: [x + ((nextX - x) * rest) / length, y + ((nextY - y) * rest) / length],
  };
};

/** The place beside the bar at an end of a way: on the line of that bar, out from the edge the arrow meets. */
const getPlaceBeside = (points: TPoint[], end: TArrowEnd, distance: number): TTextPlace => {
  const [[endX, endY], [beforeX]] =
    end === "head" ? [points[points.length - 1], points[points.length - 2]] : [points[0], points[1]];
  return { on: { end, distance }, point: [endX - Math.sign(endX - beforeX) * distance, endY] };
};

const getLength = (points: TPoint[]) =>
  points.slice(1).reduce((length, point, index) => length + getDistance(points[index], point), 0);

/**
 * The place a text had on its arrow, on the way the arrow has now. None when that way has no such place: a bar
 * came so near that the arrow turns elsewhere, and the stretch is shorter or gone.
 */
const getKeptPlace = (points: TPoint[], on: TPlaceOnArrow): TTextPlace | undefined => {
  if ("end" in on) return getPlaceBeside(points, on.end, on.distance);
  const stretch = points.slice(on.stretch, on.stretch + 2);
  if (stretch.length < 2 || on.distance > getLength(stretch)) return;
  return { on, point: getPlaceAt(stretch, on.distance).point };
};

const isOver = (a: TRect, b: TRect) => a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;

/** What a text of a width takes when it stands with its middle at a place. */
const getTextRect = ([x, y]: TPoint, width: number, height = TEXT_HEIGHT): TRect => ({
  left: x - width / 2,
  top: y - height / 2,
  right: x + width / 2,
  bottom: y + height / 2,
});

/**
 * What a text that has its place keeps the next texts off: so much higher than a text is looked for with, that
 * the next one comes no nearer than the height texts are drawn with. Two texts may not touch as a text and a bar
 * may.
 */
const getPlacedTextRect = (place: TPoint, width: number): TRect =>
  getTextRect(place, width, 2 * DRAWN_TEXT_HEIGHT - TEXT_HEIGHT);

/**
 * What a text keeps clear of: the bars of the lines that are drawn, the dates that stand beside them, and the
 * stretch of every arrow beside the bar it leaves and beside the bar it reaches. There each arrow of an edge is
 * pointed at by itself, and its ends are taken.
 */
const getTakenRects = (props: Props): TRect[] => {
  const { drawnArrows, days, lineIndexes, firstLine, lastLine, pxPerDay, datedTaskIds, draggedTaskId } = props;
  const rects: TRect[] = drawnArrows.flatMap(({ points, hitWidth }) =>
    [points.slice(0, 2), points.slice(-2)].map(([[fromX, y], [toX]]) => ({
      left: Math.min(fromX, toX),
      top: y - hitWidth / 2,
      right: Math.max(fromX, toX),
      bottom: y + hitWidth / 2,
    }))
  );
  for (const [taskId, lineIndex] of lineIndexes) {
    const task = days[taskId];
    if (!task || lineIndex < firstLine - 1 || lineIndex > lastLine) continue;
    const left = getDayDistance(pxPerDay, task.start);
    const right = Math.max(getDayDistance(pxPerDay, task.end + 1), left + MIN_BAR_WIDTH);
    const top = lineIndex * BLOCK_HEIGHT + BAR_TOP;
    rects.push({ left, top, right, bottom: top + BAR_HEIGHT });
    // a date is as high as a text, in the middle of the line of its bar
    const dateTop = top + (BAR_HEIGHT - TEXT_HEIGHT) / 2;
    const dateWidth = DATE_DISTANCE + DATE_WIDTH;
    const isDragged = taskId === draggedTaskId;
    if (isDragged || datedTaskIds.has(taskId))
      rects.push({ left: left - dateWidth, top: dateTop, right: left, bottom: dateTop + TEXT_HEIGHT });
    if (isDragged) rects.push({ left: right, top: dateTop, right: right + dateWidth, bottom: dateTop + TEXT_HEIGHT });
  }
  return rects;
};

/** Whether a text of a width that stands with its middle at a point lies on nothing. */
const isFree = (point: TPoint, width: number, takenRects: TRect[]) => {
  const rect = getTextRect(point, width);
  return !takenRects.some((taken) => isOver(rect, taken));
};

/**
 * The place of a text on its arrow: as near to the middle of the arrow as a place is free, and clear of the ends
 * of the arrow, where the handles are. An arrow between bars that stand close has no free place on it: its text
 * then stands beside the bar the arrow leads to, on the line of that bar and out from the edge the arrow meets,
 * or so beside the bar it leads from. A place among the lines in view goes before one that is not; where no
 * place is free at all the text stands in the middle of the arrow.
 */
const getTextPlace = (
  points: TPoint[],
  width: number,
  takenRects: TRect[],
  viewTop: number,
  viewBottom: number
): TTextPlace => {
  const length = getLength(points);
  let freePlace: TTextPlace | undefined;
  /**
   * A place is taken when a text there would lie on something, and also when it is outside the lines in view: the
   * first free place of that second kind is kept for when no other is free.
   */
  const isTaken = (place: TTextPlace) => {
    if (!isFree(place.point, width, takenRects)) return true;
    freePlace ??= place;
    return place.point[1] < viewTop || place.point[1] > viewBottom;
  };
  for (let offset = 0; offset <= TEXT_REACH; offset += TEXT_STEP)
    for (const distance of offset ? [length / 2 + offset, length / 2 - offset] : [length / 2]) {
      if (distance < STUB || distance > length - STUB) continue;
      const place = getPlaceAt(points, distance);
      if (!isTaken(place)) return place;
    }
  // beside a bar: past the handle at the edge, each place a step further out than the one before
  for (const end of ["head", "tail"] as const)
    for (let step = 0; step <= TEXT_REACH; step += TEXT_STEP) {
      const place = getPlaceBeside(points, end, STUB + width / 2 + step);
      if (!isTaken(place)) return place;
    }
  return freePlace ?? getPlaceAt(points, length / 2);
};

type TTextProps = {
  ref: (element: HTMLElement | null) => void;
  arrow: TScheduleArrow;
  text: TArrowText;
  state: TArrowState;
  place: TPoint;
  // a click on it opens the control of its arrow
  isClickable: boolean;
  // the part that the wheel turns where the pointer is
  heldPartIndex: number | undefined;
  onClick: (arrow: TScheduleArrow, click: React.MouseEvent) => void;
  onHover: (arrow: TScheduleArrow | undefined) => void;
  renderCard: (arrow: TScheduleArrow, text: HTMLElement) => ReactNode;
};

function ArrowText(props: TTextProps) {
  const { ref, arrow, text, state, place, isClickable, heldPartIndex, onClick, onHover, renderCard } = props;
  // states
  const [element, setElement] = useState<HTMLElement | null>(null);

  return (
    <>
      <TimelineText
        ref={(textElement) => {
          setElement(textElement);
          return ref(textElement);
        }}
        isDanger={text.isDanger}
        state={state}
        className={cn(
          "absolute -translate-x-1/2 -translate-y-1/2",
          ARROW_TEXT_CLASS_NAMES[getShownArrowState(state, text.isDanger)]
        )}
        style={{ left: place[0], top: place[1] }}
      >
        {text.parts.map((part, index) => (
          <TimelineTextPart
            key={part.key}
            isActionable={isClickable || !!part.turn}
            isTurned={!!part.turn}
            isHeld={!!part.turn && index === heldPartIndex}
            onClick={isClickable ? (e) => onClick(arrow, e) : undefined}
            onPointerEnter={() => onHover(arrow)}
            onPointerLeave={() => onHover(undefined)}
          >
            {part.label}
          </TimelineTextPart>
        ))}
      </TimelineText>
      {/* beside the text, not in it: what a text holds are its parts */}
      {element && renderCard(arrow, element)}
    </>
  );
}

const ArrowTexts = memo(function ArrowTexts(props: Props) {
  const {
    drawnArrows,
    plan,
    schedule,
    arrowStates,
    isOperationGoingOn,
    viewTop,
    viewBottom,
    wheelTurn,
    isEditable,
    scroll,
    onClick,
    onHover,
    renderCard,
  } = props;
  // refs
  const elementsRef = useRef(new Map<string, HTMLElement>());
  // where each text stood on its arrow when the texts were last drawn
  const placesRef = useRef(new Map<string, TPlaceOnArrow>());
  // where the pointer was when the part that the wheel turns was last found
  const pointRef = useRef<{ x: number; y: number }>(undefined);
  // states
  // The text whose area the pointer is in: its place, the part of it that the wheel turns there, and whether the
  // wheel turns it at all. It stays at that place while the pointer is in the area, whatever its arrow does: a
  // text that moved away from the pointer would have to be found again.
  const [heldByPointer, setHeld] = useState<{
    arrowId: string;
    place: TPoint;
    partIndex: number;
    isForWheel: boolean;
  }>();
  // A gesture has the pointer to itself: the text the pointer was near when it began goes with its arrow, as
  // every other text does.
  const held = isEditable ? heldByPointer : undefined;
  // translation
  const { t } = useTranslation();

  // a short arrow has few places for its text and a long one many: the short ones are placed first
  const natural = sortBy(drawnArrows, ({ points }) => getLength(points)).flatMap(({ arrow, points }) => {
    const text = getArrowText(arrow, plan, schedule, arrow.id === held?.arrowId && held.isForWheel, t);
    return text ? [{ arrow, points, text }] : [];
  });
  // the text that the pointer holds stays also when its arrow is out of the lines that are drawn
  const heldArrow = held && plan.arrows.find((arrow) => arrow.id === held.arrowId);
  const heldText =
    natural.find(({ arrow }) => arrow.id === held?.arrowId)?.text ??
    (heldArrow && held.isForWheel ? getArrowText(heldArrow, plan, schedule, true, t) : undefined);
  const getWidth = (text: TArrowText) =>
    text.parts.reduce((width, part) => width + (part.label.length + 2) * CHARACTER_WIDTH, 0);
  // A text that has its place is in the way of the next ones: first the one the pointer holds, then the others.
  const takenRects = getTakenRects(props);
  if (held && heldText) takenRects.push(getPlacedTextRect(held.place, getWidth(heldText)));
  const placesOnArrows = new Map<string, TPlaceOnArrow>();
  const placedTexts: { arrow: TScheduleArrow; text: TArrowText; place: TPoint }[] = [];
  const takePlace = (arrow: TScheduleArrow, text: TArrowText, { on, point }: TTextPlace) => {
    placesOnArrows.set(arrow.id, on);
    placedTexts.push({ arrow, text, place: point });
    takenRects.push(getPlacedTextRect(point, getWidth(text)));
  };
  const unheldTexts = natural.filter(({ arrow }) => arrow.id !== held?.arrowId);
  // the text that the pointer holds has its place on its arrow again when the pointer lets it go
  const heldOn = held && placesRef.current.get(held.arrowId);
  if (held && heldOn) placesOnArrows.set(held.arrowId, heldOn);
  // A place is looked for from the middle of the arrow, and the middle moves when an operation makes the arrow
  // longer or shorter: a text that looked for its place at every change would go back and forth along its arrow.
  // During an operation a text keeps the place it has on its arrow for as long as that place is free. These
  // texts have their places first, so that none of them loses its place to a text that looks for one.
  if (isOperationGoingOn)
    for (const { arrow, points, text } of unheldTexts) {
      const on = placesRef.current.get(arrow.id);
      const place = on && getKeptPlace(points, on);
      if (place && isFree(place.point, getWidth(text), takenRects)) takePlace(arrow, text, place);
    }
  for (const { arrow, points, text } of unheldTexts)
    if (!placesOnArrows.has(arrow.id))
      takePlace(arrow, text, getTextPlace(points, getWidth(text), takenRects, viewTop, viewBottom));
  if (held && heldArrow && heldText) placedTexts.push({ arrow: heldArrow, text: heldText, place: held.place });

  useEffect(() => {
    placesRef.current = placesOnArrows;
  });

  const getHeldPart = (arrowId: string, partIndex: number) => {
    const parts = elementsRef.current.get(arrowId)?.children;
    return parts?.[Math.min(partIndex, parts.length - 1)];
  };
  const partAnchor = usePartAnchor(
    () => held && getHeldPart(held.arrowId, held.partIndex),
    (distance) => setHeld((text) => text && { ...text, place: [text.place[0] + distance, text.place[1]] })
  );

  /** The arrow whose text the wheel is turning; nothing while it turns something else of the timeline. */
  const getTurnedArrowId = () => {
    const turnedKey = wheelTurn.getTurnedKey();
    return placedTexts.some(({ arrow }) => arrow.id === turnedKey) ? turnedKey : undefined;
  };

  /**
   * The text that has a place of the window in its area, and its part that is nearest to that place; of several
   * texts the nearest. The area of a text that the wheel turns is the text and `WHEEL_MARGIN` on every side of
   * it: there the wheel turns its nearest part. The area of another text is the text. A text that is being turned
   * keeps the wheel while the place is in its area: its bars move, and another text may come nearer. Where the
   * pointer is on something else that takes the wheel, that has it.
   */
  const getTextNear = ({ clientX, clientY, target }: TPosition) => {
    if (!isEditable || !scroll) return;
    const part = target instanceof Element ? target.closest("[data-actionable]") : null;
    if (part && ![...elementsRef.current.values()].some((element) => element.contains(part))) return;
    const frame = scroll.getBoundingClientRect();
    // the list and the header of the timeline cover what is under them
    if (clientX < frame.left + SIDEBAR_WIDTH || clientY < frame.top + HEADER_HEIGHT) return;
    const getDistanceX = (box: DOMRect) => Math.max(box.left - clientX, clientX - box.right, 0);
    const textsNear = placedTexts.flatMap((placedText) => {
      const element = elementsRef.current.get(placedText.arrow.id);
      if (!element) return [];
      const box = element.getBoundingClientRect();
      const margin = placedText.text.parts.some(({ turn }) => turn) ? WHEEL_MARGIN : 0;
      const distanceY = Math.max(box.top - clientY, clientY - box.bottom, 0);
      if (getDistanceX(box) > margin || distanceY > margin) return [];
      const partIndex = getNearestPartIndex(element, clientX);
      return [{ ...placedText, partIndex, distance: Math.hypot(getDistanceX(box), distanceY) }];
    });
    return textsNear.find(({ arrow }) => arrow.id === getTurnedArrowId()) ?? minBy(textsNear, "distance");
  };

  /** Holds the text that has the pointer in its area, and saves what the wheel turned on the one it has left. */
  const holdTextNear = useLatestCallback((position: TPosition | undefined) => {
    const textNear = position && getTextNear(position);
    const turnedArrowId = getTurnedArrowId();
    if (turnedArrowId && textNear?.arrow.id !== turnedArrowId) wheelTurn.end(false);
    // A turn changes the text under a pointer that rests, and another part may come nearest: the wheel stays
    // with its part until the pointer moves.
    const hasMoved = position?.clientX !== pointRef.current?.x || position?.clientY !== pointRef.current?.y;
    pointRef.current = position && { x: position.clientX, y: position.clientY };
    if (hasMoved) partAnchor.release();
    if (!textNear) {
      if (held) setHeld(undefined);
      return;
    }
    const isHeldText = textNear.arrow.id === held?.arrowId;
    const partIndex = isHeldText && !hasMoved ? held.partIndex : textNear.partIndex;
    if (!isHeldText || partIndex !== held.partIndex)
      setHeld({
        arrowId: textNear.arrow.id,
        place: isHeldText ? held.place : textNear.place,
        partIndex,
        isForWheel: isHeldText ? held.isForWheel : textNear.text.parts.some(({ turn }) => turn),
      });
    return { ...textNear, partIndex, part: textNear.text.parts[Math.min(partIndex, textNear.text.parts.length - 1)] };
  });

  useEffect(() => {
    if (!scroll) return;
    const handlePointerLeave = () => holdTextNear(undefined);
    scroll.addEventListener("pointermove", holdTextNear);
    scroll.addEventListener("pointerleave", handlePointerLeave);
    return () => {
      scroll.removeEventListener("pointermove", holdTextNear);
      scroll.removeEventListener("pointerleave", handlePointerLeave);
    };
  }, [scroll, holdTextNear]);

  // in the area of a text that the wheel turns, the wheel does nothing else, also on a part that only tells
  useWheelNotches(
    scroll,
    (direction, event) => {
      const textNear = holdTextNear(event);
      const turn = textNear?.part.turn;
      const part = textNear && getHeldPart(textNear.arrow.id, textNear.partIndex);
      if (!textNear || !turn || !part) return;
      partAnchor.hold(part, event.clientX);
      wheelTurn.turn(textNear.arrow.id, (turnedPlan) => turn(turnedPlan, direction));
    },
    (event) => !!holdTextNear(event)?.text.parts.some(({ turn }) => turn)
  );

  // a text that went away with the pointer in its area tells nobody that the pointer has left it
  const isHeldTextGone = !!heldByPointer && !heldText;
  useEffect(() => {
    if (isHeldTextGone) setHeld(undefined);
  }, [isHeldTextGone]);

  return placedTexts.map(({ arrow, text, place }) => (
    <ArrowText
      key={arrow.id}
      ref={(element) => {
        if (element) elementsRef.current.set(arrow.id, element);
        return () => {
          elementsRef.current.delete(arrow.id);
        };
      }}
      arrow={arrow}
      text={isEditable ? text : { ...text, parts: text.parts.map(({ key, label }) => ({ key, label })) }}
      state={getArrowState(arrow.id, arrowStates)}
      place={place}
      isClickable={isEditable}
      heldPartIndex={arrow.id === held?.arrowId ? held.partIndex : undefined}
      onClick={(clickedArrow, click) => {
        wheelTurn.end(false);
        onClick(clickedArrow, click);
      }}
      onHover={onHover}
      renderCard={renderCard}
    />
  ));
});

/** The texts over the arrows: what each arrow is, without a click, and where the wheel changes it. */
export function TimelineArrowTexts(props: Omit<Props, "pxPerDay"> & { view: TTimelineView }) {
  const { view, ...textsProps } = props;

  return (
    <div className="absolute inset-y-0 left-0" style={getArrowLayerStyle(view)}>
      <ArrowTexts pxPerDay={view.pxPerDay} {...textsProps} />
    </div>
  );
}
