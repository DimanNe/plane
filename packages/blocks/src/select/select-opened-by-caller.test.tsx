/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Select } from "./select";

type Option = { id: string; name: string };

const options: Option[] = [
  { id: "a", name: "Alpha" },
  { id: "b", name: "Beta" },
  { id: "c", name: "Gamma" },
];

let openDropdown: () => void;

/**
 * A caller that opens the dropdown itself, as a key does and not a press on the trigger. What goes with that it
 * passes only while the dropdown is open.
 */
function OpenedByCaller(props: { finalFocus?: boolean }) {
  const [isOpen, setIsOpen] = useState(false);
  openDropdown = () => setIsOpen(true);

  return (
    <>
      <button type="button">Elsewhere</button>
      <Select<Option>
        {...(isOpen ? { open: true, ...props } : {})}
        onOpenChange={setIsOpen}
        getValues={() => options}
        value={null}
        onChange={vi.fn()}
        getOptionValue={(option) => option.id}
        getOptionLabel={(option) => option.name}
        placeholder="Pick"
        searchPlaceholder="Search options"
      >
        <Select.Trigger variant="select-md">
          <Select.Value />
        </Select.Trigger>
      </Select>
    </>
  );
}

const querySearch = () => within(document.body).queryByRole("combobox", { name: /search options/i });

const open = async () => {
  act(() => openDropdown());
  await waitFor(() => expect(document.activeElement).toBe(querySearch()));
};

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"], shouldAdvanceTime: true });
});

afterEach(async () => {
  // as in select.test.tsx: callbacks of the virtualizer can outlive the unmount
  cleanup();
  try {
    await act(() => vi.runOnlyPendingTimersAsync());
  } finally {
    vi.useRealTimers();
  }
});

describe("the focus after a dropdown that its caller opened has closed", () => {
  const cases: { name: string; hadFocus: boolean; finalFocus: boolean | undefined; expected: string }[] = [
    { name: "something had the focus: it has it again", hadFocus: true, finalFocus: undefined, expected: "Elsewhere" },
    {
      name: "nothing had the focus: base-ui gives it to the trigger",
      hadFocus: false,
      finalFocus: undefined,
      expected: "Pick",
    },
    {
      name: "nothing had the focus, and finalFocus was false while the dropdown was open: nothing has it",
      hadFocus: false,
      finalFocus: false,
      expected: "nothing",
    },
  ];

  it.each(cases)("$name", async ({ hadFocus, finalFocus, expected }) => {
    const user = userEvent.setup();
    render(<OpenedByCaller finalFocus={finalFocus} />);
    if (hadFocus) screen.getByRole("button", { name: "Elsewhere" }).focus();

    await open();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(querySearch()).toBeNull());
    // base-ui moves the focus a moment after the popup has gone
    await act(() => vi.advanceTimersByTimeAsync(100));

    const focused = document.activeElement;
    expect(focused === document.body ? "nothing" : (focused?.getAttribute("aria-label") ?? focused?.textContent)).toBe(
      expected
    );
  });
});
