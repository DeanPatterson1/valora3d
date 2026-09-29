/**
 * OWNER LAUNCH SWITCH. The legal pages still carry owner-pending placeholders ("[Owner to complete …]",
 * "[To be confirmed by owner]", "Draft — pending owner review"): legal name, address, governing law, DMCA
 * agent, retention periods, effective date. While this is true they may ship (the site is private).
 *
 * Flip to `false` once they are filled in: app/legal-placeholders.test.ts then fails, listing every
 * placeholder left, so none can reach a public launch.
 */
export const LEGAL_PLACEHOLDERS_ALLOWED = true;
