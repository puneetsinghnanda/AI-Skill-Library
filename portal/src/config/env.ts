/**
 * Build-time configuration from `import.meta.env` (SDD-09 §3.2, §10; DEV-01). Nothing here is a
 * secret: the SPA holds no secret. `.env.example` lists every variable.
 */
const raw = import.meta.env;

function str(v: string | undefined, fallback: string): string {
  return v !== undefined && v.trim() !== '' ? v.trim() : fallback;
}

const repoUrl = str(
  raw.VITE_MARKETPLACE_REPO_URL,
  'https://github.com/[TRUMINDS-ORG]/truminds-skill-library',
).replace(/\/+$/, '');

export const env = {
  tenantId: str(raw.VITE_ENTRA_TENANT_ID, ''),
  clientId: str(raw.VITE_ENTRA_CLIENT_ID, ''),
  redirectUri: str(raw.VITE_ENTRA_REDIRECT_URI, ''),
  apiScope: str(raw.VITE_API_SCOPE, 'api://truminds-insights/Portal.Read'),
  apiBaseUrl: str(raw.VITE_API_BASE_URL, ''),
  marketplaceRepoUrl: repoUrl,
  /** `org/repo`, used in commands such as `/plugin marketplace add <org>/<repo>` (OQ-10). */
  marketplaceRepoSlug: repoUrl.replace(/^https?:\/\/[^/]+\//, ''),
  pilotMailto: str(raw.VITE_PILOT_MAILTO, ''),
  helpUrl: str(raw.VITE_HELP_URL, ''),
  envName: str(raw.VITE_ENV_NAME, raw.MODE),
  buildId: str(raw.VITE_BUILD_ID, 'local'),
} as const;

export type Env = typeof env;

/** `mailto:` link for "Request a pilot" (SDD-10 §6.4). Null when no inbox is configured (SDD-10 O-06). */
export function pilotHref(subject: string): string | null {
  if (!env.pilotMailto) return null;
  return `mailto:${env.pilotMailto}?subject=${encodeURIComponent(subject)}`;
}
