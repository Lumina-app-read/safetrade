// Uniquement pour l'affichage et l'orientation : l'accès réel est décidé par le backend.
const ADMIN_ROLES = ["super_admin", "support", "finance"];

export function isAdminRole(role: string | undefined): boolean {
  return role !== undefined && ADMIN_ROLES.includes(role);
}

/**
 * Page d'arrivée après connexion : l'espace client pour tous, administrateurs compris.
 * L'administration s'ouvre ensuite par une seconde connexion (bouton réservé aux administrateurs).
 */
export function homePath(locale: string): string {
  return `/${locale}/dashboard`;
}
