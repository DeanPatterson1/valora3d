import { CREDIT_COSTS, FREE_PLAN_CREDITS, MAX_UPLOAD_BYTES, PLAN_LIMITS, REFERRAL_BONUS_CREDITS, REFERRAL_MONTHLY_CAP, creditValue, type PlanId } from "./pricing";
import { WORLDS } from "./render/worlds";
import { INPUT_FAILURE_FEE } from "./render/failurePolicy";
import { INPUT_FAILURE_DAILY_CAP } from "./usageLimits";

/**
 * The render-credit refund rules in plain words. They follow lib/render/failurePolicy.ts (the one table the
 * pipeline and the SQL fee use); help.test.ts pins the numbers.
 */
export const RENDER_REFUND_RULES = `Credits are refunded automatically when a render fails on our side, or when you cancel it before the GPU starts. If the model or scene itself makes the render fail (a file the renderer can't read, or a scene too heavy to finish in time), ${INPUT_FAILURE_FEE} credits are kept and the rest is refunded. A render canceled after it started rendering isn't refunded.`;

/** How long each kind of credit lasts, in plain words (the rule is PLAN_CREDIT_ROLLOVER_PERIODS in lib/pricing.ts). */
export const CREDIT_EXPIRY_RULES = `Monthly plan credits roll over for one month: credits from a billing period that are still unused when the next period ends expire. When you spend, the plan credits that expire soonest are used first, before any pack credits. Credit packs, the Free plan credits and referral bonuses never expire.`;

export type HelpSection = {
  id: string;
  title: string;
  paragraphs: string[];
  steps?: string[];
  links?: { label: string; href: string }[];
};
export type HelpArticle = { slug: string; title: string; summary: string; sections: HelpSection[] };
const maxMB = MAX_UPLOAD_BYTES / 1024 / 1024;
const planNames: Record<PlanId, string> = { free: "Free", creator: "Creator", pro: "Pro" };
const planSummary = (id: PlanId) => {
  const p = PLAN_LIMITS[id];
  return `${planNames[id]}: ${p.tiers.includes("final") ? "540p previews and 1080p finals" : "540p previews only"}, ${p.watermark ? "with a watermark" : "no watermark"}, ${p.maxActiveJobs} ${p.maxActiveJobs === 1 ? "render at a time" : "renders at once"}, ${p.retentionDays}-day retention.`;
};

export const HELP_ARTICLES: HelpArticle[] = [
  {
    slug: "getting-started", title: "Getting started", summary: "From your first model to a finished shot.",
    sections: [
      { id: "first-shot", title: "Make your first shot", paragraphs: ["Valora3D turns a 3D model and a written shot description into a video. Renders run on cloud GPUs."], steps: [
        "Create an account, then open a new project.",
        `Upload one self-contained .glb (binary glTF) file, up to ${maxMB} MB. You can also try a sample model. Other upload formats are not accepted yet.`,
        "Describe the subject, mood, camera move and lighting in plain English.",
        "Pick a world and choose landscape 16:9 or portrait 9:16. Start with Preview to check the shot.",
        "Review the result, adjust what needs changing, then use Final when your plan supports it. Download the finished video to keep a copy.",
      ], links: [{ label: "Prepare your model", href: "/help/preparing-your-model" }, { label: "Write a shot prompt", href: "/help/writing-a-good-shot-prompt" }] },
      { id: "before-rendering", title: "Before you render", paragraphs: [`Preview is 540p and costs ${CREDIT_COSTS.preview_render} credits. Final is 1080p and costs ${CREDIT_COSTS.final_render} credits. Renders that fail on our side are refunded automatically; a failure caused by the model keeps a ${INPUT_FAILURE_FEE}-credit fee.`, "You own your renders. You must own or license the model you upload, including any textures. Check its license before using it commercially."], links: [{ label: "Acceptable use", href: "/acceptable-use" }, { label: "Credits, plans and refunds", href: "/help/credits-plans-and-refunds" }] },
    ],
  },
  {
    slug: "preparing-your-model", title: "Preparing your model", summary: "Export a self-contained .glb with textures, ready to upload.",
    sections: [
      { id: "requirements", title: "One file, everything inside", paragraphs: [`Upload one .glb (binary glTF), up to ${maxMB} MB. Include the geometry and image textures in that file. A .blend, .fbx, .obj, .gltf or ZIP file cannot be uploaded directly. Renaming the extension does not convert a model.`] },
      { id: "blender", title: "Export from Blender", paragraphs: ["Work on a copy of your model. Check its size and orientation before exporting."], steps: [
        "Select your model in Object Mode. Use Object > Apply > Rotation & Scale to apply transforms after checking that it faces the right way.",
        'Choose File > Export > glTF 2.0. Set Format to "glTF Binary (.glb)".',
        "Include only the objects you need. Use image textures with glTF-compatible materials; bake procedural textures first. The binary export embeds supported image textures in the .glb.",
        `Export, then import the .glb into a fresh Blender scene to check the result. Keep the file under ${maxMB} MB.`,
      ], links: [{ label: "Blender glTF export manual", href: "https://docs.blender.org/manual/en/3.6/addons/import_export/scene_gltf2.html" }] },
      { id: "sketchfab", title: "Models from Sketchfab", paragraphs: ["Check the model's license before downloading: a free download does not always permit commercial use. Keep the attribution and license details where required.", "If the download includes a self-contained .glb, inspect it before uploading. If it contains a .gltf with separate textures or another format, import a supported version into Blender with its textures and export a .glb."] },
      { id: "other-apps", title: "SketchUp, 3ds Max, Maya and Cinema 4D", paragraphs: ["Use a glTF exporter available for your application and version, and choose binary .glb with embedded textures. Some versions need an exporter plug-in.", "If your exporter cannot produce .glb, export a format Blender can import, bring the model and textures into Blender, then follow the steps above. Check materials after conversion; they may need rebuilding."] },
      { id: "smaller-files", title: "Reduce file size", paragraphs: ["Remove unused objects and hidden geometry. On a copy, try Blender's Decimate modifier and resize large textures, checking that the silhouette and surface detail still look right.", "For a command-line workflow, glTF Transform provides simplify and resize tools. Keep the original and inspect the output before uploading. Avoid adding compression extensions unless you have checked that the resulting file imports correctly."], links: [{ label: "glTF Transform CLI guide", href: "https://gltf-transform.dev/cli" }, { label: "Fix missing textures or upload errors", href: "/help/troubleshooting" }] },
    ],
  },
  {
    slug: "writing-a-good-shot-prompt", title: "Writing a good shot prompt", summary: "Describe the subject, mood, camera and light in a few clear sentences.",
    sections: [
      { id: "structure", title: "Give the shot a clear direction", paragraphs: ["Start with what the viewer should notice. Name the subject, mood, camera move, lighting and time of day. Choose a world that suits the description.", "Keep the camera direction simple: a slow orbit, a gentle push-in or a low side view. Conflicting moves and lighting requests make the shot harder to interpret. The prompt guides the result; it is not a guarantee of an exact frame." ] },
      { id: "examples", title: "Try these prompts", paragraphs: [
        'Studio: "A clean product shot of the watch. Slow orbit around the face, soft side lighting, calm mood, the dial clearly visible."',
        'Rain courtyard: "The car on damp asphalt under an overcast daytime sky. A slow, low push-in toward the front, soft reflections, quiet cinematic mood."',
        'Golden field: "Show the model in warm late-afternoon light. A gentle side orbit, long soft shadows, relaxed mood. Keep the whole subject in frame."',
      ] },
      { id: "iterate", title: "Change one thing at a time", paragraphs: ["Use a Preview to check composition before spending credits on a Final. If the subject is hard to see, ask for softer, brighter light or switch to Studio. If the framing feels busy, simplify the camera move.", "Describe visible changes rather than only saying ‘make it better’. For example: ‘Move closer to the front and keep the camera at headlight height.’"], links: [{ label: "Worlds and quality tiers", href: "/help/worlds-formats-and-quality" }] },
    ],
  },
  {
    slug: "worlds-formats-and-quality", title: "Worlds, formats and quality tiers", summary: "Choose the setting, aspect ratio and output quality for your shot.",
    sections: [
      { id: "worlds", title: "Choose a world", paragraphs: WORLDS.map((world) => `${world.label}: ${world.blurb}`) },
      { id: "formats", title: "Landscape or portrait", paragraphs: ["Choose 16:9 for landscape or 9:16 for portrait. Check the framing in your chosen format; a shot composed for landscape may crop the subject in portrait.", "Optional shot settings include a length of 8, 10 or 12 seconds, paint color and finish, and a seed. A seed helps keep comparisons controlled; it does not promise identical results after other settings change."] },
      { id: "quality", title: "Preview and Final", paragraphs: [`Preview: 540p, ${CREDIT_COSTS.preview_render} credits. Use it to check the shot.`, `Final: 1080p, ${CREDIT_COSTS.final_render} credits. Available on Creator and Pro.`, "Both tiers render on cloud GPUs. Completion time varies with the scene and available capacity."], links: [{ label: "Check plan limits", href: "/help/credits-plans-and-refunds" }] },
    ],
  },
  {
    slug: "credits-plans-and-refunds", title: "Credits, plans and refunds", summary: "Understand render costs, plan limits and automatic credit refunds.",
    sections: [
      { id: "credits", title: "What a render costs", paragraphs: [`A Preview (540p) costs ${CREDIT_COSTS.preview_render} credits. A Final (1080p) costs ${CREDIT_COSTS.final_render} credits. Scene generation costs ${CREDIT_COSTS.scene_generation} credits and a prompt edit costs ${CREDIT_COSTS.prompt_edit} credit.`, "Check your balance before starting a render. Buying extra credits does not change your plan's quality, retention or simultaneous-render limits."], links: [{ label: "Current pricing and credit packs", href: "/pricing" }] },
      { id: "free", title: "The Free plan", paragraphs: [`A new account gets ${FREE_PLAN_CREDITS} credits once, after you confirm your email: enough for ${creditValue(FREE_PLAN_CREDITS, "free")}. Free renders Previews only; Final renders need Creator or Pro.`] },
      { id: "plans", title: "Plan limits", paragraphs: (Object.keys(planNames) as PlanId[]).map(planSummary) },
      { id: "expiry", title: "Do credits expire?", paragraphs: [CREDIT_EXPIRY_RULES] },
      { id: "referrals", title: "Invite friends", paragraphs: [`Your invite link is on your Profile. When someone signs up with it and makes their first payment, you both get ${REFERRAL_BONUS_CREDITS} credits. Nothing is paid for a signup alone. Up to ${REFERRAL_MONTHLY_CAP} referrals are rewarded per month. Your own accounts don't count, and the bonus is taken back if that first payment is fully refunded or charged back.`], links: [{ label: "Referral terms", href: "/terms#referrals" }] },
      { id: "refunds", title: "Failed or canceled renders", paragraphs: [RENDER_REFUND_RULES, `After ${INPUT_FAILURE_DAILY_CAP} renders fail on their model in one day, new renders pause until the next day, so check the model in a glTF viewer first. If the balance still looks wrong after refreshing, contact support with the project and render details.`, "An automatic render-credit refund is different from a refund of a payment. See the refund policy for payment questions."], links: [{ label: "Refund policy", href: "/refunds" }, { label: "Contact support", href: "/contact" }] },
      { id: "billing", title: "Receipts, invoices and VAT", paragraphs: ["Paddle is the merchant of record and handles payments, receipts, invoices and VAT. Use Manage billing from your account to access the billing portal when available. For a missing receipt or invoice, contact support with the transaction reference; never send card details."] },
    ],
  },
  {
    slug: "downloading-sharing-and-retention", title: "Downloading, sharing and retention", summary: "Save your video, share a copy and understand how long files are kept.",
    sections: [
      { id: "download", title: "Save the finished video", paragraphs: ["When the render finishes, open its result and choose Download to save the MP4. Keep a local copy of anything you need long term.", "If a download link has expired, return to the result and choose Download again for a fresh link, as long as the render is still within retention."] },
      { id: "sharing", title: "Share your work", paragraphs: ["You own your renders. To share one, open the finished render, choose Share, then Create link. Anyone with the link can watch the video on its own page; nothing is public until you do this, and your prompt stays hidden unless you tick Show my prompt on the page.", "Stop sharing at any time from the same place: the old link stops working at once, and sharing again makes a new link. A shared link also stops working when the render expires under your plan's retention, so download a copy of anything you want to keep.", "Your model and texture licenses still apply. Follow any attribution or commercial-use restrictions and read the acceptable-use policy."], links: [{ label: "Acceptable use", href: "/acceptable-use" }] },
      { id: "retention", title: "How long files are kept", paragraphs: [
        `Render retention is ${PLAN_LIMITS.free.retentionDays} days on Free, ${PLAN_LIMITS.creator.retentionDays} days on Creator and ${PLAN_LIMITS.pro.retentionDays} days on Pro. The render's retention period is set when it starts and runs from completion.`,
        "Uploaded models are also subject to plan retention, measured from their last use. Keep the source model yourself. Expired outputs are removed and cannot be downloaded; the result may remain listed as Expired. Changing plan does not restore deleted files.",
      ] },
    ],
  },
  {
    slug: "troubleshooting", title: "Troubleshooting", summary: "Fix rejected uploads, failed renders, dark shots and model problems.",
    sections: [
      { id: "upload-rejected", title: "Upload rejected", paragraphs: [`Check that the file is a real, self-contained .glb and is no larger than ${maxMB} MB. Other formats and renamed files will be rejected.`, "Open the exported file in a fresh Blender scene. If it does not import correctly, export again from the original. If it is too large, reduce geometry or texture sizes."], links: [{ label: "How to export a .glb", href: "/help/preparing-your-model" }] },
      { id: "render-failed", title: "Render failed", paragraphs: [`Read the error shown with the result. Failures on our side are refunded automatically; if the model caused it, ${INPUT_FAILURE_FEE} credits are kept. Check the model and try a simpler shot; if the service is unavailable, try again later.`, "If it fails again, contact support with the project, error message and approximate time. Never include your password or access tokens."], links: [{ label: "Contact support", href: "/contact" }] },
      { id: "dark", title: "The shot looks dark", paragraphs: ["Try Studio and ask for soft, bright light with the subject clearly visible. Night street deliberately uses a darker setting. Check the model's base color and materials too; changing the light will not fix missing textures."] },
      { id: "scale", title: "Wrong scale or orientation", paragraphs: ["Check the source model's units, size and forward direction. Remove distant stray objects that could distort its bounds. Correct the orientation and apply rotation and scale in Blender, then export and inspect a fresh .glb."] },
      { id: "textures", title: "Missing textures", paragraphs: ["Make sure the .glb embeds its image textures. Procedural shaders and application-specific materials may not survive glTF export. Bake them to images and use glTF-compatible materials. Reopen the exported file before uploading to confirm that the surfaces look right."], links: [{ label: "Model preparation guide", href: "/help/preparing-your-model" }] },
    ],
  },
  {
    slug: "accounts-and-security", title: "Accounts & security", summary: "Sign in, recover access and keep your account safe.",
    sections: [
      { id: "sign-in", title: "Signing in", paragraphs: ["Use the sign-in method you used to create your account. If asked to confirm your email, open the verification message and follow its link. Check spam if it has not arrived.", "For an email-and-password account, choose Forgot password on the login screen and follow the reset email. Use the newest reset link if an earlier one has expired."], links: [{ label: "Sign in", href: "/login" }, { label: "Reset your password", href: "/forgot-password" }] },
      { id: "security", title: "Keep access private", paragraphs: ["Use a strong, unique password and sign out on shared devices. Do not share login credentials, reset links or access tokens. Support does not need your password.", "If you suspect someone has accessed your account, reset your password and contact support. Report security concerns using the contact page."], links: [{ label: "Contact and security reports", href: "/contact" }] },
      { id: "account", title: "Account details and privacy", paragraphs: ["Open Profile for account and billing information, and Settings for application preferences. Read the privacy notice for information about your data. Contact support if you cannot access your account or need help with a data request."], links: [{ label: "Privacy notice", href: "/privacy" }] },
    ],
  },
];

export const HELP_FAQS = [
  { question: "Which model files can I upload?", answer: `One self-contained .glb (binary glTF), up to ${maxMB} MB. Other formats are not accepted yet.`, slug: "preparing-your-model" },
  { question: "How many credits does a render cost?", answer: `Preview (540p) costs ${CREDIT_COSTS.preview_render} credits. Final (1080p) costs ${CREDIT_COSTS.final_render} credits and requires Creator or Pro.`, slug: "credits-plans-and-refunds" },
  { question: "What happens if a render fails?", answer: RENDER_REFUND_RULES, slug: "credits-plans-and-refunds" },
  { question: "Do credits expire?", answer: CREDIT_EXPIRY_RULES, slug: "credits-plans-and-refunds" },
  { question: "Do I own my renders?", answer: "Yes. You own your renders, and you must own or license the models and textures you upload. Follow any license restrictions when sharing your work.", slug: "downloading-sharing-and-retention" },
  { question: "How long are renders kept?", answer: `Free: ${PLAN_LIMITS.free.retentionDays} days. Creator: ${PLAN_LIMITS.creator.retentionDays} days. Pro: ${PLAN_LIMITS.pro.retentionDays} days. Download a copy before retention ends.`, slug: "downloading-sharing-and-retention" },
];

export type HelpSearchEntry = Pick<HelpArticle, "slug" | "title" | "summary"> & { searchText: string };
export function helpSearchEntries(): HelpSearchEntry[] {
  return HELP_ARTICLES.map(({ slug, title, summary, sections }) => ({
    slug, title, summary,
    searchText: [title, summary, ...sections.flatMap((s) => [s.title, ...s.paragraphs, ...(s.steps ?? [])])].join(" ").toLowerCase(),
  }));
}
export function filterHelp(entries: HelpSearchEntry[], query: string): HelpSearchEntry[] {
  const terms = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  return entries.filter((entry) => terms.every((term) => entry.searchText.includes(term)));
}
