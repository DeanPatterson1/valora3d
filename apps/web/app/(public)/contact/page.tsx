import Link from "next/link";
import { LegalEmail, PostalAddressNotice, SupportEmail, TrustPage } from "@/components/trust/TrustPage";
import { publicMetadata } from "@/lib/site";

export const metadata = publicMetadata("Contact", "Contact Valora3D support for account, rendering, billing, privacy and copyright questions.", "/contact");

export default function ContactPage() {
  return (
    <TrustPage title="Contact" intro="Valora3D is a solo-operated service. Email is the best way to reach the person responsible for product support.">
      <section><h2>Product and account support</h2><p>Email <SupportEmail />. Include your account email, the relevant project or job reference, what you expected and what happened. Screenshots and error messages help; remove private information first. Never send passwords, full payment details or a model you are not allowed to share.</p><p>Support is answered by one person, usually within 2 business days (US Central time). There is no guaranteed 24-hour desk or response-time commitment. Valora3D is operated by Dean Patterson, an individual in Texas, United States. <PostalAddressNotice /></p></section>
      <section><h2>Billing and refunds</h2><p>Paddle is our merchant of record and seller of record. For charges, receipts and payment refunds, use <a href="https://paddle.net">Paddle buyer support</a> or email <a href="mailto:billing@valora3d.com">billing@valora3d.com</a> with your order reference. See our <Link href="/refunds">refunds and cancellation draft</Link>.</p></section>
      <section><h2>Privacy and deletion</h2><p>Send access, correction or deletion requests from your account email to <SupportEmail /> with the subject “Privacy request”. We may need to verify account ownership. See the <Link href="/privacy">privacy notice</Link> for data uses and providers.</p></section>
      <section><h2>Abuse, copyright and security</h2><p>Use the subject “Abuse report”, “Copyright takedown” or “Security report” and include the affected URL or project reference. Copyright notices go to <LegalEmail />; for DMCA notice requirements, see <Link href="/acceptable-use">acceptable use</Link>. For security issues, email <a href="mailto:security@valora3d.com">security@valora3d.com</a> and describe the issue without accessing other people’s data or disrupting the service; we will coordinate a private investigation.</p></section>
    </TrustPage>
  );
}
