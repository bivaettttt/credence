import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/600.css";
import "./styles.css";
import { useEffect, useState, type ReactNode, type FormEvent } from "react";
import { createRoot } from "react-dom/client";
import {
  type LucideIcon,
  ArrowRight,
  Bell,
  Building2,
  ClipboardCheck,
  Files,
  FlaskConical,
  Landmark,
  LayoutDashboard,
  LogOut,
  Settings,
  ShieldCheck,
} from "lucide-react";
import {
  api,
  ApiError,
  session,
  type User,
  type Org,
  type Product,
  type Application,
  type Detail,
  type Event,
  type Lab,
  type Inputs,
} from "./api";

const money = (v: number) =>
  new Intl.NumberFormat("ru", { style: "currency", currency: "RUB" }).format(
    v / 100,
  );
const stamp = (v: string) => new Date(v).toLocaleString("ru");
const states: Record<string, string> = {
  DRAFT: "Черновик",
  SUBMITTED: "Подана",
  REVIEW: "На рассмотрении",
  INFO_REQUIRED: "Нужны сведения",
  DECISION_PENDING: "На согласовании",
  OFFERED: "Предложение",
  REJECTED: "Отклонена",
  ACCEPTED: "Принята",
  DECLINED: "Отказ заявителя",
  EXPIRED: "Истекла",
  WITHDRAWN: "Отозвана",
};
const labels: Record<string, string> = {
  amount: "Сумма",
  term: "Срок",
  documents: "Документы",
  financials: "Финансовые сведения",
  organization: "Компания",
  FINANCIAL: "Финансовая сводка",
  REGISTRATION: "Регистрационный профиль",
  SUPPORTING: "Дополнительные сведения",
};
const roles: Record<string, string> = {
  APPLICANT: "Заявитель",
  CREDIT_ANALYST: "Кредитный аналитик",
  RISK_OFFICER: "Риск-офицер",
  ADMIN: "Администратор",
};
const form = (e: FormEvent<HTMLFormElement>) => {
  e.preventDefault();
  return Object.fromEntries(new FormData(e.currentTarget)) as Record<
    string,
    string
  >;
};
function useData<T>(path: string, epoch: number) {
  const [state, set] = useState<{ data?: T; error?: Error; pending: boolean }>({
    pending: true,
  });
  useEffect(() => {
    let active = true;
    set({ pending: true });
    api<T>(path).then(
      (data) => {
        if (active) set({ data, pending: false });
      },
      (error) => {
        if (active) set({ error, pending: false });
      },
    );
    return () => {
      active = false;
    };
  }, [path, epoch]);
  return state;
}
function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="panel">
      <h2>{title}</h2>
      {children}
    </section>
  );
}
function State({ value }: { value: string }) {
  return (
    <span
      className={
        "tag " +
        (["ACCEPTED", "OFFERED", "VERIFIED"].includes(value)
          ? "green"
          : ["INFO_REQUIRED", "DECISION_PENDING", "REVIEW"].includes(value)
            ? "amber"
            : "")
      }
    >
      {states[value] ?? value}
    </span>
  );
}
function ErrorBox({ error }: { error: unknown }) {
  return error ? (
    <div className="error" role="alert">
      {error instanceof Error ? error.message : String(error)}
      {error instanceof ApiError && <small>{error.requestId}</small>}
      {error instanceof ApiError && error.checks && (
        <Checks checks={error.checks} />
      )}
    </div>
  ) : null;
}
function Checks({ checks }: { checks: Record<string, boolean> }) {
  return (
    <ul className="checks">
      {Object.entries(checks).map(([k, v]) => (
        <li key={k}>
          {labels[k] ?? k}
          <span className={v ? "ok" : "fail"}>
            {v ? "Подтверждено" : "Не пройдено"}
          </span>
        </li>
      ))}
    </ul>
  );
}
function Table({ headers, rows }: { headers: string[]; rows: ReactNode[][] }) {
  return rows.length ? (
    <div className="scroll">
      <table>
        <thead>
          <tr>
            {headers.map((v, i) => (
              <th key={i}>{v}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {row.map((x, j) => (
                <td key={j}>{x}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ) : (
    <p className="pad muted">Записей пока нет.</p>
  );
}
function Json({ value }: { value: unknown }) {
  return <pre>{JSON.stringify(value, null, 2)}</pre>;
}
function Head({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children?: ReactNode;
}) {
  return (
    <header className="heading">
      <div>
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {children}
    </header>
  );
}
function Brand() {
  return (
    <div className="brand">
      <span>
        <Landmark size={21} />
      </span>
      Credence
    </div>
  );
}
function Credentials({ done }: { done: (user: User) => void }) {
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  return (
    <div className="login">
      <div className="login-intro">
        <Brand />
        <div>
          <h1>
            Кредитная заявка.
            <br />
            От подачи до решения.
          </h1>
          <p>Учебное пространство для заявителей и кредитной команды.</p>
        </div>
      </div>
      <section>
        <h2>Вход в Credence</h2>
        <form
          onSubmit={(e) => {
            const body = form(e);
            setBusy(true);
            setError(null);
            void api<{ token: string }>("/auth/login", "POST", body)
              .then(async (x) => {
                session(x.token);
                done(await api<User>("/me"));
              })
              .catch(setError)
              .finally(() => setBusy(false));
          }}
        >
          <label>
            Логин
            <input name="username" required autoComplete="username" />
          </label>
          <label>
            Пароль
            <input
              name="password"
              type="password"
              required
              autoComplete="current-password"
            />
          </label>
          <ErrorBox error={error} />
          <button className="primary" disabled={busy}>
            Войти <ArrowRight size={16} />
          </button>
        </form>
      </section>
    </div>
  );
}
function App() {
  const [user, setUser] = useState<User | null>(null);
  const [route, setRoute] = useState(
    () => location.hash.slice(1) || "overview",
  );
  const [epoch, refresh] = useState(0);
  const [error, setError] = useState<unknown>();
  useEffect(() => {
    const update = () => setRoute(location.hash.slice(1) || "overview");
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
  const update = () => refresh((i) => i + 1);
  if (!user) return <Credentials done={setUser} />;
  const items: [string, string, LucideIcon][] = [
    ["overview", "Обзор", LayoutDashboard],
    [
      "applications",
      user.role === "APPLICANT" ? "Мои заявки" : "Очередь заявок",
      Files,
    ],
    ...(user.role === "APPLICANT"
      ? [
          ["organizations", "Компании", Building2] as [
            string,
            string,
            LucideIcon,
          ],
          ["notifications", "Уведомления", Bell] as [
            string,
            string,
            LucideIcon,
          ],
        ]
      : []),
    ["products", "Продукты", Landmark],
    ...(user.role === "ADMIN"
      ? [
          ["users", "Пользователи", Settings] as [string, string, LucideIcon],
          ["audit", "Аудит", ShieldCheck] as [string, string, LucideIcon],
        ]
      : []),
    ...(user.lab
      ? [["lab", "Лаборатория", FlaskConical] as [string, string, LucideIcon]]
      : []),
  ];
  return (
    <div className="shell">
      <aside>
        <Brand />
        <nav aria-label="Разделы">
          {items.map(([path, title, Icon]) => (
            <a
              key={path}
              href={"#" + path}
              className={
                route === path || route.startsWith(path + "/") ? "active" : ""
              }
            >
              <Icon size={17} />
              {title}
            </a>
          ))}
        </nav>
        <small>Учебная среда · RUB</small>
      </aside>
      <div className="workspace">
        <div className="top">
          <span>
            <ClipboardCheck size={16} /> {roles[user.role]}
          </span>
          <div>
            {user.name}
            <button
              aria-label="Выйти"
              onClick={() =>
                void api("/auth/logout", "POST")
                  .then(() => {
                    session("");
                    setUser(null);
                  })
                  .catch(setError)
              }
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
        <main>
          <ErrorBox error={error} />
          {route === "overview" ? (
            <Overview epoch={epoch} />
          ) : route === "applications" ? (
            <Registry epoch={epoch} user={user} />
          ) : route === "applications/new" && user.role === "APPLICANT" ? (
            <Create epoch={epoch} />
          ) : route.startsWith("applications/") ? (
            <ApplicationView
              key={route}
              id={route.split("/")[1]}
              user={user}
              epoch={epoch}
              update={update}
            />
          ) : route === "organizations" ? (
            <Organizations epoch={epoch} update={update} />
          ) : route === "products" ? (
            <Products
              epoch={epoch}
              update={update}
              admin={user.role === "ADMIN"}
            />
          ) : route === "notifications" ? (
            <Notifications epoch={epoch} update={update} />
          ) : route === "audit" ? (
            <Audit epoch={epoch} />
          ) : route === "users" ? (
            <Users epoch={epoch} update={update} />
          ) : route === "lab" && user.lab ? (
            <Laboratory />
          ) : (
            <Head title="Раздел недоступен" />
          )}
        </main>
      </div>
    </div>
  );
}
function Overview({ epoch }: { epoch: number }) {
  const stats = useData<{ state: string; count: number }[]>("/stats", epoch);
  const rows = useData<Application[]>("/applications", epoch);
  return (
    <>
      <Head
        title="Обзор заявок"
        subtitle="Состояние кредитного процесса по доступным заявкам"
      />
      <ErrorBox error={stats.error ?? rows.error} />
      <div className="metrics">
        {stats.data?.map((s) => (
          <div key={s.state}>
            <small>{states[s.state]}</small>
            <strong>{s.count}</strong>
          </div>
        ))}
      </div>
      <Panel title="Последние заявки">
        {rows.pending ? (
          <p className="pad">Загрузка…</p>
        ) : (
          <Applications rows={rows.data?.slice(0, 8) ?? []} />
        )}
      </Panel>
    </>
  );
}
function Applications({ rows }: { rows: Application[] }) {
  return (
    <Table
      headers={["Номер", "Компания", "Продукт", "Сумма", "Состояние"]}
      rows={rows.map((a) => [
        <a href={"#applications/" + a.id}>CR-{a.number}</a>,
        a.organization,
        a.product,
        money(a.data.amount),
        <State value={a.state} />,
      ])}
    />
  );
}
function Registry({ epoch, user }: { epoch: number; user: User }) {
  const [filter, setFilter] = useState("");
  const [offset, setOffset] = useState(0);
  const rows = useData<Application[]>(
    "/applications?offset=" + offset + "&" + filter,
    epoch,
  );
  return (
    <>
      <Head
        title={
          user.role === "APPLICANT" ? "Мои заявки" : "Очередь рассмотрения"
        }
        subtitle="Поиск по номеру заявки или компании"
      >
        {user.role === "APPLICANT" && (
          <a className="primary" href="#applications/new">
            Новая заявка <ArrowRight size={16} />
          </a>
        )}
      </Head>
      <ErrorBox error={rows.error} />
      <Panel title="Реестр">
        <form
          className="pad inline"
          onSubmit={(e) => {
            const f = form(e);
            setOffset(0);
            setFilter(
              new URLSearchParams(
                Object.entries(f).filter(([, v]) => v),
              ).toString(),
            );
          }}
        >
          <label>
            Поиск
            <input name="q" />
          </label>
          <label>
            Статус
            <select name="state">
              <option value="">Все</option>
              {Object.entries(states).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <button>Применить</button>
        </form>
        {rows.pending ? (
          <p className="pad">Загрузка…</p>
        ) : (
          <Applications rows={rows.data ?? []} />
        )}
        <div className="pad inline">
          <button disabled={!offset} onClick={() => setOffset(offset - 50)}>
            Назад
          </button>
          <button
            disabled={(rows.data?.length ?? 0) < 50}
            onClick={() => setOffset(offset + 50)}
          >
            Далее
          </button>
        </div>
      </Panel>
    </>
  );
}
function InputFields({ v }: { v?: Inputs }) {
  return (
    <>
      <label>
        Сумма, коп.
        <input
          name="amount"
          type="number"
          min="1"
          required
          defaultValue={v?.amount}
        />
      </label>
      <label>
        Срок, месяцев
        <input
          name="months"
          type="number"
          required
          min="1"
          max="60"
          defaultValue={v?.months}
        />
      </label>
      <label>
        Цель
        <input name="purpose" required defaultValue={v?.purpose} />
      </label>
      <label>
        Годовая выручка, коп.
        <input
          name="revenue"
          type="number"
          min="1"
          defaultValue={v?.revenue ?? ""}
        />
      </label>
      <label>
        Задолженность, коп.
        <input name="debt" type="number" min="0" defaultValue={v?.debt ?? ""} />
      </label>
      <label>
        Годовая прибыль, коп.
        <input name="profit" type="number" defaultValue={v?.profit ?? ""} />
      </label>
      <label>
        Возраст компании, месяцев
        <input
          name="age"
          type="number"
          min="0"
          max="1200"
          defaultValue={v?.age ?? ""}
        />
      </label>
    </>
  );
}
function fields(v: Record<string, string>) {
  return {
    ...Object.fromEntries(
      ["amount", "months", "revenue", "debt", "profit", "age"].map((k) => [
        k,
        v[k] === "" ? null : Number(v[k]),
      ]),
    ),
    purpose: v.purpose,
  };
}
function Create({ epoch }: { epoch: number }) {
  const orgs = useData<Org[]>("/organizations", epoch);
  const products = useData<Product[]>("/loan-products", epoch);
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  return (
    <>
      <Head
        title="Новая заявка"
        subtitle="Данные вымышленной компании и запрошенные условия"
      />
      <ErrorBox error={error ?? orgs.error ?? products.error} />
      <Panel title="Параметры финансирования">
        <form
          className="pad form"
          onSubmit={(e) => {
            const v = form(e);
            setBusy(true);
            void api<Application>("/applications", "POST", {
              ...fields(v),
              organization_id: v.organization_id,
              product_id: v.product_id,
            })
              .then((r) => {
                location.hash = "applications/" + r.id;
              })
              .catch(setError)
              .finally(() => setBusy(false));
          }}
        >
          <label>
            Компания
            <select name="organization_id" required>
              <option value="">Выберите</option>
              {orgs.data?.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Продукт
            <select name="product_id" required>
              <option value="">Выберите</option>
              {products.data?.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name}
                </option>
              ))}
            </select>
          </label>
          <InputFields />
          <button className="primary" disabled={busy}>
            Сохранить черновик
          </button>
        </form>
      </Panel>
    </>
  );
}
function ApplicationView({
  id,
  user,
  epoch,
  update,
}: {
  id: string;
  user: User;
  epoch: number;
  update: () => void;
}) {
  const path = "/applications/" + id;
  const query = useData<Detail>(path, epoch);
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const [edit, setEdit] = useState(false);
  const [tab, setTab] = useState("summary");
  const a = query.data;
  async function send(
    suffix: string,
    method = "POST",
    body: object = {},
    critical = false,
  ) {
    if (!a) return;
    setBusy(true);
    setError(null);
    try {
      await api(
        path + suffix,
        method,
        { revision: a.revision, ...body },
        critical ? crypto.randomUUID() : undefined,
      );
      setEdit(false);
      update();
    } catch (error) {
      setError(error);
    } finally {
      setBusy(false);
    }
  }
  const command = (action: string, body: object = {}) =>
    void send("/" + action, "POST", body, true);
  if (!a)
    return (
      <>
        <ErrorBox error={query.error} />
        {query.pending && <p>Загрузка заявки…</p>}
      </>
    );
  const applicant = user.role === "APPLICANT";
  const analyst = user.role === "CREDIT_ANALYST";
  const editable = applicant && ["DRAFT", "INFO_REQUIRED"].includes(a.state);
  const risk = a.evidence.filter((e) => e.kind === "RISK");
  const check = a.evidence.find((e) => e.kind === "ELIGIBILITY" && e.current);
  const currentRisk = risk.find((e) => e.current);
  return (
    <>
      <a href="#applications">← Реестр заявок</a>
      <Head
        title={"Заявка CR-" + a.number}
        subtitle={"Редакция " + a.revision + " · Подача " + a.data_version}
      >
        <State value={a.state} />
      </Head>
      <ErrorBox error={error} />
      <div className="tabs">
        {[
          ["summary", "Материалы"],
          ["eligibility", "Проверка"],
          ["risk", "Риск-оценка"],
          ["decision", "Решение"],
          ["offer", "Предложение"],
          ["history", "История"],
        ]
          .filter(([k]) => !applicant || !["risk", "eligibility"].includes(k))
          .map(([k, v]) => (
            <button
              key={k}
              className={tab === k ? "selected" : ""}
              onClick={() => setTab(k)}
            >
              {v}
            </button>
          ))}
      </div>
      {tab === "summary" && (
        <>
          <Panel title="Запрошенные условия">
            {edit ? (
              <form
                className="pad form"
                onSubmit={(e) => void send("", "PATCH", fields(form(e)))}
              >
                <InputFields v={a.data} />
                <button className="primary" disabled={busy}>
                  Сохранить изменения
                </button>
              </form>
            ) : (
              <div className="pad stack">
                <strong className="amount">{money(a.data.amount)}</strong>
                <p>
                  {a.data.months} мес. · {a.data.purpose}
                </p>
                <p>
                  Выручка{" "}
                  {a.data.revenue === null ? "—" : money(a.data.revenue)} · Долг{" "}
                  {a.data.debt === null ? "—" : money(a.data.debt)}
                </p>
                {editable && (
                  <button onClick={() => setEdit(true)}>
                    Изменить черновик
                  </button>
                )}
              </div>
            )}
          </Panel>
          <Panel title="Учебные документы">
            <Table
              headers={["Тип", "Файл / запись", "Версия", "Статус"]}
              rows={a.documents.map((d) => [
                labels[d.kind],
                d.label,
                "v" + d.version,
                <State value={d.status} />,
              ])}
            />
            {editable && (
              <form
                className="pad inline"
                onSubmit={(e) => void send("/documents", "POST", form(e))}
              >
                <label>
                  Тип документа
                  <select name="kind">
                    {["FINANCIAL", "REGISTRATION", "SUPPORTING"].map((k) => (
                      <option key={k} value={k}>
                        {labels[k]}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Название документа
                  <input name="label" required />
                </label>
                <button disabled={busy}>Добавить документ</button>
              </form>
            )}
          </Panel>
          <div className="inline">
            {editable && (
              <button
                className="primary"
                disabled={busy}
                onClick={() => command("submit")}
              >
                Отправить заявку
              </button>
            )}
            {analyst && a.state === "SUBMITTED" && (
              <button
                className="primary"
                disabled={busy}
                onClick={() => command("claim")}
              >
                Взять на рассмотрение
              </button>
            )}
            {applicant &&
              ["DRAFT", "SUBMITTED", "REVIEW", "INFO_REQUIRED"].includes(
                a.state,
              ) && (
                <button
                  disabled={busy}
                  onClick={() => {
                    if (confirm("Отозвать заявку?")) command("withdraw");
                  }}
                >
                  Отозвать
                </button>
              )}
          </div>
        </>
      )}
      {tab === "eligibility" && (
        <Panel title="Проверка комплектности">
          {check ? (
            <div className="pad">
              <Checks
                checks={check.payload.checks as Record<string, boolean>}
              />
            </div>
          ) : (
            <p className="pad muted">Результат проверки отсутствует.</p>
          )}
          {analyst && a.state === "REVIEW" && !check && (
            <div className="pad">
              <button
                className="primary"
                disabled={busy}
                onClick={() => command("validate")}
              >
                Проверить комплектность
              </button>
            </div>
          )}
        </Panel>
      )}
      {tab === "risk" && (
        <Panel title="Учебная риск-оценка">
          {analyst && a.state === "REVIEW" && check && !currentRisk && (
            <div className="pad">
              <button
                className="primary"
                disabled={busy}
                onClick={() => command("assess")}
              >
                Рассчитать оценку
              </button>
            </div>
          )}
          {risk.length === 0 && <p className="pad muted">Оценки пока нет.</p>}
          {risk.map((e) => (
            <div className="pad stack" key={e.id}>
              <div className="inline">
                <strong className="amount">
                  {String(e.payload.score)} / 100
                </strong>
                <State value={String(e.payload.category)} />
                <span>
                  Подача {e.version} · {e.current ? "Актуальна" : "Устарела"}
                </span>
              </div>
              <p>
                {String(e.payload.explanation)} Методика v
                {String(e.payload.model)}.
              </p>
              <Table
                headers={["Правило", "Фактор", "Вход", "Баллы"]}
                rows={(
                  e.payload.factors as {
                    id: string;
                    label: string;
                    value: unknown;
                    points: number;
                  }[]
                ).map((f) => [
                  f.id,
                  f.label,
                  JSON.stringify(f.value),
                  f.points,
                ])}
              />
            </div>
          ))}
        </Panel>
      )}
      {tab === "decision" && (
        <>
          <Panel title="Рекомендации и решения">
            {a.evidence
              .filter((e) => ["DECISION", "RECOMMENDATION"].includes(e.kind))
              .map((e) => (
                <div key={e.id} className="pad">
                  <strong>
                    {e.kind === "DECISION" ? "Решение" : "Рекомендация"} ·{" "}
                    {String(e.payload.choice)}
                  </strong>
                  <p>
                    {String(e.payload.reason)} · Подача {e.version}
                  </p>
                </div>
              ))}
            {((analyst && a.state === "REVIEW") ||
              (user.role === "RISK_OFFICER" &&
                a.state === "DECISION_PENDING")) && (
              <form
                className="pad form"
                onSubmit={(e) => {
                  const v = form(e);
                  if (["request_info", "return"].includes(v.action))
                    command(v.action, { reason: v.reason });
                  else
                    command(v.action, { choice: v.choice, reason: v.reason });
                }}
              >
                <label>
                  Действие
                  <select name="action">
                    {analyst ? (
                      <>
                        <option value="recommend">Рекомендовать решение</option>
                        <option value="request_info">Запросить сведения</option>
                      </>
                    ) : (
                      <>
                        <option value="decide">Принять решение</option>
                        <option value="return">Вернуть аналитику</option>
                      </>
                    )}
                  </select>
                </label>
                <label>
                  Результат
                  <select name="choice">
                    <option value="APPROVE">Одобрить</option>
                    <option value="REJECT">Отклонить</option>
                  </select>
                </label>
                <label>
                  Обоснование
                  <textarea name="reason" required minLength={5} />
                </label>
                <button className="primary" disabled={busy}>
                  Подтвердить действие
                </button>
              </form>
            )}
          </Panel>
        </>
      )}
      {tab === "offer" && (
        <Panel title="Кредитное предложение">
          {a.offer ? (
            <>
              <div className="pad stack">
                <strong className="amount">
                  {money(a.offer.terms.amount)}
                </strong>
                <p>
                  {a.offer.terms.months} мес. · {a.offer.terms.rate / 100}%
                  годовых · до {stamp(a.offer.expires_at)}
                </p>
                <State value={a.offer.state} />
                {applicant && a.state === "OFFERED" && (
                  <div className="inline">
                    <button
                      className="primary"
                      disabled={busy}
                      onClick={() => command("respond", { choice: "ACCEPT" })}
                    >
                      Принять предложение
                    </button>
                    <button
                      disabled={busy}
                      onClick={() => command("respond", { choice: "DECLINE" })}
                    >
                      Отклонить предложение
                    </button>
                  </div>
                )}
              </div>
              <Table
                headers={[
                  "Месяц",
                  "Основной долг",
                  "Проценты",
                  "Платёж",
                  "Остаток",
                ]}
                rows={a.offer.terms.schedule.map((s) => [
                  s.month,
                  money(s.principal),
                  money(s.interest),
                  money(s.payment),
                  money(s.balance),
                ])}
              />
            </>
          ) : (
            <p className="pad muted">Предложение пока отсутствует.</p>
          )}
        </Panel>
      )}
      {tab === "history" && (
        <Panel title="Хронология заявки">
          <Events rows={a.events} />
          <details>
            <summary>Снимки подач</summary>
            <Json value={a.snapshots} />
          </details>
        </Panel>
      )}
    </>
  );
}
function Organizations({
  epoch,
  update,
}: {
  epoch: number;
  update: () => void;
}) {
  const rows = useData<Org[]>("/organizations", epoch);
  const [editing, setEditing] = useState<Org>();
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  return (
    <>
      <Head
        title="Учебные компании"
        subtitle="Синтетические регистрационные профили"
      />
      <ErrorBox error={rows.error ?? error} />
      <Panel title="Компании">
        <Table
          headers={["Название", "Отрасль", "Регистрация", "Действие"]}
          rows={(rows.data ?? []).map((r) => [
            r.name,
            r.industry,
            <code>{r.registration}</code>,
            <button onClick={() => setEditing(r)}>Изменить</button>,
          ])}
        />
      </Panel>
      <Panel title={editing ? "Редактирование компании" : "Новая компания"}>
        <form
          key={editing?.id ?? epoch}
          className="pad form"
          onSubmit={(e) => {
            const v = form(e);
            setBusy(true);
            void api(
              editing ? "/organizations/" + editing.id : "/organizations",
              editing ? "PUT" : "POST",
              v,
            )
              .then(() => {
                setEditing(undefined);
                update();
              })
              .catch(setError)
              .finally(() => setBusy(false));
          }}
        >
          <label>
            Название компании
            <input name="name" required defaultValue={editing?.name} />
          </label>
          <label>
            Отрасль
            <input name="industry" required defaultValue={editing?.industry} />
          </label>
          <label>
            Профиль
            <textarea name="profile" required defaultValue={editing?.profile} />
          </label>
          <button className="primary" disabled={busy}>
            {editing ? "Сохранить компанию" : "Создать компанию"}
          </button>
          {editing && (
            <button type="button" onClick={() => setEditing(undefined)}>
              Отмена
            </button>
          )}
        </form>
      </Panel>
    </>
  );
}
function Products({
  epoch,
  update,
  admin,
}: {
  epoch: number;
  update: () => void;
  admin: boolean;
}) {
  const rows = useData<Product[]>("/loan-products", epoch);
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  return (
    <>
      <Head
        title="Кредитные продукты"
        subtitle="Учебные условия и редакции каталога"
      />
      <ErrorBox error={rows.error ?? error} />
      <Panel title="Каталог">
        <Table
          headers={[
            "Продукт",
            "Редакция",
            "Сумма",
            "Срок",
            "Ставка",
            "Доступность",
          ]}
          rows={(rows.data ?? []).map((p) => [
            p.name + " · " + p.code,
            p.version,
            money(p.min_amount) + " – " + money(p.max_amount),
            p.min_months + "–" + p.max_months + " мес.",
            p.rate / 100 + "%",
            p.active ? "Активен" : "Закрыт",
          ])}
        />
      </Panel>
      {admin && (
        <Panel title="Опубликовать условия">
          <form
            key={epoch}
            className="pad form"
            onSubmit={(e) => {
              const v = form(e);
              setBusy(true);
              void api("/loan-products", "POST", {
                code: v.code,
                name: v.name,
                active: v.active === "yes",
                ...Object.fromEntries(
                  [
                    "min_amount",
                    "max_amount",
                    "min_months",
                    "max_months",
                    "rate",
                  ].map((k) => [k, Number(v[k])]),
                ),
              })
                .then(update)
                .catch(setError)
                .finally(() => setBusy(false));
            }}
          >
            <label>
              Код
              <input name="code" required />
            </label>
            <label>
              Название
              <input name="name" required />
            </label>
            {[
              ["min_amount", "Сумма от, коп."],
              ["max_amount", "Сумма до, коп."],
              ["min_months", "Срок от, мес."],
              ["max_months", "Срок до, мес."],
              ["rate", "Ставка, базисные пункты"],
            ].map(([name, label]) => (
              <label key={name}>
                {label}
                <input type="number" name={name} required min="0" />
              </label>
            ))}
            <label>
              Доступность
              <select name="active">
                <option value="yes">Активен</option>
                <option value="no">Закрыт</option>
              </select>
            </label>
            <button className="primary" disabled={busy}>
              Опубликовать редакцию
            </button>
          </form>
        </Panel>
      )}
    </>
  );
}
function Users({ epoch, update }: { epoch: number; update: () => void }) {
  const rows = useData<
    { username: string; name: string; role: string; active: boolean }[]
  >("/users", epoch);
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  return (
    <>
      <Head title="Учебные пользователи" />
      <ErrorBox error={rows.error ?? error} />
      <Panel title="Участники">
        <Table
          headers={["Логин", "Имя", "Роль", "Статус"]}
          rows={(rows.data ?? []).map((u) => [
            u.username,
            u.name,
            roles[u.role],
            u.active ? "Активен" : "Отключён",
          ])}
        />
      </Panel>
      <Panel title="Новая учётная запись">
        <form
          key={epoch}
          className="pad form"
          onSubmit={(e) => {
            const v = form(e);
            setBusy(true);
            void api("/users", "POST", v)
              .then(update)
              .catch(setError)
              .finally(() => setBusy(false));
          }}
        >
          <label>
            Логин
            <input name="username" required />
          </label>
          <label>
            Имя
            <input name="name" required />
          </label>
          <label>
            Пароль
            <input name="password" type="password" required minLength={12} />
          </label>
          <label>
            Роль
            <select name="role">
              {Object.entries(roles).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <button className="primary" disabled={busy}>
            Создать пользователя
          </button>
        </form>
      </Panel>
    </>
  );
}
function Events({ rows }: { rows: Event[] }) {
  return (
    <Table
      headers={["Действие", "Переход", "Субъект", "Время", "Запрос"]}
      rows={rows.map((e) => [
        <>
          {e.action}
          {e.reason && <small>{e.reason}</small>}
        </>,
        [e.previous, e.state]
          .filter(Boolean)
          .map((s) => states[s!] ?? s)
          .join(" → "),
        e.actor_name ?? "—",
        e.created_at ? stamp(e.created_at) : "—",
        <code title={e.request_id}>{e.request_id.slice(0, 8)}</code>,
      ])}
    />
  );
}
function Audit({ epoch }: { epoch: number }) {
  const [offset, setOffset] = useState(0);
  const rows = useData<Event[]>("/audit?offset=" + offset, epoch);
  return (
    <>
      <Head
        title="Журнал аудита"
        subtitle="События и идентификаторы запросов"
      />
      <ErrorBox error={rows.error} />
      <Panel title="История действий">
        <Events rows={rows.data ?? []} />
        <div className="pad inline">
          <button disabled={!offset} onClick={() => setOffset(offset - 100)}>
            Назад
          </button>
          <button
            disabled={(rows.data?.length ?? 0) < 100}
            onClick={() => setOffset(offset + 100)}
          >
            Далее
          </button>
        </div>
      </Panel>
    </>
  );
}
function Notifications({
  epoch,
  update,
}: {
  epoch: number;
  update: () => void;
}) {
  const rows = useData<
    {
      id: number;
      app_id: string;
      message: string;
      read_at: string | null;
      created_at: string;
    }[]
  >("/notifications", epoch);
  const [error, setError] = useState<unknown>();
  return (
    <>
      <Head title="Уведомления" />
      <ErrorBox error={rows.error ?? error} />
      <Panel title="Входящие">
        <Table
          headers={["Сообщение", "Когда", "Заявка", "Статус"]}
          rows={(rows.data ?? []).map((n) => [
            n.message,
            stamp(n.created_at),
            <a href={"#applications/" + n.app_id}>Открыть</a>,
            n.read_at ? (
              "Прочитано"
            ) : (
              <button
                onClick={() =>
                  void api("/notifications/" + n.id + "/read", "POST")
                    .then(update)
                    .catch(setError)
                }
              >
                Отметить прочитанным
              </button>
            ),
          ])}
        />
      </Panel>
    </>
  );
}
const scenarios: Record<string, string> = {
  success: "Успешная заявка",
  incomplete: "Неполные данные",
  additional: "Дополнительные документы",
  mismatch: "Несоответствие продукту",
  high: "Высокий риск",
  review: "Ручное рассмотрение",
  approval: "Независимое согласование",
  rejection: "Отклонение заявки",
  stale: "Устаревшая оценка",
  concurrent: "Конкурентные решения",
  replay: "Повтор согласования",
  expired: "Истечение предложения",
  invalid: "Недопустимый переход",
  foreign: "Чужая заявка",
};
function Laboratory() {
  const [scenario, setScenario] = useState("stale");
  const [result, setResult] = useState<Lab>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  return (
    <>
      <Head
        title="Лаборатория Credence"
        subtitle="Реальные запросы API и снимки PostgreSQL в изолированной среде"
      />
      <ErrorBox error={error} />
      <Panel title="Сценарии">
        <form
          className="pad inline"
          onSubmit={(e) => {
            e.preventDefault();
            setBusy(true);
            setError(null);
            setResult(undefined);
            void api<Lab>("/lab/" + scenario, "POST")
              .then(setResult)
              .catch(setError)
              .finally(() => setBusy(false));
          }}
        >
          <label>
            Сценарий
            <select
              value={scenario}
              onChange={(e) => setScenario(e.target.value)}
              disabled={busy}
            >
              {Object.entries(scenarios).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <button className="primary" disabled={busy}>
            {busy ? "Выполняем запросы…" : "Запустить сценарий"}
          </button>
        </form>
      </Panel>
      {result && (
        <>
          <Panel
            title={result.passed ? "Проверка пройдена" : "Ошибка инварианта"}
          >
            <div className="pad">
              <Checks checks={result.checks} />
              <a href={"#applications/" + result.application_id}>
                Открыть заявку эксперимента
              </a>
            </div>
          </Panel>
          <Panel title="Переходы состояний">
            <Events rows={result.events} />
            <details>
              <summary>Состояние PostgreSQL до и после</summary>
              <Json value={{ before: result.before, after: result.after }} />
            </details>
          </Panel>
          <Panel title="HTTP-запросы и ответы">
            {result.traffic.map((step) => (
              <details key={step.request_id}>
                <summary>
                  {step.method} {step.path} · HTTP {step.status}
                </summary>
                <Json value={step} />
              </details>
            ))}
          </Panel>
        </>
      )}
    </>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
