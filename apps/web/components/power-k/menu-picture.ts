/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

/**
 * A kind of menu that a key can choose in: how its open element is found, how its items are found in it, and the
 * attribute its item has while it is the highlighted one.
 */
type TMenuKind = { menu: string; item: string; highlighted: string };

/** The state menu of a line of the list and of the peek view. */
export const STATE_SELECT_MENU: TMenuKind = {
  menu: "[data-select-popup]",
  item: '[role="option"]',
  highlighted: "data-highlighted",
};

/** The palette, which is the menu of states on the work item page. */
export const PALETTE_MENU: TMenuKind = {
  menu: '[role="dialog"]:has([cmdk-root])',
  item: "[cmdk-item]",
  highlighted: "aria-selected",
};

const PICTURE_CLASS_NAME = "menu-choice-picture";
// The picture shows the chosen item for a moment, long enough to be seen, and then goes as a closing menu goes.
const SHOWN_FOR = 200;
const GOES_IN = 150;

/** What stands over what on the page is decided by the element with a layer of its own that holds the menu. */
const getLayer = (element: HTMLElement) => {
  for (let node: HTMLElement | null = element; node && node !== document.body; node = node.parentElement) {
    const layer = getComputedStyle(node).zIndex;
    if (layer !== "auto") return layer;
  }
  return "auto";
};

/**
 * A key has chosen an item of the open menu. The page is the person's again at that moment: the next key and the
 * next click are for what lies under the menu, and what the choice changes has changed. So the menu itself goes
 * at once, and what is still seen of it is a picture: a copy in its place, with the chosen item drawn as the one
 * under the pointer is, that takes no key and no pointer and removes itself.
 *
 * The caller closes the menu right after this.
 */
export const leavePictureOfChoice = (kind: TMenuKind, chosenItemText: string) => {
  const menu = [...document.querySelectorAll<HTMLElement>(kind.menu)].find(
    (element) => !element.classList.contains(PICTURE_CLASS_NAME)
  );
  if (!menu) return;

  // A menu that is still opening is drawn smaller than it is laid out, about its origin. The picture is the menu
  // as it is laid out.
  const drawn = menu.getBoundingClientRect();
  const [originX, originY] = getComputedStyle(menu).transformOrigin.split(" ").map(parseFloat);
  const shrunkBy = 1 - drawn.width / menu.offsetWidth;
  const picture = menu.cloneNode(true) as HTMLElement;
  for (const item of picture.querySelectorAll(kind.item)) {
    if (item.textContent?.trim() === chosenItemText) item.setAttribute(kind.highlighted, "true");
    else item.removeAttribute(kind.highlighted);
  }
  picture.classList.add(PICTURE_CLASS_NAME);
  picture.inert = true;
  Object.assign(picture.style, {
    position: "fixed",
    left: `${drawn.left - originX * shrunkBy}px`,
    top: `${drawn.top - originY * shrunkBy}px`,
    width: `${menu.offsetWidth}px`,
    height: `${menu.offsetHeight}px`,
    margin: "0",
    transform: "none",
    transition: "none",
    opacity: "1",
    zIndex: getLayer(menu),
  });
  // Closed without the moment its closing takes, the menu is off the page in the next frame.
  menu.style.transition = "none";
  document.body.append(picture);
  picture.animate(
    { opacity: [1, 1, 0], offset: [0, SHOWN_FOR / (SHOWN_FOR + GOES_IN), 1] },
    SHOWN_FOR + GOES_IN
  ).onfinish = () => picture.remove();
};
