/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_IDENTITY_PROVIDER?: string;
  readonly VITE_ENVIRONMENT?: string;
  readonly VITE_ENTRA_TENANT_ID?: string;
  readonly VITE_ENTRA_CLIENT_ID?: string;
  readonly VITE_ENTRA_REDIRECT_URI?: string;
  readonly VITE_API_SCOPE?: string;
  readonly VITE_API_WRITE_SCOPE?: string;
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_MARKETPLACE_REPO_URL?: string;
  readonly VITE_PILOT_MAILTO?: string;
  readonly VITE_HELP_URL?: string;
  readonly VITE_ENV_NAME?: string;
  readonly VITE_BUILD_ID?: string;
  readonly VITE_RD1_NAME_REVEAL_ROLES?: string;
  readonly VITE_RD2_ENGINEER_RUN_SCOPE?: string;
  readonly VITE_RD3_QUESTION_TEXT_IN_CLOUD?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
