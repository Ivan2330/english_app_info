import { useEffect } from "react";

// Хелпер для викликів тільки після готовності Tidio
function onTidioReady(cb) {
  if (window.tidioChatApi) return cb();
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
        // Офіційний метод оновлення даних відвідувача
        window.tidioChatApi.setVisitorData({
          ...("distinct_id" in visitor ? { distinct_id: visitor.distinct_id } : {}),
          ...("name" in visitor ? { name: visitor.name } : {}),
          ...("email" in visitor ? { email: visitor.email } : {}),
          ...("phone" in visitor ? { phone: visitor.phone } : {}),
        });
      } catch (e) {
        // eslint-disable-next-line no-console
        console.error("Failed to set Tidio visitor data:", e);
      }
    });
  }, [visitor]);

  return null;
}
