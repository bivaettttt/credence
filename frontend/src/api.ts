let token = "";
export function session(value: string) {
  token = value;
}
export type User = { name: string; role: string; lab: boolean };
export type Org = {
  id: string;
  name: string;
  industry: string;
  profile: string;
  registration: string;
};
export type Product = {
  id: string;
  name: string;
  code: string;
  version: number;
  rate: number;
  min_amount: number;
  max_amount: number;
  min_months: number;
  max_months: number;
  active: boolean;
};
export type Inputs = {
  amount: number;
  months: number;
  purpose: string;
  revenue: number | null;
  debt: number | null;
  profit: number | null;
  age: number | null;
};
export type Application = {
  id: string;
  number: number;
  state: string;
  revision: number;
  data_version: number;
  data: Inputs;
  organization?: string;
  product?: string;
};
export type Event = {
  id: number;
  action: string;
  previous: string | null;
  state: string | null;
  actor_name: string;
  request_id: string;
  created_at: string;
  reason: string | null;
};
export type Proof = {
  id: string;
  kind: string;
  version: number;
  current: boolean;
  payload: Record<string, unknown>;
};
export type Offer = {
  state: string;
  expires_at: string;
  terms: {
    amount: number;
    months: number;
    rate: number;
    schedule: {
      month: number;
      principal: number;
      interest: number;
      payment: number;
      balance: number;
    }[];
  };
};
export type Detail = Application & {
  evidence: Proof[];
  events: Event[];
  documents: {
    id: string;
    kind: string;
    version: number;
    label: string;
    status: string;
  }[];
  snapshots: unknown[];
  offer: Offer | null;
  submission_checks?: Record<string, boolean>;
};
export type Lab = {
  scenario: string;
  passed: boolean;
  application_id: string;
  before: unknown;
  after: unknown;
  checks: Record<string, boolean>;
  events: Event[];
  traffic: {
    request_id: string;
    method: string;
    path: string;
    status: number;
  }[];
};
const errors: Record<string, string> = {
  INVALID_CREDENTIALS: "Проверьте логин и пароль.",
  REVISION_CONFLICT: "Данные изменились. Откройте заявку повторно.",
  INVALID_TRANSITION: "Команда недоступна в этом состоянии.",
  ROLE_FORBIDDEN: "Недостаточно прав.",
  APPLICATION_NOT_FOUND: "Заявка недоступна.",
  INELIGIBLE: "Подача не прошла проверки.",
  CURRENT_EVIDENCE_REQUIRED: "Нужна актуальная проверка или оценка.",
  LAB_DISABLED: "Запустите отдельный стенд лаборатории.",
  INVALID_INPUT: "Проверьте значения полей.",
};
export class ApiError extends Error {
  constructor(
    public code: string,
    public requestId: string,
    public checks?: Record<string, boolean>,
  ) {
    super(errors[code] ?? code);
  }
}
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
  key?: string,
): Promise<T> {
  const response = await fetch("/api" + path, {
    method,
    headers: {
      Authorization: "Bearer " + token,
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      ...(key ? { "Idempotency-Key": key } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (response.status === 204) return undefined as T;
  const data = await response.json();
  if (!response.ok)
    throw new ApiError(
      typeof data.detail === "string"
        ? data.detail
        : (data.detail?.code ?? "HTTP " + response.status),
      response.headers.get("X-Request-ID") ?? "",
      data.detail?.checks,
    );
  return data;
}
