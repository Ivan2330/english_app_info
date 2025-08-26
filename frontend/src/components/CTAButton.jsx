export default function CTAButton({ label = "Пробний урок", onClick }) {
  return (
    <button onClick={onClick}>{label}</button>
  );
}
