import { useState } from "react";

/**
 * Покупка Частинами monobank — значок і обовʼязкові юридичні тексти.
 *
 * ЧОМУ ОКРЕМИЙ КОМПОНЕНТ
 * ----------------------
 * Вимоги monobank стосуються не однієї сторінки, а кожної згадки сервісу:
 * і сторінки цін, і оформлення замовлення, і майбутніх банерів. Коли ці
 * правила розсипані по розмітці, перша ж правка тексту тихо робить сайт
 * таким, що порушує умови — а за це відключають від сервісу, не штрафують.
 * Тому все в одному місці.
 *
 * Джерела: monobank.ua/knowledge-base/chast/marketing і .../marketing/brand.
 * ---------------------------------------------------------------------------
 * 1. Назва тільки одна з трьох: «Покупка Частинами», «Покупка Частинами
 *    monobank», «Покупка Частинами monobank | Universal Bank».
 *    НЕ «Кредит monobank», НЕ «Оплата частинами», НЕ «АТ Universal Bank».
 *    Тому назва береться з констант нижче, а не набирається руками.
 *
 * 2. У будь-якій рекламі з Покупкою Частинами мають бути ДВА юридичні тексти:
 *    — про ставку й строк кредитування. Його кегль має бути **не менше 50%**
 *      від кегля слів «Покупка Частинами»;
 *    — реквізити банку. Його розмір довільний.
 *    Перше правило виконане в CSS (`--chast-name-size` → `.chast-legal__rate`),
 *    а не на око: інакше достатньо один раз збільшити заголовок, щоб вимога
 *    перестала виконуватись, і ніхто цього не помітить.
 *
 * 3. **Кастомізувати візуальні матеріали можна лише за погодженням із банком.**
 *    Через це тут НЕ намальований «схожий» значок: самотужки зроблений логотип —
 *    саме те порушення, яке правила й забороняють. Компонент показує офіційний
 *    файл із медіакіту в `public/chast/`. Джерело записане в README поруч.
 *    Текстовий варіант лишений на випадок помилки завантаження.
 */

/* Дозволені написання. Брати звідси, не набирати руками. */
export const CHAST_SHORT = "Покупка Частинами";
export const CHAST_NAME = "Покупка Частинами monobank";
export const CHAST_FULL = "Покупка Частинами monobank | Universal Bank";

/* Текст 1 — кегль ≥ 50% від «Покупка Частинами» */
export const CHAST_RATE_NOTE =
  "Реальна річна процентна ставка — 0,000001%, макс. строк кредитування " +
  "до 400 000 грн — 24 місяці. Перший внесок — аванс у розмірі щомісячного платежу.";

/* Текст 2 — розмір довільний */
export const CHAST_BANK_NOTE =
  "АТ «УНІВЕРСАЛ БАНК», Ліцензія НБУ №92 від 20.01.1994, " +
  "у держреєстрі банків №226, деталі на monobank.ua";

/* Оригінальний SVG із медіакіту, без перемальовування чи зміни кольорів. */
const BADGE_SRC = "/chast/chast-badge.svg";

/**
 * @param {"short"|"name"|"full"} naming  яке з дозволених написань показати
 * @param {"sm"|"md"} size
 */
export function ChastBadge({ naming = "name", size = "md", className = "" }) {
  const [hasAsset, setHasAsset] = useState(true);
  const label =
    naming === "short" ? CHAST_SHORT : naming === "full" ? CHAST_FULL : CHAST_NAME;

  return (
    <span className={`chast-badge chast-badge--${size} ${className}`.trim()}>
      {hasAsset ? (
        <span className="chast-badge__brand">
          <img
            className="chast-badge__img"
            src={BADGE_SRC}
            alt={CHAST_SHORT}
            width="1296"
            height="136"
            onError={() => setHasAsset(false)}
            loading="lazy"
          />
          {naming !== "short" && (
            <span className="chast-badge__provider">
              {naming === "full" ? "monobank | Universal Bank" : "monobank"}
            </span>
          )}
        </span>
      ) : (
        <span className="chast-badge__text">{label}</span>
      )}
    </span>
  );
}

/**
 * Обовʼязкові юридичні тексти. Ставити поруч із КОЖНОЮ згадкою сервісу.
 *
 * `full` додає перелік істотних характеристик продукту — він потрібен там,
 * де ПЧ описана як спосіб оплати (сторінка цін), і зайвий там, де це просто
 * одна з кнопок (оформлення замовлення).
 */
export function ChastLegal({ full = false }) {
  return (
    <div className="chast-legal">
      <strong className="chast-legal__name">{CHAST_FULL}</strong>

      {/* Кегль цього абзацу привʼязаний до --chast-name-size у CSS. Вимога
          банку: не менше половини від кегля слів «Покупка Частинами». */}
      <p className="chast-legal__rate">{CHAST_RATE_NOTE}</p>

      {full && (
        <ul className="chast-legal__facts">
          <li>Мінімальна сума розстрочки: 2 грн</li>
          <li>Максимальна сума розстрочки: 400 000 грн</li>
          <li>Реальна річна процентна ставка: 0,000001%</li>
          <li>Доступний строк, платежів: 3 — 25</li>
          <li>Порядок погашення: щомісячні платежі рівними частинами</li>
          <li>Перший платіж у момент оформлення покупки</li>
        </ul>
      )}

      <p className="chast-legal__bank">{CHAST_BANK_NOTE}</p>

      <p className="chast-legal__link">
        Інформація про істотні характеристики продукту та попередження —
        на сайті продукту{" "}
        <a href="https://chast.monobank.ua" target="_blank" rel="noreferrer">
          chast.monobank.ua
        </a>
      </p>
    </div>
  );
}

export default ChastBadge;
