import { useCallback, useEffect, useState } from "react";
import {
  adminGetOrders, adminUpdateOrder, adminManualPayment, adminSetDiscount,
} from "../api/admin.js";

/* Підстави для знижки. Мають збігатися з DISCOUNT_LABELS у pricing.py —
   бекенд відхиляє невідомі ключі, тож розбіжність вилізе одразу, а не мовчки. */
const DISCOUNTS = [
  { key: "family", label: "Сімейна", hint: "10% — підтвердити родинний зв'язок" },
  { key: "referral", label: "Реферальний бонус", hint: "500 ₴, чек від 3 000 ₴" },
  { key: "second_course", label: "Другий курс", hint: "10% поверх абонемента" },
];

const STATUSES = [
  { value: "new", label: "Нове" },
  { value: "pending", label: "Очікує оплати" },
  { value: "partial", label: "Часткова оплата" },
  { value: "paid", label: "Оплачене" },
  { value: "cancelled", label: "Скасоване" },
  { value: "refunded", label: "Повернуто" },
];

const METHOD_LABEL = {
  card: "Картка",
  chast: "Покупка Частинами",   // назву не скорочувати: вимога monobank
  invoice: "Рахунок",
  manual: "Вручну",
};

function money(uah) {
  return `${Number(uah || 0).toLocaleString("uk-UA")} ₴`;
}

function fmt(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("uk-UA", {
    day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
  });
}

export default function OrdersPage() {
  const [items, setItems] = useState([]);
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminGetOrders({
        ...(status ? { status } : {}),
        ...(q.trim() ? { q: q.trim() } : {}),
      });
      setItems(data.items || []);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [status, q]);

  useEffect(() => { load(); }, [status]);   // пошук — по Enter, не на кожну літеру

  async function changeStatus(order, value) {
    setItems((list) =>
      list.map((o) => (o.public_id === order.public_id ? { ...o, status: value } : o))
    );
    try {
      await adminUpdateOrder(order.public_id, { status: value });
    } catch {
      load();
    }
  }

  async function addPayment(order) {
    const raw = window.prompt(
      `Сума оплати в гривнях для ${order.public_id}\n` +
      `До сплати: ${money(order.amount_uah - order.paid_amount / 100)}`,
      String(order.amount_uah - order.paid_amount / 100)
    );
    if (!raw) return;
    try {
      await adminManualPayment(order.public_id, {
        amount_uah: raw.replace(",", "."),
        note: "внесено з кабінету",
      });
      load();
    } catch {
      window.alert("Не вдалося зафіксувати оплату");
    }
  }

  /* Перемикач знижки. Кожен клік шле ПОВНИЙ перелік, а не дельту:
     бекенд рахує від base_amount і повністю перезаписує стан, тож
     «додати» й «зняти» — одна й та сама операція без окремих гілок. */
  async function toggleDiscount(order, key) {
    const current = order.discount_kinds || [];
    const next = current.includes(key)
      ? current.filter((k) => k !== key)
      : [...current, key];
    try {
      await adminSetDiscount(order.public_id, next);
      load();
    } catch (err) {
      window.alert(err?.response?.data?.detail || "Не вдалося змінити знижку");
    }
  }

  return (
    <>
      <header className="adm-head">
        <h1>Замовлення</h1>
        <form
          className="adm-search"
          onSubmit={(e) => { e.preventDefault(); load(); }}
        >
          <input
            placeholder="Номер, імʼя або телефон"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <button type="submit">Знайти</button>
        </form>
      </header>

      <div className="adm-tabs adm-tabs--wide">
        <button type="button" className={!status ? "is-on" : ""} onClick={() => setStatus("")}>
          Усі
        </button>
        {STATUSES.map((s) => (
          <button
            key={s.value}
            type="button"
            className={status === s.value ? "is-on" : ""}
            onClick={() => setStatus(s.value)}
          >
            {s.label}
          </button>
        ))}
      </div>

      {loading && <p className="adm-empty">Завантажуємо…</p>}
      {!loading && items.length === 0 && <p className="adm-empty">Замовлень немає</p>}

      <div className="adm-rows">
        {items.map((o) => (
          <article key={o.public_id} className={`adm-row st-${o.status}`}>
            <div
              className="adm-row__main"
              onClick={() => setOpen(open === o.public_id ? null : o.public_id)}
            >
              <div className="adm-row__who">
                <b>{o.customer_name}</b>
                <span className="adm-mono">{o.public_id}</span>
              </div>

              <div className="adm-row__meta">
                <span className="adm-tag">{o.package_name}</span>
                <span className="adm-date">{fmt(o.created_at)}</span>
              </div>

              <div className="adm-row__money">
                <b>{money(o.amount_uah)}</b>
                {o.paid_amount > 0 && o.paid_amount < o.amount && (
                  <span>сплачено {money(o.paid_amount / 100)}</span>
                )}
              </div>

              <select
                className="adm-select"
                value={o.status}
                onClick={(e) => e.stopPropagation()}
                onChange={(e) => changeStatus(o, e.target.value)}
              >
                {STATUSES.map((s) => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
            </div>

            {open === o.public_id && (
              <div className="adm-row__body">
                <dl>
                  {o.customer_phone && (
                    <><dt>Телефон</dt><dd><a href={`tel:${o.customer_phone}`}>{o.customer_phone}</a></dd></>
                  )}
                  {o.customer_email && (
                    <><dt>Email</dt><dd><a href={`mailto:${o.customer_email}`}>{o.customer_email}</a></dd></>
                  )}
                  {o.student_name && <><dt>Учень</dt><dd>{o.student_name}</dd></>}
                  {o.lessons_count && <><dt>Занять</dt><dd>{o.lessons_count}</dd></>}
                  <dt>Оплачено</dt><dd>{money(o.paid_amount / 100)} з {money(o.amount_uah)}</dd>
                </dl>

                {/* Історія спроб оплати. Саме тут видно, що людина спершу
                    спробувала Покупку Частинами, отримала відмову банку
                    й оплатила карткою — і що списання було одне. */}
                {o.payments?.length > 0 && (
                  <table className="adm-table">
                    <thead>
                      <tr><th>Спосіб</th><th>Стан</th><th>Сума</th><th>Частин</th><th>Причина відмови</th></tr>
                    </thead>
                    <tbody>
                      {o.payments.map((p) => (
                        <tr key={p.id}>
                          <td>{METHOD_LABEL[p.method] || p.method}</td>
                          <td>{p.status}</td>
                          <td>{money(p.amount_uah)}</td>
                          <td>{p.parts_count || "—"}</td>
                          <td className="adm-fail">{p.fail_code || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}

                {/* Знижки. Сімейну бекенд проставити не може — спорідненість
                    за даними замовлення не підтверджується, — тому вона
                    ставиться тут, руками, після перевірки. Реферальну
                    й «другий курс» система ставить сама, але зняти їх
                    теж треба вміти: помилки трапляються. */}
                <div className="adm-disc">
                  <p className="adm-disc__head">
                    Знижки
                    {o.discount_amount > 0 && (
                      <span className="adm-disc__sum">
                        −{money(o.discount_amount_uah)} від {money(o.base_amount_uah)}
                      </span>
                    )}
                  </p>

                  <div className="adm-disc__row">
                    {DISCOUNTS.map((d) => (
                      <button
                        key={d.key}
                        type="button"
                        title={d.hint}
                        disabled={o.status === "paid" || o.paid_amount > 0}
                        className={
                          "adm-disc__chip" +
                          (o.discount_kinds?.includes(d.key) ? " is-on" : "")
                        }
                        onClick={() => toggleDiscount(o, d.key)}
                      >
                        {d.label}
                      </button>
                    ))}
                  </div>

                  {(o.status === "paid" || o.paid_amount > 0) && (
                    <p className="adm-disc__lock">
                      За замовленням уже є гроші — суму не міняємо.
                      Потрібна компенсація — оформлюйте повернення різниці.
                    </p>
                  )}

                  {o.promo_code && (
                    <p className="adm-disc__promo">
                      Код при оформленні: <b>{o.promo_code}</b>
                    </p>
                  )}
                </div>

                <button type="button" className="adm-btn" onClick={() => addPayment(o)}>
                  Зафіксувати оплату вручну
                </button>
              </div>
            )}
          </article>
        ))}
      </div>
    </>
  );
}
