// Captures the landing page assets from the app's own viewer.
//
//   node scripts/capture-landing.mjs [hero|gallery|app|thumbs|all]   (dev server on :3000)
//
// hero    → public/landing/hero.{mp4,webm} + hero-poster.jpg (slow orbit, rainy night city)
// gallery → public/landing/gallery/*.jpg + manifest.json (clip entries are merged, not lost)
// app     → public/landing/app/*.jpg (three studio screenshots from a seeded project)
//
// Frames come from /dev/viewer?bare=WxH; the viewer is stepped along the plan's camera
// path with the `rs:preview` event, and ffmpeg (on PATH) assembles the loop.

import { chromium } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const OUT = join(process.cwd(), "public", "landing");
const HERO_FRAMES = 120;
const HERO_SECONDS = 10;
const FPS = 24;

// Framing: the whole car with margin (distance �1.4 of the plan's default, 1.1 m camera,
// 40 mm) so the headline over the loop stays legible and the sides survive the mobile crop.
const HERO_QUERY = "source=sample&prompt=Rainy%20night%20on%20a%20city%20street%2C%20cinematic&rain=0.4&wet=0.7&dist=0.95&height=0.9&lens=45&grid=0";

// (file, prompt, model, size hint for the gallery grid (large spans two columns), preview second)
const GALLERY = [
  { file: "car-studio-white", source: "sample", prompt: "White studio, soft light, orbit around the car", size: "large", t: 6 },
  { file: "car-studio-black", source: "sample", prompt: "Clean black studio, dramatic lighting, slow orbit", size: "wide", t: 3.5 },
  { file: "car-road-dusk", source: "sample", prompt: "Open mountain road at sunset, cinematic", size: "wide", t: 4 },
  { file: "car-city-rain", source: "sample", prompt: "Rainy night on a city street, wet asphalt, cinematic", size: "wide", t: 7 },
  { file: "product-studio-white", source: "product", prompt: "White studio, soft even light", size: "wide", t: 2 },
  { file: "product-studio-black", source: "product", prompt: "Black studio, dramatic three-point light", size: "large", t: 5 },
  { file: "product-road", source: "product", prompt: "On the road at golden hour", size: "wide", t: 6.5 },
  { file: "car-handheld-approach", source: "sample", prompt: "Handheld, walking toward the car at night in the rain", size: "large", t: 8 },
  { file: "car-low-tracking", source: "sample", prompt: "Low tracking shot alongside the car, foggy road at dusk", size: "wide", t: 5 },
];

const LAUNCH = { args: ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] };

function ffmpeg(args) {
  execFileSync("ffmpeg", ["-y", "-hide_banner", "-loglevel", "error", ...args], { stdio: "inherit" });
}

const HIDE_DEV_BADGE = "nextjs-portal { display: none !important; }";

/** The app shell is behind the AuthGate: a fresh context signs in as the local guest first. */
async function newAppPage(browser, viewport) {
  const page = await browser.newPage({ viewport });
  await page.goto(`${BASE}/login`);
  await page.getByRole("button", { name: /continue as guest/i }).click();
  await page.waitForURL((u) => !u.pathname.startsWith("/login"));
  return page;
}

// The bare viewer sits inside the app shell (260px sidebar), so the window is wider than the frame.
const VIEWER_VIEWPORT = { width: 1600 + 320, height: 1000 + 40 };

/** Opens the bare viewer, waits for the model to land, then leaves the page for shots. */
async function openViewer(page, query, size = "1600x1000") {
  await page.goto(`${BASE}/dev/viewer?bare=${size}&${query}`);
  await page.addStyleTag({ content: HIDE_DEV_BADGE });
  const viewer = page.locator("[data-bare-viewer]");
  await page.locator("[data-model-loaded='true']").waitFor({ timeout: 90_000 });
  // The intro settle drives the orbit camera; the preview camera takes over once `t` is set.
  await page.waitForTimeout(1500);
  return viewer;
}

async function setPreview(page, seconds) {
  await page.evaluate((s) => window.dispatchEvent(new CustomEvent("rs:preview", { detail: s })), seconds);
  // Two frames so the preview camera and rain layer have both rendered at the new time.
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
  await page.waitForTimeout(120);
}

async function captureHero(browser) {
  const dir = join(tmpdir(), "rs-hero-frames");
  rmSync(dir, { recursive: true, force: true });
  mkdirSync(dir, { recursive: true });
  const page = await newAppPage(browser, VIEWER_VIEWPORT);
  const viewer = await openViewer(page, `${HERO_QUERY}&t=0`);
  // Fixed clip: an element screenshot waits for the element to be "stable", which never
  // settles while the page animates; the viewer box does not move, so measure it once.
  const clip = await viewer.boundingBox();
  for (let i = 0; i < HERO_FRAMES; i++) {
    await setPreview(page, (i / HERO_FRAMES) * HERO_SECONDS);
    await page.screenshot({ path: join(dir, `f${String(i).padStart(4, "0")}.png`), type: "png", clip, animations: "disabled" });
    if (i % 20 === 0) console.log(`hero frame ${i}/${HERO_FRAMES}`);
  }
  await page.close();

  // The orbit covers 162°, so its ends differ too much for a crossfade (it ghosts the car).
  // Ping-pong instead: forward, then the same frames reversed, minus the duplicated turning
  // frames, so the loop has no seam. Motion interpolation halves the speed to a real slow orbit.
  const frames = `${dir.replaceAll("\\", "/")}/f%04d.png`;
  const filter =
    `[0:v]scale=1280:800:flags=lanczos,split[a][b];` +
    `[b]reverse,trim=start_frame=1:end_frame=${HERO_FRAMES - 1},setpts=PTS-STARTPTS[r];` +
    `[a][r]concat=n=2:v=1:a=0,setpts=2*PTS,` +
    `minterpolate=fps=${FPS}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,format=yuv420p[v]`;
  ffmpeg(["-framerate", String(FPS), "-i", frames, "-filter_complex", filter, "-map", "[v]", "-c:v", "libx264", "-preset", "slow", "-crf", "24", "-movflags", "+faststart", join(OUT, "hero.mp4")]);
  ffmpeg(["-framerate", String(FPS), "-i", frames, "-filter_complex", filter, "-map", "[v]", "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "36", "-row-mt", "1", join(OUT, "hero.webm")]);
  ffmpeg(["-i", join(dir, "f0000.png"), "-vf", "scale=1280:800", "-q:v", "4", join(OUT, "hero-poster.jpg")]);
  for (const f of ["hero.mp4", "hero.webm", "hero-poster.jpg"]) console.log(f, Math.round(statSync(join(OUT, f)).size / 1024), "KB");
  rmSync(dir, { recursive: true, force: true });
}

async function captureGallery(browser) {
  const dir = join(OUT, "gallery");
  mkdirSync(dir, { recursive: true });
  const page = await newAppPage(browser, VIEWER_VIEWPORT);
  const manifest = [];
  for (const g of GALLERY) {
    const viewer = await openViewer(page, `source=${g.source}&prompt=${encodeURIComponent(g.prompt)}&t=${g.t}`);
    await setPreview(page, g.t);
    const png = join(tmpdir(), `rs-${g.file}.png`);
    await viewer.screenshot({ path: png, type: "png" });
    const jpg = join(dir, `${g.file}.jpg`);
    // q 82 ≈ ffmpeg -q:v 4; step down if a still is over the 250 KB budget.
    for (const q of [4, 5, 6, 7]) {
      ffmpeg(["-i", png, "-q:v", String(q), jpg]);
      if (statSync(jpg).size <= 250 * 1024) break;
    }
    rmSync(png, { force: true });
    manifest.push({ file: `${g.file}.jpg`, caption: g.prompt, prompt: g.prompt, model: g.source === "product" ? "product" : "car", size: g.size, width: 1600, height: 1000 });
    console.log(g.file, Math.round(statSync(jpg).size / 1024), "KB");
  }
  await page.close();
  writeFileSync(join(dir, "manifest.json"), JSON.stringify(mergeManifest(join(dir, "manifest.json"), manifest), null, 2) + "\n");
}

/**
 * Stills are recaptured, everything else is kept: an entry's clip fields (poster,
 * preview, video, credit, placeholder) and any entry this run does not produce —
 * clip-only entries included — survive, in their existing order.
 */
function mergeManifest(path, fresh) {
  let previous = [];
  if (existsSync(path)) {
    try {
      previous = JSON.parse(readFileSync(path, "utf8"));
    } catch {
      previous = [];
    }
  }
  const byFile = new Map(fresh.map((item) => [item.file, item]));
  const out = [];
  for (const old of previous) {
    const next = byFile.get(old.file);
    if (!next) {
      out.push(old);
      continue;
    }
    byFile.delete(old.file);
    const { poster, preview, video, credit, placeholder } = old;
    out.push({ ...next, ...(poster && { poster }), ...(preview && { preview }), ...(video && { video }), ...(credit && { credit }), ...(placeholder && { placeholder }) });
  }
  return [...out, ...byFile.values()];
}

/** Three studio states from a fresh project: upload card, planning sequence, scene with the drawer open. */
async function captureApp(browser) {
  const dir = join(OUT, "app");
  mkdirSync(dir, { recursive: true });
  const page = await newAppPage(browser, { width: 1440, height: 900 });
  const context = page.context();
  const shot = async (name) => {
    const png = join(tmpdir(), `rs-app-${name}.png`);
    await page.screenshot({ path: png });
    const jpg = join(dir, `${name}.jpg`);
    ffmpeg(["-i", png, "-q:v", "3", jpg]);
    rmSync(png, { force: true });
    console.log(name, Math.round(statSync(jpg).size / 1024), "KB");
  };

  await page.goto(`${BASE}/projects`);
  await page.addStyleTag({ content: HIDE_DEV_BADGE });
  await page.getByRole("button", { name: /new project/i }).first().click();
  const dialog = page.getByRole("dialog");
  await dialog.waitFor();
  await dialog.getByRole("button", { name: /^create$/i }).click();
  await page.waitForURL(/\/projects\/[^/?]+$/);
  await page.waitForTimeout(800);
  await shot("01-upload");

  await page.getByRole("button", { name: "Model options" }).click();
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Add a model" }).click();
  await chooser;
  await page.getByRole("button", { name: "Sample car" }).click();
  await page.locator("[data-model-loaded='true']").waitFor({ timeout: 90_000 });
  await page.getByTestId("studio-status").filter({ hasText: /car/i }).waitFor({ timeout: 20_000 });
  await page.waitForTimeout(1200);

  const prompt = page.getByRole("textbox", { name: "Describe your render" });
  await prompt.fill("Rainy night on a city street, handheld, walking toward the car");
  await page.keyboard.press("Enter");
  await page.waitForTimeout(700);
  await shot("02-planning");

  await page.getByRole("button", { name: /^1 version$/ }).waitFor({ timeout: 20_000 });
  await page.getByRole("button", { name: "Scene details" }).click();
  await page.waitForTimeout(1500);
  await shot("03-scene");
  await context.close();
}

/** Dropzone thumbnail of the sample car: model-only studio frame at 640�400. */
async function captureThumbs(browser) {
  const page = await newAppPage(browser, VIEWER_VIEWPORT);
  const viewer = await openViewer(page, "source=sample&env=studio_black&t=5.5&dist=0.9&height=1.1&lens=45", "1280x800");
  const png = join(tmpdir(), "rs-thumb-car.png");
  await viewer.screenshot({ path: png, type: "png" });
  const jpg = join(process.cwd(), "public", "samples", "car.jpg");
  ffmpeg(["-i", png, "-vf", "scale=640:400:flags=lanczos", "-q:v", "5", jpg]);
  rmSync(png, { force: true });
  await page.close();
  console.log("car.jpg", Math.round(statSync(jpg).size / 1024), "KB");
}

const what = process.argv[2] ?? "all";
mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch(LAUNCH);
try {
  if (what === "hero" || what === "all") await captureHero(browser);
  if (what === "gallery" || what === "all") await captureGallery(browser);
  if (what === "app" || what === "all") await captureApp(browser);
  if (what === "thumbs" || what === "all") await captureThumbs(browser);
} finally {
  await browser.close();
}
console.log("done:", readdirSync(OUT).join(", "));
