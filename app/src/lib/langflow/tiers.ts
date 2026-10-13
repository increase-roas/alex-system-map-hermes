// What each current Langflow core component may do in this dashboard.
//
// Alex's rule (chat, 2026-10-13): runs stay local. Components that call an AI model, reach the
// internet, run code or touch files, or need a Langflow server are show-and-edit only.
// Source of the tier list: reviews/2026-10-13-langflow-nodes-audit.md (63 current components in the
// engine's component_index.json). A component that is not listed here is "unknown" and never runs.
//
// A component only runs here after a live run on the real engine produced its real output.
// Evidence: reviews/receipts/2026-10-13-langflow-nodes/live-components.txt.
// Pure module: safe to import from the browser.

export type RunTier = 'local' | 'ai' | 'internet' | 'code_files' | 'server' | 'unknown';

export const TIER_LABEL: Record<RunTier, string> = {
  local: 'Local',
  ai: 'AI model: show only',
  internet: 'Internet: show only',
  code_files: 'Code or files: show only',
  server: 'Needs Langflow server: show only',
  unknown: 'Unknown: show only',
};

const TIER_REASON: Record<Exclude<RunTier, 'local'>, string> = {
  ai: 'calls an AI model',
  internet: 'reaches the internet',
  code_files: 'runs code or touches files',
  server: 'needs a running Langflow server',
  unknown: 'is not in the checked component list',
};

export const COMPONENT_TIERS: Record<string, RunTier> = {
  AMapComponent: 'ai',
  AgenerateComponent: 'ai',
  AreduceComponent: 'ai',
  CustomComponent: 'code_files',
  APIRequest: 'internet',
  MockDataGenerator: 'local',
  SQLComponent: 'code_files',
  URLComponent: 'internet',
  UnifiedWebSearch: 'internet',
  File: 'code_files',
  FileSystemTool: 'code_files',
  Knowledge: 'code_files',
  MemoryBase: 'code_files',
  SaveToFile: 'code_files',
  FileContentRetriever: 'code_files',
  FileDescriptionGeneratorComponent: 'code_files',
  MergeFlows: 'server',
  ConditionalRouter: 'local',
  HumanInput: 'server',
  Listen: 'local',
  LoopComponent: 'local',
  Notify: 'local',
  RunFlow: 'server',
  ChatInput: 'local',
  ChatOutput: 'local',
  Webhook: 'server',
  CSVAgent: 'ai',
  CharacterTextSplitter: 'local',
  HtmlLinkExtractor: 'local',
  'LangChain Hub Prompt': 'ai',
  LangChainFakeEmbeddings: 'local',
  LanguageRecursiveTextSplitter: 'local',
  NaturalLanguageTextSplitter: 'local',
  OpenAIToolsAgent: 'ai',
  OpenAPIAgent: 'ai',
  RecursiveCharacterTextSplitter: 'local',
  RunnableExecutor: 'code_files',
  SQLAgent: 'ai',
  SQLDatabase: 'code_files',
  SemanticTextSplitter: 'ai',
  ToolCallingAgent: 'ai',
  XMLAgent: 'ai',
  BatchRunComponent: 'ai',
  GuardrailValidatorV2: 'ai',
  LLMSelectorComponent: 'ai',
  'Smart Transform': 'ai',
  SmartRouter: 'ai',
  StructuredOutput: 'ai',
  A2AAgent: 'ai',
  Agent: 'ai',
  EmbeddingModel: 'ai',
  LanguageModelComponent: 'ai',
  MCPTools: 'code_files',
  Memory: 'local',
  'Prompt Template': 'local',
  DynamicCreateData: 'local',
  Operations: 'local',
  ParserComponent: 'local',
  SplitText: 'local',
  TypeConverterComponent: 'local',
  CalculatorComponent: 'local',
  CurrentDate: 'local',
  PythonREPLComponent: 'code_files',
};

/** Local components that produced their real output on the real engine (live receipt). Only these run. */
export const EXECUTABLE_COMPONENTS = ['ChatInput', 'ChatOutput'] as const;

/** Local components that did not prove themselves live. They stay show and edit only, with the reason. */
export const LOCAL_NOT_ENABLED: Record<string, string> = {
  NaturalLanguageTextSplitter: 'Its engine package NLTK is not installed, so it failed on the real engine. It stays off rather than downloading anything.',
  Operations: "Its operation picker shows its real settings only through a running Langflow server, which this build does not have. On the engine it passed the text through unchanged.",
  Memory: "On the engine it returned an empty result for both store and retrieve, so it is not proven. Its messages live in Langflow's database.",
  LangChainFakeEmbeddings: 'Its output (Embeddings) only feeds components that are show only here, so a run cannot show what it did.',
};

export function tierOf(componentType: string): RunTier {
  return COMPONENT_TIERS[componentType] ?? 'unknown';
}

export function isExecutable(componentType: string): boolean {
  return (EXECUTABLE_COMPONENTS as readonly string[]).includes(componentType);
}

/** Why a component does not run here, or null when it does. */
export function runBlockReason(componentType: string, label: string): string | null {
  if (isExecutable(componentType)) return null;
  const tier = tierOf(componentType);
  const name = `"${label}" (${componentType || 'unknown'})`;
  if (tier === 'local') {
    return `${name} is local but not enabled: ${LOCAL_NOT_ENABLED[componentType] ?? 'it has no live engine proof yet.'}`;
  }
  return `${name} ${TIER_REASON[tier]}. Running those is off in this app: runs stay local (Alex, 2026-10-13).`;
}
