import { parseGalleryManifest, type GalleryItem } from "@/components/landing/manifestSchema";
import { clipMedia, type ClipMedia } from "@/components/landing/manifest";
import { WORLDS, type WorldId } from "@/lib/render/worlds";
import { SITE_URL } from "@/lib/site";
import manifest from "@/public/landing/gallery/manifest.json";

/**
 * The /examples pages: one per landing gallery clip (public/landing/gallery/manifest.json), each with its own
 * hand-written notes on why the shot works and how to adapt it. The media, caption, prompt and credit come from
 * the manifest; everything written here is per-clip copy. examples.test.ts fails when a manifest clip has no entry,
 * when an entry's text runs under 150 words, or when copy names a car or product brand.
 */

/**
 * When the gallery clips were published: the day the rendered files were added to the repository
 * (`git log --diff-filter=A -- public/landing/gallery/*.mp4`, all on 2026-09-18). Used as the VideoObject uploadDate.
 */
export const EXAMPLES_UPLOAD_DATE = "2026-09-18";

/** Where the clips came from, said on every example page (the gallery says the same). */
export const EXAMPLES_PROVENANCE =
  "This clip was rendered with Blender Cycles through the same offline rendering pipeline that powers Valora3D, on a workstation, to show what the pipeline produces. It was not made through the web app, and your own renders will differ with your model, prompt and settings.";

type ExampleCopy = {
  /** The manifest entry this copy belongs to, by its `video` file. */
  video: string;
  slug: string;
  title: string;
  description: string;
  world: WorldId;
  /** Plain-words version of the camera move and light, shown near the top. */
  shotIdea: string;
  /** Measured with ffprobe on the shipped .mp4 (whole seconds). */
  durationSeconds: number;
  sections: { heading: string; paragraphs: string[] }[];
  /** Concrete changes to adapt the shot to another model. */
  adapt: string[];
};

export type Example = ExampleCopy & { item: GalleryItem; media: ClipMedia; worldLabel: string };

const COPY: ExampleCopy[] = [
  {
    video: "camera-01.mp4",
    slug: "vintage-camera-slow-orbit",
    title: "Vintage camera: slow orbit with a push-in on black",
    description: "A vintage camera turns on a black studio cyclorama under a key and rim light. See why a slow orbit with a gentle push-in suits small objects, and how to adapt it.",
    world: "studio_cyc",
    shotIdea: "The camera circles about 70 degrees around the subject while easing slightly closer, with one main light and one edge light on a black background.",
    durationSeconds: 4,
    sections: [
      {
        heading: "Why the camera move works",
        paragraphs: [
          "A small object with lots of surface detail, like a camera body with dials, a lens barrel and a strap, reads best when the viewer sees it from more than one side. A partial orbit of about 70 degrees shows the front, one corner and part of the side without ever swinging round to the plain back. The gentle push-in on top of the orbit adds a sense of arrival, so the clip feels like it is going somewhere rather than just spinning.",
          "A 70 mm lens keeps the proportions natural. Wider lenses exaggerate the parts nearest the camera, which makes a compact object look distorted; this focal length flattens it just enough to look like a product photo in motion.",
        ],
      },
      {
        heading: "Why the light works",
        paragraphs: [
          "The key light gives the body its shape and shows the texture of the leatherette and metal. The rim light traces the outline from behind, which is what separates a dark object from a black background. Without that edge the silhouette would disappear. The black cyclorama has no horizon line, so nothing competes with the subject.",
        ],
      },
    ],
    adapt: [
      "For a lighter object, keep the same move but ask for a charcoal or white background so the edges do not glow too much.",
      "If your model has a plain back, keep the orbit under 90 degrees so the camera never shows it.",
      "For a portrait 9:16 version, ask for a slightly slower push-in so the subject stays in the narrower frame.",
    ],
  },
  {
    video: "pocket-watch.mp4",
    slug: "pocket-watch-85mm-push-in",
    title: "Pocket watch: an 85 mm push-in on a black cyclorama",
    description: "A pocket watch shot with a longer lens and a shallow depth of field. Learn why 85 mm at f/2 flatters reflective jewelry and small metal objects.",
    world: "studio_cyc",
    shotIdea: "A slow partial orbit with a gentle push-in, framed tighter with a longer lens and a wide aperture so the background falls away.",
    durationSeconds: 4,
    sections: [
      {
        heading: "Why a longer lens",
        paragraphs: [
          "Watches and jewelry are small, round and highly reflective. An 85 mm lens lets the camera frame the object tightly from further away, which keeps the case and chain in true proportion and stops the nearest edge from bulging towards the viewer. The shallow depth of field at f/2 keeps the dial sharp while the chain softens, pulling attention to the face.",
          "Because the lens is long, small camera movements look large on screen. That is why the move stays slow: a fast orbit at this focal length would feel restless and make fine engraving hard to read.",
        ],
      },
      {
        heading: "Why the light works on metal",
        paragraphs: [
          "Polished metal does not show its own color much; it shows what it reflects. The key light creates one bright highlight that travels across the case as the camera moves, and that moving highlight is what tells the viewer the surface is metal. The rim light keeps the outline of the case visible against the black background.",
        ],
      },
    ],
    adapt: [
      "For rings or earrings, keep the 85 mm framing and ask for an even slower move so the highlight glides rather than flickers.",
      "If the dial glass hides the face under reflections, ask for the camera to stay a little higher, looking down onto the face.",
      "Try a longer clip length if the push-in feels rushed at this focal length.",
    ],
  },
  {
    video: "vintage-microscope.mp4",
    slug: "microscope-charcoal-cyclorama",
    title: "Vintage microscope: a charcoal cyclorama for dark metal",
    description: "A vintage microscope rendered against charcoal instead of black. See when a mid-gray background beats pure black and how to reuse the setup for tall objects.",
    world: "studio_cyc",
    shotIdea: "The same slow partial orbit and push-in as the other studio clips, but on a charcoal background, which keeps dark painted metal readable.",
    durationSeconds: 4,
    sections: [
      {
        heading: "Why charcoal instead of black",
        paragraphs: [
          "A microscope is mostly dark enamel and brass. Against pure black, the darkest parts of the frame and stand would merge with the background and the object would read as floating highlights. A charcoal cyclorama lifts the background just enough that the dark shapes still have an edge, while staying dark enough that the brass details stay the brightest thing in the frame.",
          "This is a useful rule of thumb: when most of the subject is darker than mid-gray, step the background up from black to charcoal rather than adding more light to the subject.",
        ],
      },
      {
        heading: "Framing a tall object",
        paragraphs: [
          "A microscope is taller than it is wide, so the 70 mm framing leaves room above the eyepiece and below the base. The orbit shows the stage and focusing knobs from the side, which is where the object is most interesting, instead of looking straight down the tube.",
        ],
      },
    ],
    adapt: [
      "For other tall objects such as bottles, lamps or trophies, consider portrait 9:16 so the subject fills the frame.",
      "If your object is dark and matte, ask for a stronger rim light before brightening the key light.",
      "Keep the orbit partial if one side of the model is less detailed.",
    ],
  },
  {
    video: "flighthelmet.mp4",
    slug: "flight-helmet-key-and-rim",
    title: "Flight helmet: key and rim light on mixed materials",
    description: "A flight helmet with leather, rubber, glass and metal, turning under a key and rim light. See how one lighting setup handles several materials at once.",
    world: "studio_cyc",
    shotIdea: "A slow partial orbit with a gentle push-in at 60 mm, lit by a single key light and a rim light on a black cyclorama.",
    durationSeconds: 4,
    sections: [
      {
        heading: "One light setup, many materials",
        paragraphs: [
          "This model mixes worn leather, rubber hoses, glass goggles and small metal fittings. Each material responds differently: leather shows texture under a raking key light, glass shows reflections, and metal shows sharp highlights. A simple key and rim setup lets each material behave naturally instead of flattening them all with even, shadowless light.",
          "The orbit matters here too. As the camera moves, the goggle lenses catch and lose the highlight, which is what makes glass read as glass. On a still frame the same lenses could look like flat gray discs.",
        ],
      },
      {
        heading: "Why 60 mm",
        paragraphs: [
          "The helmet is larger than a watch or camera and has depth from front to back. A slightly shorter lens keeps the whole object in view during the move while still avoiding the distortion of a wide angle. It also keeps more of the model in focus, so the straps at the back do not blur into mush.",
        ],
      },
    ],
    adapt: [
      "For shoes, bags or other soft goods with stitching, keep the key light low and to one side so the texture casts small shadows.",
      "If your model has glass parts that look dull, keep the camera moving; a static shot hides what makes glass look real.",
      "Check that your textures are embedded in the .glb first; lighting cannot fix a missing leather or fabric texture.",
    ],
  },
  {
    video: "mid-century-lounge-chair.mp4",
    slug: "lounge-chair-white-cyclorama",
    title: "Lounge chair: furniture on a white cyclorama",
    description: "A mid-century style lounge chair on a white studio cyclorama at 45 mm. See why furniture needs a wider lens and a bright background, and how to adapt it.",
    world: "studio_cyc",
    shotIdea: "A slow partial orbit with a gentle push-in using a wider 45 mm lens, on a white background with a key and rim light.",
    durationSeconds: 4,
    sections: [
      {
        heading: "Why a white background for furniture",
        paragraphs: [
          "Furniture is usually photographed in bright, clean spaces because that is how people imagine it at home. A white cyclorama gives the chair a soft floor shadow, which grounds it and shows its footprint, something a black background hides. The dark wood shell and upholstery also stand out strongly against white without needing a strong rim light.",
          "Soft floor contact matters for any object that stands on the ground. Without a visible shadow, a chair can look pasted onto the background.",
        ],
      },
      {
        heading: "Why 45 mm",
        paragraphs: [
          "A chair is a large object, and the viewer wants to see its whole silhouette as the camera moves. A 45 mm lens is close to how the eye sees a room, so the chair keeps its real proportions while the entire frame stays in view. Longer lenses would force the camera very far back or crop the armrests.",
        ],
      },
    ],
    adapt: [
      "For tables, lamps and shelving, keep the white background and ask for the camera at seated eye level rather than looking down.",
      "If your model is light-colored, switch to a charcoal background so its edges do not disappear into white.",
      "Make sure the model sits at real-world size; a chair exported in the wrong units will look odd against the studio floor.",
    ],
  },
  {
    video: "toycar.mp4",
    slug: "toy-car-close-orbit",
    title: "Toy car: a close orbit on a draped cloth",
    description: "A detailed toy car on a draped cloth, filmed in a close orbit at 85 mm. See how a longer lens and shallow focus make a small collectible look substantial.",
    world: "studio_cyc",
    shotIdea: "A slow partial orbit with a gentle push-in, tight on the subject with an 85 mm lens at f/2, on a black cyclorama.",
    durationSeconds: 4,
    sections: [
      {
        heading: "Making a small object feel big",
        paragraphs: [
          "Collectibles and scale models are small, but the goal is often to make them look like the real thing. A long lens at a wide aperture helps: the tight framing fills the screen with the subject, and the soft focus fall-off mimics the look of photographing something large from a distance. The draped cloth adds a soft surface under the model, so the scene reads as a still life rather than a floating object.",
          "Keeping the camera low, close to the height of the model, also helps. Looking down on a small object reminds the viewer of its size; looking across at it does the opposite.",
        ],
      },
      {
        heading: "Why the highlights matter",
        paragraphs: [
          "The paint and clear plastic windows pick up the key light as the camera moves. The rim light defines the roofline and wheel arches against the black background. Together they show the shape of the body, which is what a viewer reads first on any vehicle.",
        ],
      },
    ],
    adapt: [
      "For figurines, model kits or small toys, keep the 85 mm framing and a low camera height.",
      "If your model has a base or display stand, include it in the .glb so the subject has something to sit on.",
      "Try a different paint color or finish setting to compare versions before you render a Final.",
    ],
  },
  {
    video: "gt3rs-rain-walkin.mp4",
    slug: "car-rain-courtyard-walk-in",
    title: "Car in the rain: a handheld walk-in through trees",
    description: "A handheld walk-in towards a car in a rainy courtyard with wet tarmac and overcast light. See why the approach feels cinematic and how to adapt it to your vehicle.",
    world: "rain_courtyard",
    shotIdea: "The camera walks towards the car through the trees, with a slight handheld sway, in falling rain under an overcast sky.",
    durationSeconds: 5,
    sections: [
      {
        heading: "Why a walk-in works",
        paragraphs: [
          "A walk-in puts the viewer in the scene: the trees pass in the foreground, the car grows in the frame, and the slight handheld sway feels like someone approaching on foot. It is the opposite of a turntable, and it suits vehicles because it shows the car in a place rather than on a stand.",
          "Foreground elements are important. Passing branches and leaves give the move parallax, which is what makes a camera move read as real depth instead of a zoom.",
        ],
      },
      {
        heading: "Why overcast rain light",
        paragraphs: [
          "Overcast light is soft and comes from the whole sky, so the car's body shows long, smooth reflections instead of harsh hot spots. The wet tarmac doubles those reflections on the ground, and the falling rain adds texture to the air between the camera and the car. The result looks moody without being dark, which suits most paint colors.",
        ],
      },
    ],
    adapt: [
      "Use the Rain courtyard world and describe the approach direction, for example towards the front corner or the side.",
      "For a darker paint color, ask for the car to be framed against the brighter part of the sky so the roofline stays visible.",
      "Try a longer clip length if you want the walk-in to end on a held frame of the car.",
    ],
  },
  {
    video: "gt3rs-rain-close.mp4",
    slug: "car-rain-low-sill-pass",
    title: "Car in the rain: a low close pass along the sill",
    description: "A low camera pass along a car's side sill in the rain, at 45 mm and f/5.6. See why a low, close move shows detail and speed without the car moving.",
    world: "rain_courtyard",
    shotIdea: "The camera glides low and close along the side of the car towards the trees, in rain on wet tarmac, with a 45 mm lens at f/5.6.",
    durationSeconds: 5,
    sections: [
      {
        heading: "Why low and close",
        paragraphs: [
          "Placing the camera near the ground and close to the body makes a parked car feel fast. The side sill, wheels and lower bodywork rush past the lens, and the low angle makes the car look wider and more planted. It is a detail shot, meant to follow a wider establishing clip rather than to introduce the car.",
          "The pass moves towards the trees, so the background changes as the camera travels. That gives the move a destination, and the shot ends with context instead of a close-up of paint.",
        ],
      },
      {
        heading: "Why f/5.6 here",
        paragraphs: [
          "Close to a large object, a wide aperture would blur most of the body. At f/5.6 more of the sill and wheel stay sharp while the background still softens. The wet ground reflects the body line, and the rain gives the air between the lens and the car visible depth.",
        ],
      },
    ],
    adapt: [
      "Pair this shot with a wider walk-in so the viewer sees the whole car first.",
      "Ask for the pass along the side that has the most interesting detail, such as vents, badges or wheel designs on your own model.",
      "If the camera clips into a very low body, ask for a slightly higher pass at wheel-hub height.",
    ],
  },
  {
    video: "720s-rain-walkin.mp4",
    slug: "green-supercar-rain-walk-in",
    title: "Green supercar: a rainy walk-in on a bold paint color",
    description: "A handheld walk-in on a green supercar in a rainy courtyard. See how a saturated paint color behaves in soft overcast light and wet reflections.",
    world: "rain_courtyard",
    shotIdea: "The same handheld walk-in through the trees as the other rain clips, on a car with a bold green paint, in overcast light and falling rain.",
    durationSeconds: 5,
    sections: [
      {
        heading: "Bold color in soft light",
        paragraphs: [
          "Saturated paint colors can look cartoonish under hard sunlight, where bright highlights wash out the hue and deep shadows turn it black. Overcast light is much gentler: it shows the color across the whole body, and the reflections of the gray sky add depth without overpowering it. The green reads as green from every angle of the approach.",
          "The wet ground helps too. Its reflection repeats the color underneath the car, which makes the paint the main event of the frame.",
        ],
      },
      {
        heading: "Why the same move on a different car",
        paragraphs: [
          "Comparing this clip with the other rain walk-in shows how much the subject changes a shot. The camera path, world and weather are the same; only the car and its paint differ. A lower, wider body sits differently in the frame, and the trees crossing the lens hide and reveal it at different moments.",
        ],
      },
    ],
    adapt: [
      "Use the paint color setting to try your own color before writing a new prompt.",
      "For bright colors, stay in overcast worlds; for dark colors, ask for the car against the brighter sky.",
      "Keep a seed fixed while you compare colors so the camera and weather stay close between versions.",
    ],
  },
];

const ITEMS = parseGalleryManifest(manifest);

export const EXAMPLES: Example[] = COPY.map((copy) => {
  const item = ITEMS.find((i) => i.video === copy.video);
  if (!item) throw new Error(`examples: no gallery clip ${copy.video}`);
  const media = clipMedia(item);
  if (!media) throw new Error(`examples: ${copy.video} has no media`);
  const worldLabel = WORLDS.find((w) => w.id === copy.world)?.label ?? copy.world;
  return { ...copy, item, media, worldLabel };
});

export function exampleBySlug(slug: string): Example | undefined {
  return EXAMPLES.find((e) => e.slug === slug);
}

/** Up to `count` other examples: same world first, then the rest, in manifest order. */
export function relatedExamples(example: Example, count = 3): Example[] {
  const others = EXAMPLES.filter((e) => e.slug !== example.slug);
  return [...others.filter((e) => e.world === example.world), ...others.filter((e) => e.world !== example.world)].slice(0, count);
}

/** Every word of an example's own copy (not the manifest caption or prompt). */
export function exampleText(example: Pick<Example, "shotIdea" | "sections" | "adapt">): string {
  return [example.shotIdea, ...example.sections.flatMap((s) => [s.heading, ...s.paragraphs]), ...example.adapt].join(" ");
}

export function wordCount(text: string): number {
  return text.split(/\s+/).filter(Boolean).length;
}

/** ISO 8601 duration for schema.org, e.g. PT4S. */
export function isoDuration(seconds: number): string {
  return `PT${Math.round(seconds)}S`;
}

/** schema.org VideoObject for an example page. Absolute URLs; no ratings or view counts (there are none). */
export function exampleVideoSchema(example: Example): object {
  return {
    "@context": "https://schema.org",
    "@type": "VideoObject",
    name: example.title,
    description: example.description,
    thumbnailUrl: [`${SITE_URL}${example.media.poster}`],
    contentUrl: `${SITE_URL}${example.media.video}`,
    uploadDate: EXAMPLES_UPLOAD_DATE,
    duration: isoDuration(example.durationSeconds),
    url: `${SITE_URL}/examples/${example.slug}`,
  };
}
