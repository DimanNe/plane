"""
The Timeline layout of a project's work items: the plan a check builds for it, what a person does on the chart,
and what the chart draws.

A task is found by the name of its work item, which a check chooses. What is read is what the chart draws, never
what React holds: the days of a bar from where it stands under the days of the header, an arrow from the bars its
two ends touch, a text over an arrow from the arrow it stands on.
"""

import datetime as dt
import typing as t

import playwright.sync_api as pw

import browser
import instance as ins
import steps

# The kinds of an arrow as the timeline names them, and the relation type that stores each from its previous task.
RELATION_TYPES: t.Dict[str, str] = {
    "end-start": "blocking",
    "start-start": "start_before",
    "end-end": "finish_before",
}
LINE: str = '[class~="group/line"]'
BAR: str = '[class~="group/bar"]'
# what a line of the list says of its task: start, end, whether it is fixed on its start; None for each without a bar
Task: t.TypeAlias = t.Tuple[t.Optional[str], t.Optional[str], t.Optional[bool]]
# previous task, next task, kind, delay in days or None for an arrow that is linked
Arrow: t.TypeAlias = t.Tuple[str, str, str, t.Optional[int]]
# an arrow as the chart draws it: previous task, next task, kind; its delay is told by the text over it
DrawnArrow: t.TypeAlias = t.Tuple[str, str, str]

# What the readings below share. The scale is read from the header: the days (or the weeks) of its lower part with
# the month and year of the upper part they stand under; a day is a whole number of days since 1970, as the
# timeline counts. An arrow is known by the lines its two ends lie on, and its kind by the edges of their bars the
# ends are nearer to. A text over an arrow belongs to the arrow whose way passes nearest to its middle.
CHART_JS: str = """
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
  "November", "December"];
const chart = document.querySelector('.vertical-scrollbar.isolate');
const readScale = () => {
  const header = chart.firstElementChild.lastElementChild;
  const months = [...header.querySelectorAll(':scope > div.top-0')]
    .map((cell) => [cell.getBoundingClientRect(), cell.textContent.trim().split(' ')]);
  const starts = [...header.querySelectorAll(':scope > div.top-7')].flatMap((cell) => {
    const left = cell.getBoundingClientRect().left;
    const month = months.find(([box]) => box.left <= left + 0.5 && left + 0.5 < box.right);
    const number = cell.textContent.trim().match(/(\\d+)$/);
    if (!month || !number) return [];
    return [[left, Date.UTC(Number(month[1][1]), MONTHS.indexOf(month[1][0]), Number(number[1])) / 864e5]];
  });
  const [first, last] = [starts[0], starts[starts.length - 1]];
  const pxPerDay = (last[0] - first[0]) / (last[1] - first[1]);
  return { pxPerDay, dayAt: (x) => first[1] + (x - first[0]) / pxPerDay, xOf: (day) => first[0] + (day - first[1]) * pxPerDay };
};
const dateOf = (day) => new Date(Math.round(day) * 864e5).toISOString().slice(0, 10);
const dayOf = (date) => Date.parse(date) / 864e5;
const nameOf = (line) => line.firstElementChild.querySelector('span.truncate').textContent;
const lines = () => [...document.querySelectorAll('[class~="group/line"]')]
  .sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top);
const barOf = (line) => {
  const bar = line.querySelector('[class~="group/bar"]');
  return bar && bar.style.display !== 'none' ? bar : null;
};
const lineAt = (y) => lines().find((line) => {
  const box = line.getBoundingClientRect();
  return box.top <= y && y < box.bottom;
});
const COLOURS = { 'text-placeholder': 'normal', 'text-accent-primary': 'accent', 'text-danger-primary': 'danger',
  'text-success-primary': 'changing', 'text-warning-primary': 'stopping' };
const arrows = () => [...document.querySelectorAll('g[class~="group/arrow"]')].map((group) => {
  const path = group.querySelector('path');
  const matrix = path.getScreenCTM();
  const length = path.getTotalLength();
  const at = (share) => {
    const point = path.getPointAtLength(length * share);
    return [point.x * matrix.a + point.y * matrix.c + matrix.e, point.x * matrix.b + point.y * matrix.d + matrix.f];
  };
  const endAt = ([x, y]) => {
    const line = lineAt(y);
    const bar = line && barOf(line);
    if (!bar) return [line ? nameOf(line) : null, '?'];
    const box = bar.getBoundingClientRect();
    return [nameOf(line), Math.abs(x - box.left) < Math.abs(x - box.right) ? 'start' : 'end'];
  };
  const [previous, from] = endAt(at(0));
  const [next, to] = endAt(at(1));
  const colour = Object.entries(COLOURS).find(([name]) => group.classList.contains(name));
  return { group, at, previous, next, kind: `${from}-${to}`, colour: colour ? colour[1] : null };
});
const findArrow = (previous, next) => arrows().find((arrow) => arrow.previous === previous && arrow.next === next);
const textLayers = () => chart.querySelector('div[class~="z-[3]"][class~="pointer-events-none"]')
  .querySelectorAll(':scope > div.absolute.inset-y-0.left-0');
// A text stands on the way of its arrow, or beside the bar at an end of the arrow: on the line of that bar, out from
// the edge the arrow meets, as far out as it takes to be free. So its middle lies on the way, or on the ray that goes
// from an end of the way along its first or its last stretch and on past it.
const textsOverArrows = () => {
  const ways = arrows().map((arrow) => {
    const points = [...Array(201).keys()].map((index) => arrow.at(index / 200));
    const ray = (end, before) => ({ end, side: Math.sign(before[0] - end[0]) });
    return { arrow, points, rays: [ray(points[0], points[2]), ray(points[200], points[198])] };
  });
  const distance = (way, [x, y]) => Math.min(
    ...way.points.map(([pointX, pointY]) => Math.hypot(x - pointX, y - pointY)),
    ...way.rays.map(({ end, side }) => ((x - end[0]) * side >= 0 ? Math.abs(y - end[1]) : Infinity)),
  );
  return [...textLayers()[0].querySelectorAll(':scope > div[data-state]')].map((text) => {
    const box = text.getBoundingClientRect();
    const middle = [box.left + box.width / 2, box.top + box.height / 2];
    const nearest = ways.reduce((best, way) => (!best || distance(way, middle) < distance(best, middle) ? way : best), null);
    const isOnIt = nearest && distance(nearest, middle) <= 6;
    return { text, arrow: isOnIt ? nearest.arrow : null, parts: [...text.children].map((part) => part.textContent) };
  });
};
"""


def make_js(body: str) -> str:
    """A function for the page with the readings above in reach."""
    return f"(argument) => {{ {CHART_JS} {body} }}"


BARS_JS: str = make_js(
    """
  const scale = readScale();
  return lines().map((line) => {
    const bar = barOf(line);
    if (!bar) return [nameOf(line), null, null, null];
    const box = bar.getBoundingClientRect();
    return [nameOf(line), dateOf(scale.dayAt(box.left)), dateOf(scale.dayAt(box.right) - 1),
      !!bar.querySelector('[class~="w-[3px]"]')];
  });"""
)
ARROWS_JS: str = make_js(
    "return arrows().map((arrow) => [arrow.previous, arrow.next, arrow.kind, arrow.colour, arrow.group.dataset.state]);"
)
TEXTS_JS: str = make_js(
    """
  return textsOverArrows().map(({ text, arrow, parts }) => [arrow ? [arrow.previous, arrow.next] : [null, null], parts,
    text.classList.contains('text-danger-primary'), text.dataset.state]);"""
)


def day(offset: int) -> str:
    """The date a number of days from today, as the API takes it."""
    return (dt.date.today() + dt.timedelta(days=offset)).isoformat()


def format_day(date: str) -> str:
    """A date as the chart writes it beside a bar and in the control of an arrow."""
    return dt.date.fromisoformat(date).strftime("%b %d, %Y")


def make_arrows(
    instance: ins.Instance,
    project: ins.Project,
    ids: t.Dict[str, str],
    arrows: t.Sequence[Arrow],
) -> None:
    previous: str
    following: str
    kind: str
    delay: t.Optional[int]
    for previous, following, kind, delay in arrows:
        ins.call_api(
            instance,
            "POST",
            f"/projects/{project.id}/work-items/{ids[previous]}/dependencies/",
            {
                "relation_type": RELATION_TYPES[kind],
                "work_item_ids": [ids[following]],
                "delay": delay,
            },
        )


def make_plan(
    instance: ins.Instance,
    project: ins.Project,
    tasks: t.Sequence[ins.JSONObject],
    arrows: t.Sequence[Arrow] = (),
) -> t.Dict[str, str]:
    """
    Work items in the order given, which is the order of the timeline's lines, and the arrows between them. A task
    is the fields of /api/v1/ (`start_date`, `target_date`, `is_start_fixed`, and `state` and `parent` by name).
    Returns their ids by name.
    """
    ids: t.Dict[str, str] = ins.make_work_items(instance, project, tasks)
    make_arrows(instance, project, ids, arrows)
    return ids


def read_stored(
    instance: ins.Instance, project: ins.Project
) -> t.Tuple[t.Dict[str, Task], t.List[Arrow]]:
    """The plan the server has stored: every task as `read_bars` gives it, and every arrow with its delay."""
    items: t.Dict[str, ins.JSONObject] = ins.read_work_items(instance, project)
    tasks: t.Dict[str, Task] = {}
    arrows: t.List[Arrow] = []
    name: str
    item: ins.JSONObject
    for name, item in items.items():
        is_placed: bool = item["start_date"] is not None
        tasks[name] = (
            item["start_date"],
            item["target_date"],
            item["is_start_fixed"] if is_placed else None,
        )
        dependencies: ins.JSONObject = ins.call_api(
            instance,
            "GET",
            f"/projects/{project.id}/work-items/{item['id']}/dependencies/",
        )
        kind: str
        relation_type: str
        for kind, relation_type in RELATION_TYPES.items():
            following: ins.JSONObject
            for following in dependencies[relation_type]:
                arrows.append((name, following["name"], kind, following["delay"]))
    return tasks, sorted(arrows, key=str)


def open_timeline(
    check: steps.Check,
    account: ins.Account,
    project: ins.Project,
    arrows: int = 0,
    **display_filters: t.Any,
) -> pw.Page:
    """The project's work items in the Timeline layout, in the manual order, every work item a line, with the bars
    drawn, and as many arrows as the plan has: the page loads them after the lines."""
    ins.set_display(
        check.instance,
        account,
        project,
        **{
            "layout": "gantt_chart",
            "group_by": None,
            "order_by": "sort_order",
            "show_only_leaves": False,
            **display_filters,
        },
    )
    page: pw.Page = browser.open_page(
        check, account, f"/{check.instance.workspace}/projects/{project.id}/issues/"
    )
    page.locator(LINE).first.wait_for()
    page.wait_for_function(
        "() => document.querySelector('.vertical-scrollbar.isolate div.top-7') !== null"
    )
    page.wait_for_function(
        "(count) => document.querySelectorAll('g[class~=\"group/arrow\"]').length >= count",
        arg=arrows,
    )
    return page


def read_bars(page: pw.Page) -> t.Dict[str, Task]:
    """Every line that is drawn, with the days its bar stands on and whether it bears the mark of a fixed start."""
    return {
        name: (start, end, is_fixed)
        for name, start, end, is_fixed in page.evaluate(BARS_JS)
    }


def read_lines(page: pw.Page) -> t.List[str]:
    """The names of the lines from top to bottom."""
    return [name for name, _, _, _ in page.evaluate(BARS_JS)]


def read_arrows(page: pw.Page) -> t.List[DrawnArrow]:
    """Every arrow that is drawn: previous task, next task, kind."""
    return sorted(
        (previous, following, kind)
        for previous, following, kind, _, _ in page.evaluate(ARROWS_JS)
    )


def read_arrow_looks(page: pw.Page) -> t.Dict[t.Tuple[str, str], t.Tuple[str, str]]:
    """The colour of every arrow (normal, accent, danger, changing, stopping) and its state, by its two tasks."""
    return {
        (previous, following): (colour, state)
        for previous, following, _, colour, state in page.evaluate(ARROWS_JS)
    }


def read_texts(page: pw.Page) -> t.Dict[t.Tuple[str, str], str]:
    """What the text over each arrow says, by the arrow's two tasks."""
    return {
        (previous, following): " ".join(parts)
        for (previous, following), parts, _, _ in page.evaluate(TEXTS_JS)
    }


def read_text_looks(page: pw.Page) -> t.Dict[t.Tuple[str, str], t.Tuple[bool, str]]:
    """Whether the text over each arrow is red, and the state it shows, by the arrow's two tasks."""
    return {
        (previous, following): (is_danger, state)
        for (previous, following), _, is_danger, state in page.evaluate(TEXTS_JS)
    }


def read_plan(page: pw.Page) -> t.Tuple[t.Dict[str, Task], t.List[DrawnArrow]]:
    """What the chart draws of the plan: the days of every bar, and the arrows."""
    return read_bars(page), read_arrows(page)


def bar(page: pw.Page, name: str) -> pw.Locator:
    return (
        page.locator(LINE)
        .filter(has=page.get_by_text(name, exact=True))
        .first.locator(BAR)
        .first
    )


def get_bar_point(page: pw.Page, name: str, part: str = "middle") -> browser.Point:
    """A place to press a bar: inside it near its start, or on one of its edges, where it is resized."""
    box: t.Optional[pw.FloatRect] = bar(page, name).bounding_box()
    if box is None:
        raise RuntimeError(f"no bar of {name!r} is drawn")
    middle: float = box["y"] + box["height"] / 2
    if part == "start":
        return box["x"] + 1, middle
    if part == "end":
        return box["x"] + box["width"] - 1, middle
    return box["x"] + min(box["width"] / 2, 20), middle


def get_px_per_day(page: pw.Page) -> float:
    return page.evaluate(make_js("return readScale().pxPerDay;"))


# The scale once the chart has stopped zooming, which it does over a moment after a notch of the wheel: the same for a
# third of a second of frames. Frames are counted by the time they take, since a window that draws as fast as it can
# draws many in a moment.
SCALE_AT_REST_JS: str = make_js(
    """
  return new Promise((done) => {
    let scale = readScale().pxPerDay;
    let since = performance.now();
    const look = (now) => {
      const current = readScale().pxPerDay;
      if (current !== scale) [scale, since] = [current, now];
      if (now - since >= 300) done(scale);
      else requestAnimationFrame(look);
    };
    requestAnimationFrame(look);
  });"""
)


def read_px_per_day_at_rest(page: pw.Page) -> float:
    return page.evaluate(SCALE_AT_REST_JS)


def get_day_x(page: pw.Page, date: str, part: float = 0.0) -> float:
    """Where on the window a day starts (part 0) or ends (part 1)."""
    return page.evaluate(
        make_js("return readScale().xOf(dayOf(argument[0]) + argument[1]);"),
        [date, part],
    )


def read_day_at(page: pw.Page, x: float) -> float:
    """The day under a place of the window, with the part of it that lies before the place."""
    return page.evaluate(make_js("return readScale().dayAt(argument);"), x)


def line(page: pw.Page, name: str) -> pw.Locator:
    return page.locator(LINE).filter(has=page.get_by_text(name, exact=True)).first


def get_line_y(page: pw.Page, name: str) -> float:
    return browser.get_point(line(page, name))[1]


def get_entry_point(page: pw.Page, name: str) -> browser.Point:
    """A point on the first letters of a task's name in the list at the left, where a press is the line's and no
    control's."""
    return browser.get_point(line(page, name).locator("span.truncate").first, across=0)[
        0
    ] + 4, get_line_y(page, name)


def get_edge_x(page: pw.Page, name: str, edge: str) -> float:
    box: t.Optional[pw.FloatRect] = bar(page, name).bounding_box()
    if box is None:
        raise RuntimeError(f"no bar of {name!r} is drawn")
    return box["x"] if edge == "start" else box["x"] + box["width"]


def get_handle_point(page: pw.Page, name: str, edge: str) -> browser.Point:
    """The middle of the handle at an edge of a bar, which shows while the pointer is over the bar."""
    return browser.get_point(
        bar(page, name).get_by_role("button", name=f"Draw an arrow from the {edge}")
    )


def get_half_point(page: pw.Page, name: str, edge: str) -> browser.Point:
    """A point over the half of a bar whose handle takes an arrow that is brought there."""
    return browser.get_point(bar(page, name), across=0.25 if edge == "start" else 0.75)


# A point on the way of the arrow between two tasks where nothing else lies on it, as near to a part of its length
# as there is one.
ARROW_POINT_JS: str = make_js(
    """
  const [previous, next, part] = argument;
  const arrow = findArrow(previous, next);
  if (!arrow) return null;
  const shares = [...Array(39).keys()].map((index) => (index + 1) / 40).sort((a, b) => Math.abs(a - part) - Math.abs(b - part));
  for (const share of shares) {
    const point = arrow.at(share);
    if (arrow.group.contains(document.elementFromPoint(...point))) return point;
  }
  return null;"""
)
# Where an end of an arrow is taken: the small circle on the arrow near its bar, the tail at the previous task and
# the head at the next one.
ARROW_END_JS: str = make_js(
    """
  const [previous, next, index] = argument;
  const circle = findArrow(previous, next)?.group.querySelectorAll('circle')[index];
  if (!circle) return null;
  const box = circle.getBoundingClientRect();
  return [box.left + box.width / 2, box.top + box.height / 2];"""
)


def get_arrow_point(
    page: pw.Page, previous: str, following: str, part: float = 0.5
) -> browser.Point:
    point: t.Optional[t.List[float]] = page.evaluate(
        ARROW_POINT_JS, [previous, following, part]
    )
    if point is None:
        raise RuntimeError(
            f"no free point on the arrow from {previous!r} to {following!r}"
        )
    return point[0], point[1]


def get_arrow_end_point(
    page: pw.Page, previous: str, following: str, end: str
) -> browser.Point:
    point: t.Optional[t.List[float]] = page.evaluate(
        ARROW_END_JS, [previous, following, 0 if end == "tail" else 1]
    )
    if point is None:
        raise RuntimeError(f"no {end} of an arrow from {previous!r} to {following!r}")
    return point[0], point[1]


# The rectangle of the text over the arrow between two tasks, and of each of its parts: left, top, right, bottom.
TEXT_BOXES_JS: str = make_js(
    """
  const [previous, next] = argument;
  const found = textsOverArrows().find(({ arrow }) => arrow && arrow.previous === previous && arrow.next === next);
  if (!found) return null;
  const rect = (element) => { const box = element.getBoundingClientRect(); return [box.left, box.top, box.right, box.bottom]; };
  return [rect(found.text), [...found.text.children].map(rect)];"""
)
# What the small text of the chart at a point says, all its parts; null where none is.
TEXT_AT_JS: str = """
([x, y]) => {
  const text = document.elementFromPoint(x, y)?.closest('[class~="text-11"][class~="leading-4"]');
  return text ? [...text.children].map((part) => part.textContent).join(' ') : null;
}
"""


def get_text_boxes(
    page: pw.Page, previous: str, following: str
) -> t.Tuple[t.List[float], t.List[t.List[float]]]:
    """The rectangle of the text over the arrow between two tasks and those of its parts: left, top, right,
    bottom."""
    boxes: t.Optional[t.List[t.Any]] = page.evaluate(
        TEXT_BOXES_JS, [previous, following]
    )
    if boxes is None:
        raise RuntimeError(f"no text over the arrow from {previous!r} to {following!r}")
    return boxes[0], boxes[1]


def get_part_point(
    page: pw.Page, previous: str, following: str, index: int
) -> browser.Point:
    """The middle of a part of the text over the arrow between two tasks: 0 for what the arrow is, 1 for its days."""
    part: t.List[float] = get_text_boxes(page, previous, following)[1][index]
    return (part[0] + part[2]) / 2, (part[1] + part[3]) / 2


def read_text_at(page: pw.Page, point: browser.Point) -> t.Optional[str]:
    return page.evaluate(TEXT_AT_JS, list(point))


# The dates beside the bars, by the line they stand on and from left to right; and the dimension line of the bar
# that shows one, with the days on it and its width.
DATES_BESIDE_JS: str = make_js(
    """
  const texts = [...textLayers()[1].children].filter((text) => text.matches('[class~="text-11"]'));
  const found = {};
  for (const text of texts.sort((a, b) => a.getBoundingClientRect().left - b.getBoundingClientRect().left)) {
    const box = text.getBoundingClientRect();
    const line = lineAt(box.top + box.height / 2);
    if (line) (found[nameOf(line)] ??= []).push([...text.children].map((part) => part.textContent).join(' '));
  }
  return found;"""
)
DIMENSION_JS: str = make_js(
    """
  const overlay = chart.querySelector('div[class~="z-[3]"][class~="pointer-events-none"]');
  const line = overlay.querySelector(':scope > svg[class~="h-px"]');
  const number = overlay.querySelector(':scope > div[class~="text-11"]');
  if (!line || !number) return null;
  const box = line.getBoundingClientRect();
  // the bar it spans, the nearest below it of those that span as much
  const bars = lines().filter((other) => {
    const bar = barOf(other)?.getBoundingClientRect();
    return bar && Math.abs(bar.left - box.left) <= 1 && Math.abs(bar.width - box.width) <= 1 && bar.top >= box.top - 1;
  });
  return [bars.length ? nameOf(bars[0]) : null, number.textContent, Math.round(box.width)];"""
)


def read_dates_beside(page: pw.Page) -> t.Dict[str, t.List[str]]:
    """The dates that stand beside the bars, by task, from left to right."""
    return page.evaluate(DATES_BESIDE_JS)


def read_dimension(page: pw.Page) -> t.Optional[t.List[t.Any]]:
    """The dimension line over a bar: its task, the days it says and its width in pixels; None while none shows."""
    return page.evaluate(DIMENSION_JS)


def find_empty_point(page: pw.Page) -> browser.Point:
    """A point of the chart where no bar, arrow or text is: low on the chart, below the last line."""
    box: t.Optional[pw.FloatRect] = page.locator(
        ".vertical-scrollbar.isolate"
    ).bounding_box()
    assert box is not None
    return box["x"] + box["width"] - 60, box["y"] + box["height"] - 30


CONTROL: str = '[role="dialog"]:has(button[aria-label="Remove the arrow"])'
CONTROL_JS: str = """
(popup) => [
  [...popup.children].filter((item) => item.dataset.chosen === 'true').map((item) => item.innerText.split(/\\s+/).join(' ')),
  popup.querySelector('input').value,
]
"""


def open_arrow_control(
    page: pw.Page, previous: str, following: str, part: float = 0.5
) -> pw.Locator:
    """A click on the arrow between two tasks; its control, open."""
    page.mouse.click(*get_arrow_point(page, previous, following, part))
    control: pw.Locator = page.locator(CONTROL)
    control.wait_for()
    return control


def read_control(page: pw.Page) -> t.Optional[t.List[t.Any]]:
    """The open control of an arrow: the choice marked as the one that holds, and the number of days in its field;
    None while no control is open."""
    control: pw.Locator = page.locator(CONTROL)
    return control.evaluate(CONTROL_JS) if control.count() else None


def click_away(page: pw.Page) -> None:
    """A click on the header of the chart, over the days, where a click changes nothing."""
    box: t.Optional[pw.FloatRect] = page.locator(
        ".vertical-scrollbar.isolate div.top-7"
    ).last.bounding_box()
    assert box is not None
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)


CARD: str = '[role="dialog"]:has(p)'


def hover_arrow(
    page: pw.Page, previous: str, following: str, part: float = 0.5
) -> None:
    """Brings the pointer onto the arrow between two tasks, as a hand comes to it from beside it."""
    point: browser.Point = get_arrow_point(page, previous, following, part)
    page.mouse.move(point[0] - 4, point[1] - 4)
    page.mouse.move(*point, steps=2)
    browser.let_page_draw(page)


CARD_JS: str = """
() => {
  const card = [...document.querySelectorAll('[role="dialog"]')].find((dialog) => dialog.querySelector('p'));
  return card ? [card.querySelector('p').innerText, [...card.querySelectorAll('button')].map((button) => button.innerText)] : null;
}
"""


def read_card(page: pw.Page) -> t.Optional[t.List[t.Any]]:
    """The card that explains a conflict or a link that is apart: its sentence and its ways out; None while none
    is shown."""
    return page.evaluate(CARD_JS)


RINGED_JS: str = make_js(
    """return lines().filter((line) => barOf(line)?.querySelector(`a[class~="${argument}"]`)).map(nameOf);"""
)


TAILS_JS: str = make_js(
    """
  const scale = readScale();
  return lines().flatMap((line) => {
    const tail = barOf(line)?.querySelector('div[class~="rounded-r-full"]');
    return tail ? [[nameOf(line), Math.round(tail.getBoundingClientRect().width / scale.pxPerDay)]] : [];
  });"""
)


def read_tails(page: pw.Page) -> t.Dict[str, int]:
    """The tasks drawn with a tail after their bar, and how many days long it is: the days their end can go later
    before anything else changes."""
    return dict(page.evaluate(TAILS_JS))


def read_ringed(page: pw.Page, colour: str) -> t.List[str]:
    """The tasks whose bars have a ring: "accent" for the critical ones, "danger" for those that produce the
    conflict under the pointer."""
    return page.evaluate(RINGED_JS, f"ring-{colour}-strong")


def drag(page: pw.Page, start: browser.Point, end: browser.Point) -> None:
    """Presses at a point and moves in a straight line to another, holding the button: the first move decides
    whether the drag is along the time or across the lines."""
    page.mouse.move(*start)
    page.mouse.down()
    page.mouse.move(*end, steps=12)
    browser.let_page_draw(page)


def drag_bar(page: pw.Page, name: str, days: int, part: str = "middle") -> None:
    """Takes a bar, or one of its edges, and holds it a number of days later (earlier when negative)."""
    start: browser.Point = get_bar_point(page, name, part)
    drag(page, start, (start[0] + days * get_px_per_day(page), start[1]))


def let_go(page: pw.Page) -> None:
    page.mouse.up()
    browser.let_page_draw(page)


def carry_entry(page: pw.Page, name: str) -> None:
    """Presses the name of a task in the list and moves sideways, which begins to carry the task onto the chart."""
    start: browser.Point = get_entry_point(page, name)
    page.mouse.move(*start)
    page.mouse.down()
    page.mouse.move(start[0] + 40, start[1], steps=3)


def move_slowly(page: pw.Page, start: browser.Point, end: browser.Point) -> None:
    """Moves the pointer a pixel or two a frame, as a hand that aims at something does."""
    distance: float = max(abs(end[0] - start[0]), abs(end[1] - start[1]))
    count: int = max(int(distance / 2), 1)
    index: int
    for index in range(1, count + 1):
        page.mouse.move(
            start[0] + (end[0] - start[0]) * index / count,
            start[1] + (end[1] - start[1]) * index / count,
        )
        browser.let_page_draw(page)


def turn_wheel(page: pw.Page, point: browser.Point, notches: int) -> None:
    """The wheel at a point, a notch at a time: up, away from the person, for a positive number."""
    page.mouse.move(*point)
    _: int
    for _ in range(abs(notches)):
        page.mouse.wheel(0, -100 if notches > 0 else 100)
        browser.let_page_draw(page)


MARKED_HANDLES_JS: str = make_js(
    """
  return lines().flatMap((line) => [...line.querySelectorAll('button[aria-label^="Draw an arrow from the "]')]
    .filter((handle) => handle.classList.contains('scale-150'))
    .map((handle) => [nameOf(line), handle.getAttribute('aria-label').split(' ').pop(),
      handle.classList.contains('bg-danger-primary') ? 'refuses' : 'takes']));"""
)


def read_marked_handles(page: pw.Page) -> t.List[t.List[str]]:
    """The handles drawn larger, as the one that takes what is carried or drawn to it, or refuses it in red: task,
    edge, and whether it takes or refuses."""
    return page.evaluate(MARKED_HANDLES_JS)


def read_refusals(page: pw.Page) -> t.List[str]:
    """The texts beside the pointer that say why a handle does not take an arrow."""
    return page.evaluate(
        make_js(
            """return [...chart.querySelectorAll('div[class~="text-danger-primary"][class~="border-danger-strong"]')]
          .map((text) => text.innerText);"""
        )
    )


def read_selected(page: pw.Page) -> t.List[str]:
    """The lines drawn as selected."""
    return page.evaluate(
        make_js(
            """return lines().filter((line) => line.firstElementChild.className.split(' ')
             .includes('bg-layer-transparent-selected')).map(nameOf);"""
        )
    )
