import { useEffect, useState } from "react";
import { getCreativeReviews, saveCreativeReview } from "../../api/workspace";
import { errorText } from "../../api/apiClientAuth";
import { ErrorBox, Field } from "./ui";

const CRITERIA = { idea: "Ідея", design: "Дизайн", copy: "Текст", brand: "Відповідність бренду", advertising: "Рекламний потенціал" };

export default function CreativeReview({ id, onSaved }) {
  const [data, setData] = useState(null);
  const [scores, setScores] = useState({});
  const [comment, setComment] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    getCreativeReviews(id).then((result) => {
      setData(result);
      const mine = result.items.find((item) => item.mine);
      setScores(mine?.criteria || {});
      setComment(mine?.comment || "");
    }).catch((e) => setError(errorText(e)));
  }, [id]);

  async function save(event) {
    event.preventDefault();
    setBusy(true);
    setSaved(false);
    setError("");
    try { setData(await saveCreativeReview(id, { ...scores, comment })); setSaved(true); onSaved(); }
    catch (e) { setError(errorText(e)); }
    finally { setBusy(false); }
  }

  return <section className="ws-block ws-stack">
    <h3>Оцінки {data?.average != null && <span className="ws-score">{data.average}/5</span>}</h3>
    {data && <form onSubmit={save} className="ws-stack">
      <div className="ac-filters">{Object.entries(CRITERIA).map(([key, label]) => <Field key={key} label={label}>
        <select aria-label={label} className="ws-input" value={scores[key] || ""} required onChange={(e) => {
          setSaved(false);
          setScores((current) => ({ ...current, [key]: Number(e.target.value) }));
        }}><option value="">Оберіть бал</option>{[1, 2, 3, 4, 5].map((value) => <option key={value}>{value}</option>)}</select>
      </Field>)}</div>
      <Field label="Коментар"><textarea className="ws-input" maxLength={5000} rows={2} value={comment} onChange={(e) => {
        setSaved(false); setComment(e.target.value);
      }} /></Field>
      <button className="ws-btn ws-btn--primary" disabled={busy}>{saved ? "Збережено ✓" : "Зберегти оцінку"}</button>
    </form>}
    <ErrorBox text={error} />
    {data?.items.length === 0 && <p className="ws-muted">Оцінок поки немає.</p>}
    <ul className="ws-reviews">{data?.items.map((item) => <li key={item.id}>
      <strong>{item.author}</strong> <span className="ws-score">{item.average}/5</span>
      <div className="ws-row ws-wrap">{Object.entries(CRITERIA).map(([key, label]) => <span key={key} className="ws-small ws-muted">{label}: {item.criteria[key]}</span>)}</div>
      {item.comment && <p>{item.comment}</p>}
    </li>)}</ul>
  </section>;
}
