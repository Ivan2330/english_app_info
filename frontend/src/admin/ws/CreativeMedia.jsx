import { useState } from "react";
import { API_URL } from "../../config";
import { orderCreativeMedia, saveCreativeMedia } from "../../api/workspace";
import { errorText } from "../../api/apiClientAuth";
import { ErrorBox, fmtDate, fmtSize } from "./ui";

const accept = ".jpg,.jpeg,.png,.webp,.mp4,.mov";
export const mediaUrl = (path) => `${API_URL}${path}`;
export const fileSpecs = (file) => [file.format.toUpperCase(), file.width && file.height ? `${file.width} × ${file.height}` : null, fmtSize(file.size)].filter(Boolean).join(" · ");

async function videoMetadata(file) {
  if (!/\.(mp4|mov)$/i.test(file.name)) return {};
  const url = URL.createObjectURL(file);
  const video = document.createElement("video");
  video.muted = true;
  video.preload = "auto";
  try {
    return await new Promise((resolve) => {
      const done = (data) => { clearTimeout(timer); resolve(data); };
      const timer = setTimeout(() => done({ width: video.videoWidth, height: video.videoHeight }), 1800);
      video.onerror = () => done({});
      video.onloadeddata = () => {
        const width = video.videoWidth;
        const height = video.videoHeight;
        if (!width || !height) { done({}); return; }
        const scale = Math.min(1, 640 / Math.max(width, height));
        const canvas = document.createElement("canvas");
        canvas.width = Math.max(1, Math.round(width * scale));
        canvas.height = Math.max(1, Math.round(height * scale));
        canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
        canvas.toBlob((poster) => done({ width, height, poster }), "image/jpeg", 0.8);
      };
      video.src = url;
    });
  } finally {
    video.removeAttribute("src");
    video.load();
    URL.revokeObjectURL(url);
  }
}

export function MediaTile({ file, controls = false }) {
  if (!file) return <span className="ac-placeholder">Немає медіа</span>;
  if (file.kind === "video" && controls) return <video controls playsInline preload="metadata"
    src={mediaUrl(file.url)} poster={file.thumbnail ? mediaUrl(file.thumbnail) : undefined} />;
  const image = controls ? file.url : file.thumbnail || (file.kind === "image" && file.url);
  return image ? <img src={mediaUrl(image)} alt={controls ? file.name : ""} loading={controls ? "eager" : "lazy"} />
    : <span className="ac-placeholder">▶ {file.format.toUpperCase()}</span>;
}

export default function CreativeMedia({ creative, refresh, maxMb }) {
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(null);
  const [dragging, setDragging] = useState(null);
  const [error, setError] = useState("");
  const slots = creative.media;

  async function upload(event, mediaId) {
    const files = Array.from(event.target.files);
    event.target.value = "";
    if (!files.length) return;
    setBusy(true);
    setError("");
    try {
      for (const file of files) {
        if (maxMb && file.size > maxMb * 1024 * 1024) throw new Error(`«${file.name}» перевищує ${maxMb} МБ`);
        setProgress(0);
        await saveCreativeMedia(creative.id, mediaId, file, await videoMetadata(file), setProgress);
      }
    } catch (e) { setError(e.response ? errorText(e) : e.message); }
    finally { setBusy(false); setProgress(null); refresh(); }
  }

  async function move(fromId, toId) {
    if (busy || fromId === toId) return;
    const ids = slots.map((item) => item.id);
    const from = ids.indexOf(fromId);
    const to = ids.indexOf(toId);
    if (from < 0 || to < 0) return;
    ids.splice(to, 0, ids.splice(from, 1)[0]);
    setBusy(true);
    setError("");
    try { await orderCreativeMedia(creative.id, ids); await refresh(); }
    catch (e) { setError(errorText(e)); }
    finally { setBusy(false); }
  }

  return <section className="ws-block ws-stack">
    <h3>Файли креативу</h3>
    <p className="ws-muted ws-small">JPG, PNG, WebP, MP4, MOV{maxMb ? ` · до ${maxMb} МБ на файл` : ""}</p>
    <label className="ws-row ws-wrap">Додати файли <input type="file" accept={accept} multiple disabled={busy} onChange={upload} /></label>
    {progress != null && <progress value={progress} max={100} aria-label="Завантаження файлу" />}
    <ErrorBox text={error} />
    {slots.length === 0 && <p className="ws-muted">У папці ще немає файлів.</p>}
    <ol className="ac-slides">
      {slots.map((slot, index) => <li key={slot.id} draggable={!busy} onDragStart={(e) => {
        setDragging(slot.id);
        e.dataTransfer.setData("text/plain", String(slot.id));
      }} onDragEnd={() => setDragging(null)} onDragOver={(e) => { if (dragging != null) e.preventDefault(); }}
        onDrop={(e) => { e.preventDefault(); move(dragging, slot.id); setDragging(null); }}>
        <div className="ac-slide-tile"><MediaTile file={slot.current} /></div>
        <div className="ws-stack">
          <strong>{slot.current.name}</strong>
          <span className="ws-muted ws-small">{fileSpecs(slot.current)} · версія {slot.current.version}</span>
          <div className="ws-row ws-wrap">
            <button className="ws-btn" type="button" aria-label={`Перемістити слайд ${index + 1} вгору`} disabled={busy || !index}
              onClick={() => move(slot.id, slots[index - 1].id)}>↑</button>
            <button className="ws-btn" type="button" aria-label={`Перемістити слайд ${index + 1} вниз`} disabled={busy || index === slots.length - 1}
              onClick={() => move(slot.id, slots[index + 1].id)}>↓</button>
            <label className="ac-file-button ws-btn">Замінити файл
              <input type="file" aria-label={`Замінити файл ${slot.current.name}`} accept={accept} disabled={busy} onChange={(e) => upload(e, slot.id)} />
            </label>
          </div>
          <details><summary>Історія версій ({slot.versions.length})</summary>
            <ul>{slot.versions.map((file) => <li key={file.id}>
              <a href={mediaUrl(`${file.url}?download=true`)}>Версія {file.version} · {file.name}</a>
              <span className="ws-muted ws-small"> · {fmtDate(file.created_at, true)}</span>
            </li>)}</ul>
          </details>
        </div>
      </li>)}
    </ol>
  </section>;
}
