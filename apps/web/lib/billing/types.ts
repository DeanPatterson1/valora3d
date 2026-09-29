/** Wire types shared by the billing API routes and the browser client. */

export type CheckoutResponse =
  | {
      kind: "checkout";
      priceId: string;
      /** Passed to Paddle.js verbatim; the webhook verifies user_sig before crediting user_id. */
      customData: { user_id: string; user_sig: string; /** First-touch attribution, compact JSON (unsigned, informational). */ src?: string };
      /** The Paddle customer for the account's own email, when the API key is configured. */
      customerId: string | null;
      customerEmail: string | null;
    }
  /** An existing subscription was moved to the chosen plan; credits follow by webhook. */
  | { kind: "changed" };

export type PortalResponse = { url: string };
