"use client";

import { X } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";

/**
 * Fenêtre native (`dialog`) : focus piégé et touche Échap gérés par le navigateur.
 * Téléphone : panneau accroché en bas, à portée de pouce. Ordinateur : fenêtre centrée.
 */
export function Dialog({
  open,
  onClose,
  title,
  closeLabel,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  closeLabel: string;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const element = ref.current;
    if (open && element && !element.open) element.showModal();
    if (!open && element?.open) element.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-label={title}
      className="m-0 mt-auto max-h-[92dvh] w-full max-w-none rounded-t-2xl border border-line bg-card text-fg shadow-card backdrop:bg-anthracite/60 sm:m-auto sm:max-w-xl sm:rounded-xl"
    >
      <div className="sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-line bg-card px-5 py-3 sm:px-6">
        <h2 className="text-h3 font-medium">{title}</h2>
        <button
          type="button"
          onClick={onClose}
          aria-label={closeLabel}
          className="grid size-11 place-items-center rounded-lg text-muted hover:text-fg"
        >
          <X size={20} strokeWidth={1.5} aria-hidden />
        </button>
      </div>
      <div className="px-5 py-5 pb-[calc(20px+env(safe-area-inset-bottom))] sm:px-6">{open && children}</div>
    </dialog>
  );
}
