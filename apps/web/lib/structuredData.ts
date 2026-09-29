import { CREDIT_PACKS, PLANS } from "@/lib/pricing";
import { HOME_DESCRIPTION, OPERATOR_NAME, SITE_URL } from "@/lib/site";

const SUPPORT_EMAIL = "support@valora3d.com";

/**
 * Home-page structured data: who runs the site, the site itself, and the product with its offers. Prices are
 * read from PLANS and CREDIT_PACKS, so the markup cannot drift from the pricing cards. No ratings or reviews:
 * there are none yet, and invented ones are a search-quality violation.
 */
export function homeStructuredData(): object {
  const org = {
    "@type": "Organization",
    "@id": `${SITE_URL}/#organization`,
    name: "Valora3D",
    legalName: OPERATOR_NAME,
    url: SITE_URL,
    logo: `${SITE_URL}/icons/icon-512.png`,
    contactPoint: { "@type": "ContactPoint", contactType: "customer support", email: SUPPORT_EMAIL },
  };
  const site = {
    "@type": "WebSite",
    "@id": `${SITE_URL}/#website`,
    name: "Valora3D",
    url: SITE_URL,
    publisher: { "@id": `${SITE_URL}/#organization` },
  };
  const offers = [
    ...PLANS.map((p) => ({
      "@type": "Offer",
      name: `${p.name} plan`,
      price: p.priceUsd.toFixed(2),
      priceCurrency: "USD",
      url: `${SITE_URL}/pricing`,
      ...(p.period === "month"
        ? { priceSpecification: { "@type": "UnitPriceSpecification", price: p.priceUsd.toFixed(2), priceCurrency: "USD", billingDuration: "P1M", unitCode: "MON" } }
        : {}),
    })),
    ...CREDIT_PACKS.map((pack) => ({
      "@type": "Offer",
      name: `${pack.credits.toLocaleString("en-US")} credit pack`,
      price: pack.priceUsd.toFixed(2),
      priceCurrency: "USD",
      url: `${SITE_URL}/pricing`,
    })),
  ];
  const app = {
    "@type": "SoftwareApplication",
    "@id": `${SITE_URL}/#app`,
    name: "Valora3D",
    url: SITE_URL,
    description: HOME_DESCRIPTION,
    applicationCategory: "MultimediaApplication",
    operatingSystem: "Web",
    publisher: { "@id": `${SITE_URL}/#organization` },
    offers,
  };
  return { "@context": "https://schema.org", "@graph": [org, site, app] };
}
