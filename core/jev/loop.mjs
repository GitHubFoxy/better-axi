/**
 * Action & Decision Loop for Jev and AXI over CDP.
 * Token-efficient accessibility snapshotting, decision making, and execution.
 */

import { requestDecision, validateChoice } from './decision_client.mjs';

export function parseSnapshotElements(snapshot) {
  if (!snapshot || typeof snapshot !== 'string') return [];
  return snapshot.split('\n').flatMap((line) => {
    const m = line.match(/uid=(\S+)\s+(\w+)(?:\s+("(?:[^"\\]|\\.)*"))?(.*)/);
    if (!m) return [];
    let label = '';
    try {
      label = m[3] ? JSON.parse(m[3]) : '';
    } catch {
      return [];
    }
    return [
      {
        uid: m[1],
        role: m[2],
        label,
        state: m[4] || '',
        current_value: (/password|secret|cvv|token|card/i.test(m[2] + ' ' + label + ' ' + (m[4] || ''))) ? '***REDACTED***' : (m[4]?.match(/value="([^"]*)"/)?.[1] ?? ''),
      },
    ];
  });
}

export function generateActions(snapshot, task) {
  const observed = {};
  const elements = parseSnapshotElements(snapshot);

  for (const el of elements) {
    if (/\b(disabled|readonly)\b/.test(el.state)) continue;

    const fieldKey = Object.hasOwn(task.fields ?? {}, el.uid) ? el.uid : el.label;
    if (
      ['textbox', 'searchbox', 'combobox', 'spinbutton'].includes(el.role) &&
      Object.hasOwn(task.fields ?? {}, fieldKey)
    ) {
      observed[`FILL:${el.uid}`] = {
        ...el,
        kind: 'fill',
        value: task.fields[fieldKey],
      };
    }

    if (
      [
        'link',
        'button',
        'checkbox',
        'radio',
        'option',
        'combobox',
        'switch',
        'tab',
        'menuitem',
        'menuitemcheckbox',
        'menuitemradio',
        'treeitem',
        'gridcell',
        'slider',
      ].includes(el.role)
    ) {
      observed[`CLICK:${el.uid}`] = { ...el, kind: 'click' };
    }
  }

  return observed;
}

export async function performAction(page, action, snapshot = '') {
  if (action.kind === 'fill') return page.fill(action.uid, action.value);
  if (action.kind === 'click') return page.click(action.uid);
  if (action.kind === 'wait') return page.wait ? page.wait(150) : new Promise((r) => setTimeout(r, 150));
  if (action.kind === 'press') return page.press(action.key);
  if (action.kind === 'back') return page.back();
  if (action.kind === 'scroll') {
    const delta = Number.isInteger(action.delta) ? action.delta : 0;
    return page.eval('() => window.scrollBy(0, ' + delta + ')');
  }
  if (action.kind === 'extra') {
    if (typeof action.handler === 'function') {
      return action.handler(page, action.params);
    }
    throw new Error('Dynamic script execution is disabled for security');
  }
  throw new Error("Unknown action kind: " + action?.kind);
}

export async function runNavigationLoop(page, task, options = {}) {
  const { mockHandler = null, timeoutS = 60, maxSteps = 20 } = options;
  const start = performance.now();
  const deadline = start + (task.timeout_s ?? timeoutS) * 1000;
  const history = [];
  const decisions = [];
  let status = 'step_budget';
  let snapshot = '';

  if (task.start_url && page.open) {
    await page.open(task.start_url);
  }

  for (let step = 0; step < (task.max_steps ?? maxSteps); step++) {
    if (performance.now() >= deadline) {
      status = 'time_budget';
      break;
    }

    snapshot = await page.snapshot();
    if (/access denied|доступ запрещен|verify you are human|cloudflare|datadome|smartcaptcha|security check|just a moment/i.test(snapshot)) {
      status = 'handoff';
      break;
    }

    const observed = generateActions(snapshot, task);
    const groups = { CLICK: {}, TYPE_TEXT: {}, EXTRA: {} };

    for (const [id, a] of Object.entries(observed)) {
      const groupKey = a.kind === 'fill' ? 'TYPE_TEXT' : 'CLICK';
      groups[groupKey][id] = {
        element: a.label,
        role: a.role,
        current_value: a.current_value,
        ...(a.kind === 'fill' ? { desired_text: a.value } : {}),
      };
    }

    const controls = {
      WAIT: { kind: 'wait', label: 'Wait briefly for loading' },
      SCROLL_DOWN: { kind: 'scroll', delta: 600, label: 'Scroll down to view more controls' },
      SCROLL_UP: { kind: 'scroll', delta: -600, label: 'Scroll up' },
      ENTER: { kind: 'press', key: 'Enter', label: 'Press Enter to submit field' },
      ESCAPE: { kind: 'press', key: 'Escape', label: 'Close modal or menu' },
      TAB: { kind: 'press', key: 'Tab', label: 'Move focus to next input' },
      BACK: { kind: 'back', label: 'Go back to previous page' },
    };

    for (const [i, a] of (task.extra_actions ?? []).entries()) {
      const id = `EXTRA:${i}`;
      observed[id] = { ...a, kind: 'extra' };
      groups.EXTRA[id] = a.label;
    }

    const criteria = Object.fromEntries(Object.entries(controls).map(([k, v]) => [k, v.label]));
    criteria.DONE = 'Goal has been visibly achieved';
    criteria.HANDOFF = 'Manual intervention or Pi guidance required';

    if (Object.keys(groups.CLICK).length) criteria.CLICK = 'Click an observed button/link';
    if (Object.keys(groups.TYPE_TEXT).length) criteria.TYPE_TEXT = 'Fill input field';
    if (Object.keys(groups.EXTRA).length) criteria.EXTRA = 'Execute custom AXI operation';

    const questions = {
      operation: {
        type: 'choice',
        criteria,
        instructions: {
          goal: task.goal,
          rules: 'Pick the single most logical next operation to make progress.',
        },
      },
    };

    for (const [op, targets] of Object.entries(groups)) {
      if (Object.keys(targets).length) {
        questions[`${op.toLowerCase()}_target`] = {
          type: 'choice',
          criteria: targets,
          instructions: { goal: task.goal, operation: op },
        };
      }
    }

    const decisionResponse = await requestDecision(
      {
        state: {
          page: {
          text: snapshot
            .slice(0, 12000)
            .replace(/value="([^"]*)"/g, (match) =>
              /password|secret|cvv|token|card/i.test(match) ? 'value="***REDACTED***"' : match
            ),
        },
          elements: groups,
          recent_actions: history.slice(-6).map((h) => h.choice),
        },
        questions,
      },
      {
        mockHandler,
        timeoutMs: Math.max(1000, Math.floor(deadline - performance.now())),
        validateResult: (res) => {
          const op = validateChoice(res.answers?.operation, criteria);
          if (Object.hasOwn(groups, op)) {
            validateChoice(res.answers?.[`${op.toLowerCase()}_target`], groups[op]);
          }
        },
      }
    );

    const res = decisionResponse.result;
    const operation = validateChoice(res.answers?.operation, criteria);
    const choice = Object.hasOwn(groups, operation)
      ? validateChoice(res.answers?.[`${operation.toLowerCase()}_target`], groups[operation])
      : operation;

    decisions.push({ choice, operation, provider: decisionResponse.provider });

    if (choice === 'DONE' || choice === 'HANDOFF') {
      status = choice === 'DONE' ? 'done' : 'handoff';
      break;
    }

    const act = observed[choice] ?? controls[choice];
    try {
      await performAction(page, act, snapshot);
      history.push({ choice, action: act.label, kind: act.kind });
    } catch (err) {
      let recovered = false;
      try {
        const freshSnapshot = await page.snapshot();
        const freshObserved = generateActions(freshSnapshot, task);
        const matched = Object.values(freshObserved).find(
          (e) => e.role === act.role && e.label === act.label && e.kind === act.kind
        );
        if (matched) {
          await performAction(page, matched, freshSnapshot);
          history.push({ choice: "RETRY:" + choice, action: matched.label, kind: matched.kind });
          recovered = true;
        }
      } catch {
        recovered = false;
      }
      if (!recovered) {
        history.push({ choice, error: err.message });
        status = 'handoff';
        break;
      }
    }

    // Detect loops
    if (history.length >= 3 && history.slice(-3).every((h) => h.choice === choice) && !['scroll', 'wait'].includes(act.kind)) {
      status = 'handoff';
      break;
    }
  }

  return {
    status,
    total_ms: Math.round(performance.now() - start),
    steps: history.length,
    history,
    decisions,
    snapshot,
  };
}
