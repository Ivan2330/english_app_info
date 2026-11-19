import { useEffect, useState } from "react";
import { getEconomy, setEconomy } from "../../api/workspace";
import { errorText } from "../../api/apiClientAuth";
import { ErrorBox, Field } from "../ws/ui";

const FIELDS = [
  ["cpl", "Ціна ліда (CPL), ₴", "0.01", 0, 1000000], ["show", "Дійшли до пробного, %", "0.01", 0, 100],
  ["trial_paid", "Оплатили після пробного, %", "0.01", 0, 100], ["price", "Ціна пакета, ₴", "0.01", 0, 10000000],
  ["lessons", "Уроків у пакеті", "1", 1, 1000], ["package_months", "Тривалість пакета, міс.", "0.01", 0.01, 48],
  ["individual_rate", "Ставка за індивідуальний урок, ₴", "0.01", 0, 100000], ["group_rate", "Ставка за груповий урок, ₴", "0.01", 0, 100000],
  ["group_size", "Учнів у групі, які оплатили", "1", 1, 100], ["card_share", "Частка карткових оплат, %", "0.01", 0, 100],
  ["card_fee", "Комісія з карткових оплат, %", "0.01", 0, 100], ["tax", "Податок із виручки, %", "0.01", 0, 100],
  ["renewal", "Подовжують пакет, %", "0.01", 0, 99],
];
const RESULTS = [
  ["cac", "Залучення клієнта (CAC)", "₴"], ["margin", "Маржа з пакета", "₴"], ["margin_percent", "Маржа, %", "%"],
  ["ltv", "Дохід за час навчання (LTV)", "₴"], ["ltv_contribution", "Маржа за час навчання", "₴"], ["payback_months", "Окупність", "міс."],
  ["teacher", "Витрати на викладача", "₴"], ["fee", "Комісія", "₴"], ["tax", "Податок", "₴"],
];
const formatNumber = new Intl.NumberFormat("uk-UA", { maximumFractionDigits: 2 });

export default function Economy() {
  const [input, setInput] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { getEconomy().then(({ inputs, results }) => { setInput(inputs); setResult(results); }).catch((e) => setError(errorText(e))); }, []);
  const update = (key) => (e) => { setInput((data) => ({ ...data, [key]: e.target.value })); setStatus("Зміни ще не застосовано"); };

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const data = Object.fromEntries(FIELDS.map(([key]) => [key, Number(input[key])]));
      const saved = await setEconomy({ ...data, format: input.format });
      setInput(saved.inputs); setResult(saved.results); setStatus("Розраховано й збережено");
    } catch (e) { setError(errorText(e)); }
    finally { setBusy(false); }
  }

  if (!input) return error ? <ErrorBox text={error} /> : <p className="ws-muted" role="status">Завантажуємо…</p>;
  return <div className="ws-stack">
    <form className="ws-card ws-stack" onSubmit={submit}>
      <Field label="Формат навчання"><select className="ws-input" aria-label="Формат навчання" value={input.format} onChange={update("format")}>
        <option value="individual">Індивідуальний</option><option value="group">Груповий</option>
      </select></Field>
      <div className="apps-fields">{FIELDS.map(([key, label, step, min, max]) => <Field key={key} label={label}>
        <input className="ws-input" type="number" inputMode="decimal" step={step} min={min} max={max} required value={input[key]} onChange={update(key)} />
      </Field>)}</div>
      <ErrorBox text={error} />
      <button className="ws-btn ws-btn--primary" disabled={busy}>{busy ? "Розраховуємо…" : "Розрахувати й зберегти"}</button>
      {status && <p className="ws-muted" role="status">{status}</p>}
    </form>
    <section className="ws-card ws-stack"><h2>Результати</h2>
      <dl className="apps-results">{RESULTS.map(([key, label, unit]) => <div key={key}>
        <dt>{label}</dt><dd>{result[key] == null ? "—" : `${formatNumber.format(result[key])} ${unit}`}</dd>
      </div>)}</dl>
      <p className="ws-muted ws-small">Комісія діє тільки на карткові оплати. Для груп вартість уроку ділиться між учнями, які оплатили. LTV припускає однакову частку подовжень після кожного пакета.</p>
    </section>
  </div>;
}
