import type { HTMLAttributes, TdHTMLAttributes, ThHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export function Table({ className, ...rest }: HTMLAttributes<HTMLTableElement>) {
  return (
    <div className="-mx-3 overflow-x-auto">
      <table {...rest} className={cn("w-full border-collapse", className)} />
    </div>
  );
}

export function Th({ numeric, className, ...rest }: ThHTMLAttributes<HTMLTableCellElement> & { numeric?: boolean }) {
  return (
    <th
      {...rest}
      className={cn(
        "border-b border-line px-3 pb-3 text-left text-small font-medium tracking-[0.06em] whitespace-nowrap text-muted uppercase",
        numeric && "text-right",
        className,
      )}
    />
  );
}

export function Td({ numeric, className, ...rest }: TdHTMLAttributes<HTMLTableCellElement> & { numeric?: boolean }) {
  return (
    <td
      {...rest}
      className={cn(
        "border-b border-line px-3 py-3.5 whitespace-nowrap [tr:last-child_&]:border-b-0",
        numeric && "text-right tabular-nums",
        className,
      )}
    />
  );
}
