import { Link } from "react-router-dom";

/** Шапка внутрішньої сторінки: хлібні крихти, заголовок, лід і дії. */
export default function PageHero({ crumb, title, lead, children }) {
  return (
    <header className="phero">
      <div className="container">
        <nav className="crumbs" aria-label="Навігаційний ланцюжок">
          <Link to="/">Головна</Link>
          <span aria-hidden="true">/</span>
          {crumb}
        </nav>
        <h1 className="phero__title">{title}</h1>
        {lead ? <p className="phero__lead">{lead}</p> : null}
        {children ? <div className="phero__actions">{children}</div> : null}
      </div>
    </header>
  );
}
