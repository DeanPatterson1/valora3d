/**
 * Structured data, escaped once here: `<` becomes \u003c so no string in the data can close the script tag.
 * Pages pass plain objects and never hand-roll `dangerouslySetInnerHTML`.
 */
export function jsonLdString(data: object): string {
  return JSON.stringify(data).replace(/</g, "\\u003c");
}

export function JsonLd({ data }: { data: object }) {
  return <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLdString(data) }} />;
}
