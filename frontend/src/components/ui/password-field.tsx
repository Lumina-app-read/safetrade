"use client";

import { Eye, EyeOff, LockKeyhole } from "lucide-react";
import { useState, type ComponentProps } from "react";

import { Field } from "./field";

type Props = Omit<ComponentProps<typeof Field>, "type" | "end"> & {
  showLabel: string;
  hideLabel: string;
};

export function PasswordField({ showLabel, hideLabel, ...rest }: Props) {
  const [visible, setVisible] = useState(false);
  const Icon = visible ? EyeOff : Eye;
  return (
    <Field
      icon={LockKeyhole}
      {...rest}
      type={visible ? "text" : "password"}
      end={
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? hideLabel : showLabel}
          aria-pressed={visible}
          className="grid size-12 shrink-0 place-items-center rounded-lg text-muted hover:text-fg"
        >
          <Icon size={20} strokeWidth={1.5} aria-hidden />
        </button>
      }
    />
  );
}
