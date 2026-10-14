// Starter flows: small, ready-wired flows that run here with one tap. Built from the installed engine's own
// component templates through the normal edits, so they pass the same checks as anything built by hand.
// Each one is proven on the real engine in tests/starters-live.test.mts. Pure: safe to import in the browser.

import type { FlowEdit } from './model';

export type Starter = { key: string; title: string; description: string; sampleInput: string; edits: () => FlowEdit[] };

const add = (componentType: string, nodeId: string, x: number, y = 0): FlowEdit => ({ kind: 'addNode', nodeId, componentType, position: { x, y } });
const set = (nodeId: string, field: string, value: string | number | boolean): FlowEdit => ({ kind: 'setField', nodeId, field, value });
const wire = (from: string, out: string, to: string, input: string): FlowEdit => ({ kind: 'connect', nodeId: from, sourceOutput: out, target: to, targetInput: input });

export const STARTERS: Starter[] = [
  {
    key: 'reply-template',
    title: 'Reply template',
    description: 'Type a name; get a ready reply. Edit the wording in Prompt Template.',
    sampleInput: 'Jordan',
    edits: () => [
      add('ChatInput', 'ChatInput-st1in', 0), add('Prompt Template', 'Prompt Template-st1pt', 380), add('ChatOutput', 'ChatOutput-st1ou', 760),
      set('Prompt Template-st1pt', 'template', "Hi {name}, thanks for reaching out! I'll send the details today."),
      wire('ChatInput-st1in', 'message', 'Prompt Template-st1pt', 'name'),
      wire('Prompt Template-st1pt', 'prompt', 'ChatOutput-st1ou', 'input_value'),
    ],
  },
  {
    key: 'router',
    title: 'Message router',
    description: 'Messages that mention "price" get the pricing reply; everything else gets the general one.',
    sampleInput: 'what is the price?',
    edits: () => [
      add('ChatInput', 'ChatInput-st2in', 0), add('ConditionalRouter', 'ConditionalRouter-st2cr', 380),
      add('ChatOutput', 'ChatOutput-st2o1', 760, -160), add('ChatOutput', 'ChatOutput-st2o2', 760, 160),
      set('ConditionalRouter-st2cr', 'match_text', 'price'), set('ConditionalRouter-st2cr', 'operator', 'contains'),
      set('ConditionalRouter-st2cr', 'case_sensitive', false),
      set('ConditionalRouter-st2cr', 'true_case_message', 'Pricing: our plans start at $99/month.'),
      set('ConditionalRouter-st2cr', 'false_case_message', 'Thanks! A teammate will reply shortly.'),
      wire('ChatInput-st2in', 'message', 'ConditionalRouter-st2cr', 'input_text'),
      wire('ConditionalRouter-st2cr', 'true_result', 'ChatOutput-st2o1', 'input_value'),
      wire('ConditionalRouter-st2cr', 'false_result', 'ChatOutput-st2o2', 'input_value'),
    ],
  },
  {
    key: 'chunker',
    title: 'Text chunker',
    description: 'Paste text with one item per line; get each line back as a bullet. Raise the chunk size in Split Text to group lines.',
    sampleInput: 'First point about the offer.\nSecond point about timing.\nThird point about next steps.',
    edits: () => [
      add('ChatInput', 'ChatInput-st3in', 0), add('SplitText', 'SplitText-st3sp', 380), add('ParserComponent', 'ParserComponent-st3pa', 760), add('ChatOutput', 'ChatOutput-st3ou', 1140),
      set('SplitText-st3sp', 'chunk_size', 1), set('SplitText-st3sp', 'chunk_overlap', 0), set('SplitText-st3sp', 'separator', '\n'),
      set('ParserComponent-st3pa', 'pattern', '- {text}'),
      wire('ChatInput-st3in', 'message', 'SplitText-st3sp', 'data_inputs'),
      wire('SplitText-st3sp', 'dataframe', 'ParserComponent-st3pa', 'input_data'),
      wire('ParserComponent-st3pa', 'parsed_text', 'ChatOutput-st3ou', 'input_value'),
    ],
  },
  {
    key: 'dated-note',
    title: 'Dated note',
    description: "Type a note; get it stamped with today's date and time.",
    sampleInput: 'Called 3 leads, 1 booked.',
    edits: () => [
      add('ChatInput', 'ChatInput-st4in', 0, 120), add('CurrentDate', 'CurrentDate-st4cd', 0, -120), add('Prompt Template', 'Prompt Template-st4pt', 380), add('ChatOutput', 'ChatOutput-st4ou', 760),
      set('Prompt Template-st4pt', 'template', 'Note ({date}): {note}'),
      wire('CurrentDate-st4cd', 'current_date', 'Prompt Template-st4pt', 'date'),
      wire('ChatInput-st4in', 'message', 'Prompt Template-st4pt', 'note'),
      wire('Prompt Template-st4pt', 'prompt', 'ChatOutput-st4ou', 'input_value'),
    ],
  },
];
