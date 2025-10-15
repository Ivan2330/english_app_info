import { useEffect } from "react";

/** Виклик callback лише після готовності Tidio */
function onTidioReady(cb) {
  if (typeof window !== "undefined" && window.tidioChatApi) return cb();
  document.addEventListener("tidioChat-ready", cb, { once: true });
}

/**
 * props.visitor: { distinct_id?: string, name?: string, email?: string, phone?: string } | null
 */
export default function TidioIdentify({ visitor }) {
  useEffect(() => {
    if (!visitor) return;

    onTidioReady(() => {
      try {
        if (!window?.tidioChatApi?.setVisitorData) return;

        const payload = {
          ...("distinct_id" in visitor ? { distinct_id: visitor.distinct_id } : {}),
          ...("name" in visitor ? { name: visitor.name } : {}),
          ...("email" in visitor ? { email: visitor.email } : {}),
          ...("phone" in visitor ? { phone: visitor.phone } : {}),
        };

        // Фільтр пустих/фальшивих значень
        Object.keys(payload).forEach((k) => {
          if (payload[k] == null || payload[k] === "" || String(payload[k]).includes("...")) {
            delete payload[k];
          }
        });

        if (Object.keys(payload).length) {
          window.tidioChatApi.setVisitorData(payload);
          // eslint-disable-next-line no-console
          console.log("[Tidio] visitor data sent");
        }
      } catch (e) {
        // eslint-disable-next-line no-console
        console.error("[Tidio] Failed to set visitor data:", e);
      }
    });
  }, [visitor]);

  return null;
}
