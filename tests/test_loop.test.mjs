import test from 'node:test';
import assert from 'node:assert/strict';
import {
  parseSnapshotElements,
  generateActions,
  performAction,
  runNavigationLoop,
} from '../core/navigation/loop.mjs';

test('parseSnapshotElements extracts interactive elements and attributes', () => {
  const snapshot = `
uid=1 textbox "Search" value="backend"
uid=2 button "Find"
uid=3 checkbox "1-3 years"
uid=4 link "About" disabled
`;
  const elements = parseSnapshotElements(snapshot);
  assert.equal(elements.length, 4);
  assert.equal(elements[0].uid, '1');
  assert.equal(elements[0].role, 'textbox');
  assert.equal(elements[0].label, 'Search');
  assert.equal(elements[0].current_value, 'backend');

  assert.equal(elements[1].role, 'button');
  assert.equal(elements[2].role, 'checkbox');
});

test('generateActions creates click and fill actions according to task fields', () => {
  const snapshot = `
uid=1 textbox "Search"
uid=2 button "Submit"
uid=3 link "Pricing"
`;
  const task = {
    goal: 'Search for jobs',
    fields: { Search: 'Python backend' },
  };

  const actions = generateActions(snapshot, task);
  assert.ok(actions['FILL:1']);
  assert.equal(actions['FILL:1'].value, 'Python backend');
  assert.ok(actions['CLICK:2']);
  assert.ok(actions['CLICK:3']);
});

test('runNavigationLoop executes actions and terminates on DONE', async () => {
  const snapshot1 = 'uid=10 textbox "Search"\nuid=20 button "Submit"';
  const snapshot2 = 'uid=30 heading "Results"\nuid=40 button "Apply"';

  let currentSnap = snapshot1;
  const actionsPerformed = [];

  const mockPage = {
    snapshot: async () => currentSnap,
    fill: async (uid, val) => {
      actionsPerformed.push({ action: 'fill', uid, val });
      currentSnap = snapshot2;
    },
    click: async (uid) => {
      actionsPerformed.push({ action: 'click', uid });
    },
  };

  let stepCount = 0;
  const mockHandler = async (payload) => {
    stepCount++;
    if (stepCount === 1) {
      return {
        answers: {
          operation: { choice: 'TYPE_TEXT' },
          type_text_target: { choice: 'FILL:10' },
        },
      };
    }
    return {
      answers: {
        operation: { choice: 'DONE' },
      },
    };
  };

  const result = await runNavigationLoop(
    mockPage,
    {
      goal: 'Fill search box and complete',
      fields: { Search: 'fastapi' },
    },
    { mockHandler }
  );

  assert.equal(result.status, 'done');
  assert.equal(actionsPerformed.length, 1);
  assert.equal(actionsPerformed[0].val, 'fastapi');
  assert.equal(result.decisions.length, 2);
});

test('runNavigationLoop hands off immediately when blocked or CAPTCHA encountered', async () => {
  const blockedSnapshot = 'uid=1 RootWebArea\nAccess Denied: verify you are human';
  const mockPage = {
    snapshot: async () => blockedSnapshot,
  };

  const result = await runNavigationLoop(
    mockPage,
    { goal: 'Open site' },
    { mockHandler: async () => ({ answers: { operation: { choice: 'WAIT' } } }) }
  );

  assert.equal(result.status, 'handoff');
});
