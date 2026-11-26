// Un geste = un coup. La molette (crans de souris, balayages de trackpad et leur inertie), les
// balayages tactiles et le clavier deviennent step(±1) ou jump('first' | 'last').
// Tant que handlers.blocked() est vrai (un panneau est ouvert), rien n'est intercepté : le panneau
// défile normalement.
import { useEffect, useRef } from 'react';

export function useShotInput(handlers) {
  const h = useRef(handlers);
  h.current = handlers;

  useEffect(() => {
    // --- molette : un balayage de trackpad envoie une longue série d'événements qui s'éteint peu à peu.
    // Seul le début compte : après un coup, rien ne part tant que la série ne s'est pas arrêtée, ou
    // qu'elle ne reprend pas nettement (un nouveau balayage).
    let armed = true;
    let lastT = 0;
    let lastAbs = 0;
    let acc = 0;
    const canScroll = (el, dy) => {
      const box = el.closest?.('[data-scroll]');
      if (!box || box.scrollHeight <= box.clientHeight + 1) return false;
      return dy > 0 ? box.scrollTop + box.clientHeight < box.scrollHeight - 1 : box.scrollTop > 0;
    };
    const onWheel = (e) => {
      if (e.ctrlKey || h.current.blocked?.()) return; // zoom par pincement, ou panneau ouvert
      if (canScroll(e.target, e.deltaY)) return;
      e.preventDefault();
      if (Math.abs(e.deltaX) > Math.abs(e.deltaY) * 1.5) return; // geste horizontal : ce n'est pas un coup
      const d = e.deltaY;
      const abs = Math.abs(d) * (e.deltaMode === 1 ? 32 : 1);
      const now = performance.now();
      const gap = now - lastT;
      if (gap > 160 || (abs > lastAbs * 2.2 && abs > 40 && gap > 12)) {
        armed = true;
        acc = 0;
      }
      lastT = now;
      lastAbs = abs;
      if (!armed) return;
      acc += abs;
      if (acc < 24) return; // un effleurement du pavé ne compte pas
      armed = false;
      acc = 0;
      h.current.step?.(d > 0 ? 1 : -1);
    };

    // --- tactile : un balayage vertical d'au moins 44 px
    let start = null;
    const onTouchStart = (e) => {
      const t = e.touches[0];
      const scrolls = e.target.closest?.('[data-scroll]') && (canScroll(e.target, 1) || canScroll(e.target, -1));
      start = h.current.blocked?.() || scrolls || e.touches.length > 1 ? null : { x: t.clientX, y: t.clientY };
    };
    const onTouchEnd = (e) => {
      if (!start) return;
      const t = e.changedTouches[0];
      const dx = start.x - t.clientX;
      const dy = start.y - t.clientY;
      start = null;
      if (Math.abs(dy) < 44 || Math.abs(dy) < Math.abs(dx)) return;
      h.current.step?.(dy > 0 ? 1 : -1);
    };

    // --- clavier
    const onKey = (e) => {
      if (e.metaKey || e.ctrlKey || e.altKey || h.current.blocked?.() || e.target.closest?.('input, textarea, select')) return;
      const k = e.key;
      const onControl = e.target.closest?.('button, a');
      if (k === 'ArrowDown' || k === 'ArrowRight' || k === 'PageDown' || (k === ' ' && !onControl && !e.shiftKey)) h.current.step?.(1);
      else if (k === 'ArrowUp' || k === 'ArrowLeft' || k === 'PageUp' || (k === ' ' && !onControl && e.shiftKey)) h.current.step?.(-1);
      else if (k === 'Home') h.current.jump?.('first');
      else if (k === 'End') h.current.jump?.('last');
      else return;
      e.preventDefault();
    };

    window.addEventListener('wheel', onWheel, { passive: false });
    window.addEventListener('touchstart', onTouchStart, { passive: true });
    window.addEventListener('touchend', onTouchEnd, { passive: true });
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('wheel', onWheel);
      window.removeEventListener('touchstart', onTouchStart);
      window.removeEventListener('touchend', onTouchEnd);
      window.removeEventListener('keydown', onKey);
    };
  }, []);
}
