// Uniquement pour l'affichage et l'orientation : l'accès réel est décidé par le backend.
const ADMIN_ROLES = ["super_admin", "support", "finance"];

export function isAdminRole(role: string | undefined): boolean {
  return role !== undefined && ADMIN_ROLES.includes(role);
}

/** Page d'arrivée après connexion selon le rôle. */
export function homePath(locale: string, role: string | undefined): string {
  return `/${locale}/${isAdminRole(role) ? "admin" : "dashboard"}`;
}
