import { expect, test, type Page } from "@playwright/test";

const fixtures = process.env.CREDENCE_DEMO_PASSWORD ?? "Credence-demo-local";
async function login(page: Page, username: string) {
  await page.getByLabel("Логин", { exact: true }).fill(username);
  await page.getByLabel("Пароль", { exact: true }).fill(fixtures);
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await expect(page.getByRole("button", { name: "Выйти" })).toBeVisible();
}
async function role(page: Page, username: string) {
  await page.getByRole("button", { name: "Выйти" }).click();
  await login(page, username);
}
async function click(page: Page, name: string) {
  await page.getByRole("button", { name, exact: true }).click();
}
async function transition(page: Page, name: string, endpoint: string) {
  const response = page.waitForResponse(
    (r) => r.url().endsWith(endpoint) && r.request().method() === "POST",
  );
  await click(page, name);
  expect((await response).status()).toBe(200);
}
async function shot(page: Page, name: string) {
  if (!process.env.CREDENCE_SHOTS) return;
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({
    path: process.env.CREDENCE_SHOTS + "/" + name + ".png",
  });
}
test("three roles process, return and accept a real application", async ({
  page,
}) => {
  await page.goto("/");
  await login(page, "applicant");
  await expect(
    page.getByRole("heading", { name: "Последние заявки" }),
  ).toBeVisible();
  await shot(page, "dashboard");
  await page.getByRole("link", { name: "Продукты" }).click();
  await expect(
    page.getByText(/Оборотное финансирование/).first(),
  ).toBeVisible();
  await shot(page, "products");
  await page.getByRole("link", { name: "Компании" }).click();
  await page.getByLabel("Название компании").fill("Северная логистика");
  await page.getByLabel("Отрасль").fill("Логистика");
  await page
    .getByLabel("Профиль", { exact: true })
    .fill("Синтетический грузовой оператор");
  await click(page, "Создать компанию");
  await expect(
    page.getByRole("cell", { name: "Северная логистика" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Мои заявки" }).click();
  await page.getByRole("link", { name: "Новая заявка" }).click();
  await page
    .getByRole("combobox", { name: "Компания", exact: true })
    .selectOption({ label: "Северная логистика" });
  await page
    .getByRole("combobox", { name: "Продукт", exact: true })
    .selectOption({ label: "Оборотное финансирование" });
  for (const [name, value] of Object.entries({
    "Сумма, коп.": "20000000",
    "Срок, месяцев": "6",
    Цель: "Учебная закупка",
    "Годовая выручка, коп.": "300000000",
    "Задолженность, коп.": "1000000",
    "Годовая прибыль, коп.": "10000000",
    "Возраст компании, месяцев": "42",
  })) {
    await page.getByLabel(name, { exact: true }).fill(value);
  }
  await shot(page, "form");
  await click(page, "Сохранить черновик");
  await expect(page.getByRole("heading", { name: /Заявка CR-/ })).toBeVisible();
  const detail = page.url().split("#")[1];
  const number = (await page
    .getByRole("heading", { name: /Заявка CR-/ })
    .textContent())!.replace("Заявка ", "");
  await page.getByLabel("Название документа").fill("Учебная финансовая сводка");
  await click(page, "Добавить документ");
  await expect(
    page.getByRole("cell", { name: "Учебная финансовая сводка" }),
  ).toBeVisible();
  await page
    .getByRole("combobox", { name: "Тип документа" })
    .selectOption("REGISTRATION");
  await page.getByLabel("Название документа").fill("Учебный профиль компании");
  await click(page, "Добавить документ");
  await expect(
    page.getByRole("cell", { name: "Учебный профиль компании" }),
  ).toBeVisible();
  await transition(page, "Отправить заявку", "/submit");
  await role(page, "analyst");
  await page.getByRole("link", { name: "Очередь заявок" }).click();
  await expect(
    page.getByRole("link", { name: number, exact: true }),
  ).toBeVisible();
  await shot(page, "queue");
  await page.getByRole("link", { name: number, exact: true }).click();
  await transition(page, "Взять на рассмотрение", "/claim");
  await expect(
    page.getByText("На рассмотрении", { exact: true }),
  ).toBeVisible();
  await shot(page, "details");
  await click(page, "Проверка");
  await transition(page, "Проверить комплектность", "/validate");
  await expect(page.getByText("Подтверждено", { exact: true })).toHaveCount(5);
  await shot(page, "eligibility");
  await click(page, "Риск-оценка");
  await transition(page, "Рассчитать оценку", "/assess");
  await expect(page.getByText(/Методика v1.0/)).toBeVisible();
  await shot(page, "risk");
  await click(page, "Решение");
  await page
    .getByRole("combobox", { name: "Действие" })
    .selectOption("request_info");
  await page.getByLabel("Обоснование").fill("Уточните размер обязательств.");
  await transition(page, "Подтвердить действие", "/request_info");
  await role(page, "applicant");
  await page.getByRole("link", { name: "Уведомления" }).click();
  await expect(page.getByText("Уточните размер обязательств.")).toBeVisible();
  await page.evaluate((hash) => (location.hash = hash), detail);
  await click(page, "Изменить черновик");
  await page.getByLabel("Задолженность, коп.").fill("2000000");
  await click(page, "Сохранить изменения");
  await expect(page.getByText(/Долг.*20/)).toBeVisible();
  await transition(page, "Отправить заявку", "/submit");
  await role(page, "analyst");
  await transition(page, "Взять на рассмотрение", "/claim");
  await click(page, "Проверка");
  await transition(page, "Проверить комплектность", "/validate");
  await click(page, "Риск-оценка");
  await transition(page, "Рассчитать оценку", "/assess");
  await expect(page.getByText(/Подача 2 · Актуальна/)).toBeVisible();
  await click(page, "Решение");
  await page
    .getByLabel("Обоснование")
    .fill("Материалы второй подачи проверены.");
  await transition(page, "Подтвердить действие", "/recommend");
  await role(page, "risk");
  await click(page, "Решение");
  await page
    .getByLabel("Обоснование")
    .fill("Условия второй подачи согласованы.");
  await shot(page, "approval");
  await transition(page, "Подтвердить действие", "/decide");
  await role(page, "applicant");
  await click(page, "Предложение");
  await expect(
    page.getByRole("heading", { name: "Кредитное предложение" }),
  ).toBeVisible();
  await shot(page, "offer");
  await transition(page, "Принять предложение", "/respond");
  await expect(
    page.getByText("Принята", { exact: true }).first(),
  ).toBeVisible();
  await click(page, "История");
  await shot(page, "timeline");
});
test("laboratory produces persisted evidence and audit", async ({ page }) => {
  await page.goto("/");
  await login(page, "admin");
  await page.getByRole("link", { name: "Лаборатория" }).click();
  await click(page, "Запустить сценарий");
  await expect(
    page.getByRole("heading", { name: "Проверка пройдена" }),
  ).toBeVisible({ timeout: 15000 });
  await expect(page.getByText(/\/recommend · HTTP 409/)).toBeVisible();
  await shot(page, "lab");
  await page.getByRole("link", { name: "Аудит" }).click();
  await expect(
    page.getByRole("cell", { name: "request_info", exact: false }).first(),
  ).toBeVisible();
  await shot(page, "audit");
});
