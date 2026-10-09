/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export type TMilestone = {
  id: string;
  title: string;
  description_html: string;
  target_date: string | null;
  total_issues: number;
  completed_issues: number;
  cancelled_issues: number;
  project: string;
  workspace: string;
  created_at: string;
  updated_at: string;
  created_by: string;
  updated_by: string | null;
};
