# Project Work-Pool Overflow Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prevent the project work-pool banner from creating horizontal overflow in the project detail card.

**Architecture:** The banner retains its existing grid layout and `width: 100%`. Its box model changes to `border-box`, causing its padding and borders to be included in that width. A source-contract test records the constraint so later style changes cannot remove it unintentionally.

**Tech Stack:** Vue 3, scoped CSS, Node.js assertion tests.

---

### Task 1: Cover and Fix Work-Pool Banner Width

**Files:**
- Modify: `frontend/src/views/projectPlanningWorkPool.test.mjs`
- Modify: `frontend/src/components/ProjectWorkPoolBand.vue`

**Step 1: Write the failing test**

Assert that `.work-pool-band` contains `box-sizing: border-box` alongside its full-width layout.

**Step 2: Run test to verify it fails**

Run: `npm test -- projectPlanningWorkPool`

Expected: failure because the banner does not yet define the required box model.

**Step 3: Write minimal implementation**

Add `box-sizing: border-box` to `.work-pool-band`.

**Step 4: Run test and build to verify**

Run: `npm test -- projectPlanningWorkPool` and `npm run build`

Expected: both commands pass.

**Step 5: Verify visually**

At a desktop viewport matching the report, confirm the project-detail card's content no longer exceeds its client width.

**Step 6: Commit**

Deferred: the workspace instruction requires explicit delivery-method confirmation before any Git operation.
