import { useEffect, useRef, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import PageHero from "../components/PageHero.jsx";
import { getOrderState, payOrder } from "../api/orders.js";
import { money } from "../lib/labels.js";

/**
 * Куди людина повертається з банку.
 *
 * Ключова деталь: **сторінка сама опитує стан**, а не показує результат
 * одразу. Причина в Покупці Частинами — банк надсилає колбек лише на два
 * статуси із семи, і в момент повернення замовлення цілком може бути ще
 * в «обробці». Без опитування людина побачила б «не оплачено» одразу
 * після успішної оплати.
 *
 * Інтервал зростає: перші секунди питаємо часто, далі рідше, і через
 * дві хвилини зупиняємось — далі це вже робота координатора, а не сторінки.
 */

const POLL_STEPS_MS = [1500, 2000, 3000, 4000, 6000, 8000, 10000];
const MAX_POLLS = 24;   // приблизно дві хвилини

export default function PaymentResult() {
  const [params] = useSearchParams();
  const publicId = params.get("order") || sessionStorage.getItem("pa_last_order");

  const [state, setState] = useState(null);
  const [failed, setFailed] = useState(false);
  const [polling, setPolling] = useState(true);
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState("");
  const attempts = useRef(0);

  useEffect(() => {
    if (!publicId) { setPolling(false); return; }
    let timer;
    let cancelled = false;

    async function tick() {
      try {
        const data = await getOrderState(publicId);
        if (cancelled) return;
        setState(data);
        setFailed(false);

        const status = data?.order?.status;
        if (data?.payments?.length && data.payments.every(p => ["failed", "expired"].includes(p.status))) {
          setPolling(false);
          return;
        }
        if (["paid", "partial", "refunded", "cancelled"].includes(status)) {
          setPolling(false);
          sessionStorage.removeItem("pa_last_order");
          if (data?.order?.package_slug) sessionStorage.removeItem(`pa_checkout_key:${data.order.package_slug}`);
          return;
        }
      } catch {
        if (cancelled) return;
        setFailed(true);
      }

      attempts.current += 1;
      if (attempts.current >= MAX_POLLS) { setPolling(false); return; }

      const delay = POLL_STEPS_MS[Math.min(attempts.current, POLL_STEPS_MS.length - 1)];
      timer = setTimeout(tick, delay);
    }

    tick();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [publicId]);

  const order = state?.order;
  const paid = order?.status === "paid";
  const partial = order?.status === "partial";
  const refunded = order?.status === "refunded";
  const rejected = state?.payments?.length > 0 && state.payments.every(p => ["failed", "expired"].includes(p.status));

  async function retryCard() {
    if (retrying) return;
    setRetrying(true);
    setRetryError("");
    try {
      const result = await payOrder(publicId, { method: "card" });
      if (result.checkout_url) window.location.assign(result.checkout_url);
      else window.location.reload();
    } catch {
      setRetryError("Не вдалося перевірити оплату. Зверніться до координатора з номером замовлення.");
      setRetrying(false);
    }
  }

  return (
    <>
      <PageHero
        crumb="Оплата"
        title={paid ? "Оплата пройшла" : partial ? "Часткова оплата або повернення" : order?.status === "refunded" ? "Кошти повернуто" : "Перевіряємо оплату"}
      />

      <section className="sec sec--tight">
        <div className="container">
          {!publicId && (
            <p className="co-msg">
              Не бачимо, яке саме замовлення перевіряти.{" "}
              <Link to="/packages">Повернутись до пакетів</Link>.
            </p>
          )}

          {publicId && (paid || partial) && (
            <div className="pr pr--ok">
              <h2>{paid ? "Дякуємо, оплата отримана" : "Потрібне уточнення суми"}</h2>
              <p>
                Замовлення <b className="adm-mono">{order.public_id}</b> на пакет
                «{order.package_name}».
                {partial && " Звʼяжіться з координатором, щоб уточнити залишок після оплати або повернення."}
              </p>
              <dl className="pr__facts">
                <div><dt>Сума</dt><dd>{money(order.amount_uah)}</dd></div>
                <div><dt>Отримано</dt><dd>{money(order.paid_amount / 100)}</dd></div>
              </dl>
              <p className="pr__next">
                Координатор напише вам найближчим часом, щоб узгодити розклад
                і підібрати викладача. Якщо зручніше — напишіть самі, контакти
                на <Link to="/contacts">сторінці звʼязку</Link>.
              </p>
            </div>
          )}

          {publicId && !paid && !partial && polling && (
            <div className="pr">
              <h2>Чекаємо підтвердження від банку</h2>
              {state?.payments?.some(p => p.method === "chast" && ["processing", "waiting_for_store_confirm"].includes(p.status)) && (
                <p>Відкрийте застосунок monobank і підтвердьте заявку на Покупку Частинами.</p>
              )}
              <p>
                Це може зайняти до хвилини. Сторінку не закривайте — щойно банк
                відповість, тут зʼявиться результат.
              </p>
              <div className="pr__spin" aria-hidden="true"><i /><i /><i /></div>
            </div>
          )}

          {publicId && !paid && !partial && !polling && (
            <div className="pr pr--wait">
              <h2>{refunded ? "Кошти за замовлення повернуто" : rejected ? "Банк не підтвердив оплату" : "Підтвердження ще не надійшло"}</h2>
              <p>
                {refunded ? "Банк підтвердив повернення. Строк зарахування залежить від банку вашої картки."
                  : rejected ? "Попередню спробу завершено без успішної оплати. Можна оплатити всю суму карткою."
                  : "Гроші могли бути списані, а повідомлення від банку ще в дорозі. Нічого не оплачуйте повторно."}
              </p>
              {rejected && <button className="btn btn-primary" onClick={retryCard} disabled={retrying}>{retrying ? "Перевіряємо…" : "Оплатити всю суму карткою"}</button>}
              {retryError && <p role="alert">{retryError}</p>}
              <p className="pr__next">
                Напишіть нам номер замовлення{" "}
                <b className="adm-mono">{publicId}</b>, і ми перевіримо вручну
                протягом робочого дня. Контакти — на{" "}
                <Link to="/contacts">сторінці звʼязку</Link>.
              </p>
              {failed && (
                <p className="pr__fine">
                  Схоже, проблема зі звʼязком. Спробуйте оновити сторінку.
                </p>
              )}
            </div>
          )}
        </div>
      </section>
    </>
  );
}
