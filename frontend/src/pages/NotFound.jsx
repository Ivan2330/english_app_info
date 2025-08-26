import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <section>
      <h1>404</h1>
      <p>На жаль, сторінку не знайдено.</p>
      <Link to="/">Повернутись на головну</Link>
    </section>
  );
}
