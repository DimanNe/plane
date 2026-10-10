/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// The requests of this page that change something on the server and have no answer yet
let writesInFlight = 0;
let writesStarted = 0;
const waiting: (() => void)[] = [];

export const trackOwnWrite = <T>(write: Promise<T>): Promise<T> => {
  writesInFlight += 1;
  writesStarted += 1;
  const finish = () => {
    writesInFlight -= 1;
    if (writesInFlight === 0) waiting.splice(0).forEach((resume) => resume());
  };
  write.then(finish, finish);
  return write;
};

const whenNoWriteInFlight = (): Promise<void> =>
  writesInFlight === 0
    ? Promise.resolve()
    : new Promise<void>((resume) => waiting.push(resume)).then(whenNoWriteInFlight);

/**
 * Fetches what this page may be changing itself at the same moment. An answer that crossed a write of the page
 * can hold the state before that write, and applying it would put back what the user just changed. So the fetch
 * waits until no write is in flight, and is made again when a write started before its answer came.
 */
export const fetchAroundOwnWrites = async <T>(fetch: () => Promise<T>): Promise<T> => {
  await whenNoWriteInFlight();
  const writesStartedBefore = writesStarted;
  const answer = await fetch();
  return writesStarted === writesStartedBefore ? answer : fetchAroundOwnWrites(fetch);
};
