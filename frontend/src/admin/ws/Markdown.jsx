import { useMemo } from "react";
import MarkdownIt from "markdown-it";
import DOMPurify from "dompurify";

/**
 * Безпечний markdown.
 *
 * Два рівні захисту:
 *  1) markdown-it з html:false — сирий HTML у тексті не виконується, а
 *     показується як текст; посилання javascript: / data: він відкидає сам;
 *  2) DOMPurify поверх результату — на випадок помилки в парсері.
 * Посилання відкриваються в новій вкладці й без доступу до window.opener.
 */
const md = new MarkdownIt({ html: false, linkify: true, breaks: true });

DOMPurify.addHook("afterSanitizeAttributes", (node) => {
  if (node.tagName === "A") {
    node.setAttribute("target", "_blank");
    node.setAttribute("rel", "noopener noreferrer nofollow");
  }
});

export function renderMarkdown(text) {
  return DOMPurify.sanitize(md.render(text || ""), { USE_PROFILES: { html: true } });
}

export default function Markdown({ text, empty = "Тексту поки немає." }) {
  const html = useMemo(() => renderMarkdown(text), [text]);
  if (!text || !text.trim()) return <p className="ws-muted">{empty}</p>;
  // eslint-disable-next-line react/no-danger -- вміст уже пройшов markdown-it (html:false) і DOMPurify
  return <div className="ws-md" dangerouslySetInnerHTML={{ __html: html }} />;
}
