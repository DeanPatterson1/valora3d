import { attributionFromCheckout, type Attribution } from "@/lib/analytics/attribution";

/**
 * The attribution a checkout sent along in Paddle custom data (`custom_data.src`, set by the checkout route; unsigned
 * and informational, so it is re-validated here and never trusted for anything but reporting). Only read from a body
 * whose signature has already been verified.
 */
export function transactionSourceFromBody(rawBody: string): Attribution | null {
  try {
    const event = JSON.parse(rawBody) as { data?: { custom_data?: { src?: unknown } | null } };
    return attributionFromCheckout(event?.data?.custom_data?.src);
  } catch {
    return null;
  }
}
