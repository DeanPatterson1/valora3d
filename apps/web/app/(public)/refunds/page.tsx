import { SupportEmail, TrustPage } from "@/components/trust/TrustPage";
import { CREDIT_EXPIRY_RULES, RENDER_REFUND_RULES } from "@/lib/help";
import { publicMetadata } from "@/lib/site";

export const metadata = publicMetadata("Refunds and cancellation", "How to request help with Valora3D subscriptions, credits and Paddle payment refunds. Draft pending owner review.", "/refunds");

export default function RefundsPage() {
  return (
    <TrustPage title="Refunds and cancellation" intro="If a charge or render has gone wrong, contact us so we can investigate. Payment refunds are processed through Paddle.">
      <section><h2>Who handles payments</h2><p>Paddle is the merchant of record and seller of record for Valora3D purchases. Its <a href="https://www.paddle.com/legal/buyer-terms">buyer terms</a> and <a href="https://www.paddle.com/legal/refund-policy">refund policy</a> govern payment refunds, alongside your mandatory consumer rights. Nothing here limits rights that cannot be waived.</p></section>
      <section><h2>Request a refund</h2><p>Email <SupportEmail /> with the email used for purchase, your Paddle order or transaction reference, the charge date and a short description of the problem. Do not send full card details or passwords. You can also request payment support directly at <a href="https://paddle.net">Paddle’s buyer support site</a>.</p><p>We will review the order, usage and any delivery problem and coordinate with Paddle. Refund eligibility, withdrawal periods and exceptions depend on the purchase and applicable law; consuming digital services may affect withdrawal rights where you have given the required consent. This draft does not promise an additional money-back period.</p></section>
      <section><h2>Failed jobs and credits</h2><p>{RENDER_REFUND_RULES}</p><p>If a render fails or credits appear incorrect, send the project and job reference to support. We will check the usage record and correct verified errors. A credit correction is different from a cash refund. Do not repeatedly resubmit a failed paid job while support is investigating.</p><p>Used credits or completed processing do not automatically qualify for a discretionary refund, but that does not remove remedies for faulty, undelivered or misdescribed services under applicable law. Any additional goodwill refund window: [Owner to confirm before publication].</p></section>
      <section><h2>Unused and expired credits</h2><p>{CREDIT_EXPIRY_RULES} Expired plan credits are not refunded. A full refund or chargeback of a payment takes back the credits it granted, and, for a first payment made through an invite link, both referral bonuses.</p></section>
      <section><h2>Cancel a subscription</h2><p>Use the subscription-management link supplied with your Paddle purchase, or contact support for help before renewal. Cancellation stops future renewals; it does not itself refund earlier charges. Access continues for the paid period unless the order is refunded or access is suspended under the terms. Keep the cancellation confirmation.</p></section>
      <section><h2>Approved refunds</h2><p>Paddle returns approved refunds through the applicable payment method. Processing time depends on Paddle and the payment provider. Refunded purchases may have associated credits or access removed to avoid duplicate benefits. If you cannot find a refund or do not recognize a charge, contact Paddle and include the transaction reference.</p></section>
    </TrustPage>
  );
}
