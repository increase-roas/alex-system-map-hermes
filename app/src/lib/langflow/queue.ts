// The panel's list of unsaved edits. Pure, so it can be tested without a browser.
import type { FlowEdit } from './model';

/** Edits that replace an earlier edit of the same thing. Structural edits are never merged. */
export function editKey(e: FlowEdit): string | null {
  if (e.kind === 'setField') return `${e.nodeId}|${e.field}`;
  if (e.kind === 'move' || e.kind === 'rename') return `${e.kind}|${e.nodeId}`;
  return null;
}

/**
 * Adds an edit. A newer value for the same setting, position or name replaces the old edit where it stands,
 * so edits that depend on it (a connection to a new prompt variable) still run after it.
 */
export function queueEditInto(list: FlowEdit[], edit: FlowEdit): FlowEdit[] {
  const key = editKey(edit);
  const at = key ? list.findIndex((e) => editKey(e) === key) : -1;
  if (at < 0) return [...list, edit];
  return list.map((e, i) => (i === at ? edit : e));
}
