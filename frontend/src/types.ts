export type QueryResponse =
  | { status: 'ok'; dataset_id: string; sql: string; results: { columns: string[]; rows: Record<string, unknown>[] }; explanation: { tables: string[]; assumptions?: string[]; notes?: string } }
  | { status: 'needs_selection'; choices: { dataset_id: string; label: string; why: string }[]; message?: string }
  | { status: 'needs_clarification'; clarifying_question: string }
  | { status: 'error'; message: string; sql?: string; dataset_id?: string }

export type ApiFetcher = (path: string, opts?: RequestInit) => Promise<unknown>
