/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { memo, useRef, useState } from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useOutsideClickDetector } from "@plane/hooks";

function Panel() {
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useOutsideClickDetector(ref, () => {
    if (isOpen) setIsOpen(false);
  });
  return (
    <div>
      <div ref={ref}>
        <button type="button" onClick={() => setIsOpen(true)}>
          open
        </button>
        {isOpen && <span>panel</span>}
      </div>
      <p>outside</p>
    </div>
  );
}

const MemoPanel = memo(Panel);

describe("outside click closes a panel that reads its own state in the callback", () => {
  it.each([
    ["plain function component", Panel],
    ["memo component, as every MobX observer is", MemoPanel],
  ])("%s", (_name, Component) => {
    render(<Component />);
    fireEvent.click(screen.getByText("open"));
    expect(screen.queryByText("panel")).not.toBeNull();
    fireEvent.mouseDown(screen.getByText("outside"));
    expect(screen.queryByText("panel")).toBeNull();
  });
});
