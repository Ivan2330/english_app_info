import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getHome } from "../api/workspace.js";
import { errorText } from "../api/apiClientAuth.js";
import { ErrorBox, fmtDate } from "./ws/ui.jsx";

/** Головна: що мені робити сьогодні і що нового від інших. */
export default function HomePage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => { getHome().then(setData).catch((e) => setError(errorText(e))); }, []);

  if (error) return <ErrorBox text={error} />;
  if (!data) return <p className="ws-muted">Завантажуємо…</p>;

  const hasTasks = "tasks_today" in data;
  const hasReports = "reports_to_review" in data;

  return (
    <div className="ws-stack ws-gap-l">
      <header className="ws-pagehead">
        <h1 className="ws-h1">Привіт, {data.name}!</h1>
        <p className="ws-muted">Сьогодні {fmtDate(data.today)}</p>
      </header>

      <div className="ws-grid">
        {hasTasks && (
          <Card title="Мої завдання на сьогодні" link="/admin/tasks?scope=mine" linkText="Усі мої завдання"
                empty="На сьогодні дедлайнів немає.">
            {data.tasks_today.map((t) => <TaskLine key={t.id} t={t} />)}
          </Card>
        )}
        {hasTasks && (
          <Card title="Прострочені" tone={data.tasks_overdue.length ? "danger" : ""}
                link="/admin/tasks?overdue=1" linkText="Відкрити список" empty="Нічого не прострочено. Так тримати!">
            {data.tasks_overdue.map((t) => <TaskLine key={t.id} t={t} />)}
          </Card>
        )}
        {hasTasks && data.tasks_to_accept.length > 0 && (
          <Card title="Чекають вашої перевірки" link="/admin/tasks?scope=created&status=review" linkText="Перевірити">
            {data.tasks_to_accept.map((t) => <TaskLine key={t.id} t={t} who={t.assignee} />)}
          </Card>
        )}
        <Card title={`Нові коментарі${data.new_comments_total ? ` · ${data.new_comments_total}` : ""}`}
              empty="Нових коментарів немає.">
          {data.new_comments.map((c, i) => (
            <Link key={i} className="ws-line" to={c.entity_type === "task" ? `/admin/tasks?open=${c.entity_id}` : `/admin/reports/${c.entity_id}`}>
              <b>{c.author}</b> у «{c.title}»
              <span>{c.body}</span>
            </Link>
          ))}
        </Card>
        {hasReports && (
          <Card title="Звіти, які ви ще не оцінили" link="/admin/reports" linkText="Усі звіти"
                empty="Усі нові звіти ви вже переглянули.">
            {data.reports_to_review.map((r) => (
              <Link key={r.id} className="ws-line" to={`/admin/reports/${r.id}`}>
                <b>{r.title}</b><span>{fmtDate(r.created_at)}</span>
              </Link>
            ))}
          </Card>
        )}
      </div>
    </div>
  );
}

function Card({ title, children, link, linkText, empty, tone = "" }) {
  const list = Array.isArray(children) ? children.filter(Boolean) : children ? [children] : [];
  return (
    <section className={`ws-card ws-home-card${tone ? ` is-${tone}` : ""}`}>
      <h2>{title}</h2>
      {list.length ? <div className="ws-lines">{list}</div> : <p className="ws-muted">{empty}</p>}
      {link && <Link className="ws-more" to={link}>{linkText} →</Link>}
    </section>
  );
}

function TaskLine({ t, who }) {
  return (
    <Link className="ws-line" to={`/admin/tasks?open=${t.id}`}>
      <b><span className={`ws-prio p-${t.priority}`}>{t.priority}</span> {t.title}</b>
      <span>{who ? `${who} · ` : ""}{t.status_label}{t.due_date ? ` · до ${fmtDate(t.due_date)}` : ""}</span>
    </Link>
  );
}
