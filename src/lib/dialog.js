// Un panneau modal : le focus y entre à l'ouverture, y reste (Tab tourne en rond), Échap le ferme,
// et à la fermeture le focus revient au bouton qui l'avait ouvert.
import { useEffect } from 'react';

const FOCUSABLE = 'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function useDialog(ref, open, onClose) {
  useEffect(() => {
    if (!open) return undefined;
    const box = ref.current;
    const opener = document.activeElement;
    const first = box.querySelector('[data-autofocus]') || box;
    first.focus({ preventScroll: true });
    const onKey = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
        return;
      }
      if (e.key !== 'Tab') return;
      const items = [...box.querySelectorAll(FOCUSABLE)].filter((el) => el.offsetParent !== null);
      if (!items.length) return;
      const head = items[0];
      const tail = items[items.length - 1];
      if (!box.contains(document.activeElement)) {
        e.preventDefault();
        head.focus();
      } else if (e.shiftKey && document.activeElement === head) {
        e.preventDefault();
        tail.focus();
      } else if (!e.shiftKey && document.activeElement === tail) {
        e.preventDefault();
        head.focus();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      if (opener && opener.isConnected) opener.focus?.({ preventScroll: true });
    };
  }, [ref, open, onClose]);
}
