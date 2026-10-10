/**
 * Живий градієнтний фон із макета.
 *
 * Чотири розмиті плями повільно рухаються за різними траєкторіями, зверху —
 * ледь помітне зерно, щоб градієнт не виглядав «пластиковим».
 *
 * Рендериться один раз на весь застосунок і лежить під контентом (z-index -2/-1),
 * тому не заважає кліками — pointer-events вимкнено в CSS.
 */
export default function AuroraBackground() {
  return (
    <>
      <div className="aurora" aria-hidden="true">
        <span className="aurora__blob aurora__blob--1" />
        <span className="aurora__blob aurora__blob--2" />
        <span className="aurora__blob aurora__blob--3" />
        <span className="aurora__blob aurora__blob--4" />
      </div>
      <div className="aurora__grain" aria-hidden="true" />
    </>
  );
}
