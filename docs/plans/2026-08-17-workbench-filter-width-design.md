# Workbench Filter Width Design

## Goal

Make every desktop filter control in the workbench toolbar match the title search input width.

## Scope

`DashboardView.vue` applies `workbench-search` to the title input and `workbench-filter` to each of the seven select controls. The desktop stylesheet currently gives those classes different fixed widths. Update the shared filter class so every control is 260px wide, which is the current title input width.

## Alternatives

1. Set widths on each select in the template. This creates repeated presentation rules and can drift when filters change.
2. Update the shared `.workbench-filter` desktop rule. This keeps the size contract in the stylesheet and is the selected approach.
3. Replace fixed widths with an auto-fit grid. This would change toolbar wrapping behavior beyond the requested visual correction.

## Responsive Behavior

The existing narrow-screen media query already sets `.workbench-filter` and `.workbench-search` to flexible, unbounded widths. It remains unchanged, preserving mobile wrapping and full-width behavior.

## Verification

Add a source-level regression assertion that the desktop search and filter classes use the same 260px width. Run the focused frontend test suite and production build, then inspect the workbench at a desktop viewport.
