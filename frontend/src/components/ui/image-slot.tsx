import { existsSync } from "node:fs";
import { join } from "node:path";

import Image from "next/image";
import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

/**
 * Emplacements d'images remplaçables par le propriétaire (voir public/images/README.md).
 * Il suffit de déposer public/images/<nom>.<extension> ; extensions acceptées ci-dessous.
 */
export const IMAGE_SLOTS = {
  hero: { width: 1600, height: 1000 },
  platform: { width: 1600, height: 1000 },
  security: { width: 1200, height: 900 },
} as const;

export type ImageSlotName = keyof typeof IMAGE_SLOTS;

const EXTENSIONS = ["webp", "png", "jpg", "jpeg", "svg"] as const;
const IMAGES_DIR = join(process.cwd(), "public", "images");

/** Chemin public du fichier déposé pour cet emplacement, ou null s'il n'existe pas encore. */
export function findSlotImage(name: ImageSlotName): string | null {
  const ext = EXTENSIONS.find((e) => existsSync(join(IMAGES_DIR, `${name}.${e}`)));
  return ext ? `/images/${name}.${ext}` : null;
}

/**
 * Affiche l'image de l'emplacement si elle a été déposée, sinon le repli fourni
 * (composition CSS ou d'interface). Rendu côté serveur : une image ajoutée est prise
 * en compte au build suivant.
 */
export function ImageSlot({
  name,
  alt,
  fallback,
  className,
  priority = false,
}: {
  name: ImageSlotName;
  alt: string;
  fallback: ReactNode;
  className?: string;
  priority?: boolean;
}) {
  const src = findSlotImage(name);
  if (!src) return <>{fallback}</>;
  const { width, height } = IMAGE_SLOTS[name];
  return (
    <Image
      src={src}
      alt={alt}
      width={width}
      height={height}
      priority={priority}
      // Le SVG n'est pas optimisable par Next.js ; il est servi tel quel.
      unoptimized={src.endsWith(".svg")}
      sizes="(min-width: 1024px) 50vw, 100vw"
      className={cn("h-auto w-full rounded-2xl object-cover", className)}
    />
  );
}
