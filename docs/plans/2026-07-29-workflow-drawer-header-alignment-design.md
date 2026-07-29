# Workflow Drawer Header Alignment Design

## Goal

Place the selected transition context at the upper-left of the advanced
configuration drawer, immediately after the back control. Keep the drawer
close control at the upper-right.

## Layout

The header uses two groups:

- The leading group contains the optional back button and the transition title
  with its source-to-target status summary.
- The close control remains in Element Plus' existing header action position.

The left navigation and the right-side configuration content remain unchanged.

## Behavior and Accessibility

The existing back action, close action, labels, and unsaved-change guards are
unchanged. The leading group may shrink without overlapping the close control.

## Verification

Add a source-level component test that requires the leading group and its
left-aligned layout rule. Run the focused frontend test and the complete
frontend test suite after the change.
