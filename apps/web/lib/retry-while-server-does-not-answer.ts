/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { SWRConfiguration } from "swr";
import { SWRConfig } from "swr";

// An axios error and an axios response both carry the status; none means that no answer came at all. A status of 500 or
// more says that the API, or the proxy in front of it, failed, and nothing about what was asked.
export const hasServerAnswered = (error: unknown): boolean => {
  const status: number | undefined = (error as { status?: number } | undefined)?.status;
  return status !== undefined && status < 500;
};

// A page can be open, or be opened, while the API of its instance does not answer: the instance is stopped, or its API
// did not start up (while it starts, its address keeps the requests until it answers them; see
// apps/api/preload_and_wait.py). A page whose first requests failed says that Plane didn't start up correctly until
// those requests, made again, are answered. SWR makes a failed request again after ever longer waits, so the page came
// back long after the server did. A request that the server did not answer is made again at a short fixed interval
// instead; one that it did answer, such as a 403, keeps SWR's own retry.
export const retryWhileServerDoesNotAnswer: NonNullable<SWRConfiguration["onErrorRetry"]> = (
  error,
  key,
  config,
  revalidate,
  options
) => {
  // FOR_REVIEWER: while the server does not answer, every open page makes each of these requests (the instance, the
  // signed-in person, the person's membership of the workspace) once a second, a few small requests a second, which a
  // local instance does not feel; a page left open on an instance whose API crashes on these requests keeps asking. A
  // longer interval brings the page back later after a restart.
  const RETRY_INTERVAL_MS = 1000;
  if (hasServerAnswered(error)) {
    SWRConfig.defaultValue.onErrorRetry(error, key, config, revalidate, options);
    return;
  }
  setTimeout(() => void revalidate(options), RETRY_INTERVAL_MS);
};
