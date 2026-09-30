/**
 * OWNER LAUNCH SWITCH. The legal pages still carry a few owner-pending placeholders (the bracketed
 * "[Owner to ...]" / "[To be confirmed ...]" tokens and "Draft — pending owner review"). While this is true they
 * may ship (the site is private).
 *
 * Remaining before public launch (2026-09-29; everything else on the pages is filled in):
 *   TODO(owner): a virtual-mailbox postal address (PostalAddressNotice in components/trust/TrustPage.tsx).
 *   TODO(owner): register the DMCA designated agent (Dean Patterson) with the US Copyright Office, dmca.copyright.gov, $6.
 *   TODO(owner): confirm retention of support email and hosting-provider server logs (privacy page).
 *   TODO(owner): confirm Supabase / R2 regions and transfer safeguards (privacy page).
 *   TODO(owner): effective date ("Effective date" in TrustPage.tsx has no automatic mechanism), then drop the draft banner.
 *
 * Flip to `false` once they are filled in: app/legal-placeholders.test.ts then fails, listing every
 * placeholder left, so none can reach a public launch.
 */
export const LEGAL_PLACEHOLDERS_ALLOWED = true;
