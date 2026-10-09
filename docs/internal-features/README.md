# What this checkout adds to Plane

This is Plane community edition with five features built in, a script that runs and backs up the
whole installation, and API endpoints that let the unmodified upstream MCP server reach the new
features. It is meant for one person and a few agents on one machine.

| Feature | Plane documentation it follows |
| --- | --- |
| Timeline dependencies | <https://docs.plane.so/core-concepts/issues/timeline-dependency> |
| Milestones | <https://docs.plane.so/projects/milestones> |
| Work item types and custom properties | <https://docs.plane.so/work-items/project-work-item-types>, <https://docs.plane.so/work-items/work-item-properties#custom-properties> |
| Wiki, collections | <https://docs.plane.so/pages/wiki>, <https://docs.plane.so/pages/collections> |
| Nested pages | <https://docs.plane.so/pages/nested-pages> |

Running, backup, restore and the MCP setup are in [runtime.md](runtime.md).

## Where it differs from the Plane documentation

Left out on purpose, because they only make sense with several human users or with features this
edition does not have:

- sharing a page with specific members, member lists of private collections, view/comment/edit
  access levels (public and private pages and collections work as documented);
- workspace-level work item types and properties: types and properties belong to one project;
- the release picker property;
- publishing pages and exporting a page together with its nested pages.

Simpler than documented:

- The project "Overview" is the list of milestones; a milestone's page shows its work items on the
  timeline without the filter row.
- A milestone description is formatted text without images.
- A dependency is drawn from the connector at the end of a bar; the dialog that follows asks which
  kind it is. Moving a work item pushes the work items that depend on it later, never earlier.
- Custom properties can be shown as table columns and card badges, and work items can be filtered
  by them; they cannot yet be ordered or grouped by them in the UI.
- Pages cannot be moved between a project and the wiki.

Added beyond the documentation:

- The badge next to a page title says "Unsaved changes" until the page's latest edit is in the
  database, then "Saved". The installation may be stopped by killing its processes, and the live
  server keeps the newest edits in memory for a moment; the badge shows that moment.

## MCP

Every feature above has endpoints under `/api/v1/` in the shapes of Plane's Python SDK, so the
upstream `plane-mcp-server` tools `milestone`, `workitem_relation`, `workitem_type`,
`workitem_property`, `page`, `collection` and the project feature switches work unchanged. Tools
for things this edition lacks (customers, initiatives, releases, workspace-level types, collection
members, links between work items and pages) answer "not found".
