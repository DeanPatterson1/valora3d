import { MAX_UPLOAD_BYTES } from "./pricing";

/**
 * "Export a .glb from <app>" guides (/guides/<slug>). Each one follows that app's own glTF export documentation,
 * listed in `sources` and shown on the page; guides.test.ts requires every source to sit on the vendor's domain.
 * Checked against the vendor pages on 2026-09-28. Apps without an official glTF exporter documented by their vendor
 * are left out on purpose rather than written from memory: Autodesk Maya (its supported export formats list no
 * glTF) and Autodesk Fusion (its export format options list FBX, OBJ and STL for meshes, no glTF).
 * When a vendor changes its exporter, update the steps from the linked page, not from recollection.
 */

export type Guide = {
  slug: string;
  app: string;
  vendor: string;
  title: string;
  summary: string;
  /** Which versions the vendor's page covers, in its own terms. */
  appliesTo: string;
  /** Domains that count as the vendor's own documentation. */
  vendorDomains: string[];
  sources: { label: string; url: string }[];
  steps: string[];
  settings: { label: string; advice: string }[];
  pitfalls: string[];
};

export const GUIDES_CHECKED_ON = "2026-09-28";

const maxMB = Math.round(MAX_UPLOAD_BYTES / 1024 / 1024);
const CHECK_STEP = `Drop the exported file into the free .glb checker to confirm its size (up to ${maxMB} MB), textures, scale and orientation before uploading.`;

export const GUIDES: Guide[] = [
  {
    slug: "export-glb-from-blender",
    app: "Blender",
    vendor: "Blender Foundation",
    title: "Export a .glb from Blender",
    summary: "Use Blender's built-in glTF 2.0 exporter to save a single .glb with its meshes, materials and image textures packed inside.",
    appliesTo: "The glTF 2.0 add-on that ships with Blender and is enabled by default (current Blender manual).",
    vendorDomains: ["blender.org"],
    sources: [{ label: "Blender Manual: glTF 2.0", url: "https://docs.blender.org/manual/en/latest/addons/scene_gltf2.html" }],
    steps: [
      "Work on a copy of the .blend file. In Object Mode, check that the model faces the way you want and sits at real-world size.",
      "Open File > Export > glTF 2.0 (.glb/.gltf).",
      "Set Format to glTF Binary (.glb). The manual describes this as a single file with all mesh data, image textures and related information packed into one binary file.",
      "Under Include, tick Selected Objects if the scene holds anything you don't want in the model, such as reference images or helper objects.",
      "Under Transform, keep +Y Up ticked. glTF expects Y to point up, and Blender converts from its own Z-up axis on export.",
      "Under Data > Mesh, tick Apply Modifiers so mirrors, subdivision and other modifiers are baked into the exported geometry.",
      "Leave Draco and Meshopt compression unticked, then export.",
      CHECK_STEP,
    ],
    settings: [
      { label: "Format", advice: "glTF Binary (.glb). glTF Separate writes loose .bin and image files, which can't be uploaded." },
      { label: "Materials", advice: "Export. Placeholder or No Export drops the look of the model." },
      { label: "Images", advice: "Anything other than None, which would leave the textures out of the file." },
      { label: "Draco / Meshopt compression", advice: "Off. Valora3D's preview does not decode compressed meshes." },
    ],
    pitfalls: [
      "Only Principled BSDF (metal/roughness) and unlit materials export. Procedural node setups need to be baked to image textures first.",
      "Area lights and World lighting are ignored by glTF. That's fine here: Valora3D lights the shot itself.",
      "UDIM textures are split into one image per tile, which can make the file much larger than expected.",
    ],
  },
  {
    slug: "export-glb-from-sketchup",
    app: "SketchUp",
    vendor: "Trimble",
    title: "Export a .glb from SketchUp",
    summary: "Save a SketchUp model as a GLTF Binary file from the 3D Model export dialog, then check the result before uploading.",
    appliesTo: "SketchUp desktop, per the SketchUp Help Center article on glTF files.",
    vendorDomains: ["sketchup.com"],
    sources: [{ label: "SketchUp Help: Working with glTF files", url: "https://help.sketchup.com/en/sketchup/working-gltf-files" }],
    steps: [
      "Save your SketchUp file, then hide or delete anything you don't want in the model, such as people, section planes and guide geometry.",
      "Select File > Export > 3D Model.",
      "In the file type drop-down, choose GLTF Binary File (*.glb), name the file and export.",
      CHECK_STEP,
    ],
    settings: [
      { label: "File type", advice: "GLTF Binary File (*.glb): it keeps geometry and textures in one file." },
      { label: "Textures", advice: "PNG and JPEG textures export as they are; SketchUp tries to convert other image formats to PNG." },
    ],
    pitfalls: [
      "SketchUp's help lists no export options for units, axis or selection, so confirm the exported size and orientation with the checker.",
      "Exported files carry two material descriptions (specular/glossiness and metal/roughness). If surfaces look wrong in a glTF viewer, simplify the SketchUp material and export again.",
      "If a material has a bump map but no normal map, the exporter uses the bump map in place of the normal map, so the surface relief may look different.",
    ],
  },
  {
    slug: "export-glb-from-3ds-max",
    app: "3ds Max",
    vendor: "Autodesk",
    title: "Export a .glb from 3ds Max",
    summary: "Use the glTF exporter built into 3ds Max 2023 and later, with glTF materials applied, to write one binary .glb.",
    appliesTo: "3ds Max 2023 and later, which added the built-in glTF exporter and glTF material (Autodesk help, 2023 and 2026).",
    vendorDomains: ["autodesk.com"],
    sources: [
      { label: "3ds Max 2026 Help: glTF export", url: "https://help.autodesk.com/cloudhelp/2026/ENU/3DSMax-Interoperability/files/GUID-5B4C8EC2-2230-4F9F-B3C6-48D9E347E37D.htm" },
      { label: "3ds Max 2023 Help: What's new (glTF exporter)", url: "https://help.autodesk.com/cloudhelp/2023/ENU/3DSMax-What-s-New/files/GUID-EFBB037D-C4EB-42D2-9CE1-30FCAD483C31.htm" },
    ],
    steps: [
      "Apply glTF Materials to the meshes you'll export. Autodesk notes the exporter gives its best results with them.",
      "Use Bitmap textures for every material input. The Bitmap Texture is the only map type the glTF Material accepts.",
      "Open File > Export > Real-Time Exporter…, or File > Export and choose GL Transmission Format (*.glb, *.gltf) in the Save as type list.",
      "Tick Export glTF Binary (.glb) so geometry, materials and textures go into a single file.",
      "Set Export Set to the selection or object set you want, so cameras, helpers and hidden work don't come along.",
      CHECK_STEP,
    ],
    settings: [
      { label: "Export glTF Binary (.glb)", advice: "On. Without it the exporter writes a .gltf with separate files." },
      { label: "Export Set", advice: "Only the objects that make up the model." },
      { label: "Shell Materials > Export", advice: "Choose the baked material if your shell materials hold a baked result you want to keep." },
    ],
    pitfalls: [
      "Animation, skin and morpher data are not exported, and hierarchies are flattened. That's fine for Valora3D, which moves the camera around a posed model.",
      "Vertex colors are not exported, so bake any look that relies on them into a texture.",
      "Two bitmaps with the same file name but different types export as one. Give every texture a unique name.",
      "Multi/Sub-Object materials with empty slots can break the export. Remove empty slots first.",
    ],
  },
  {
    slug: "export-glb-from-cinema-4d",
    app: "Cinema 4D",
    vendor: "Maxon",
    title: "Export a .glb from Cinema 4D",
    summary: "Switch Cinema 4D's glTF exporter to GLB (Binary), flip the Z axis and bake shaders so the model exports as one self-contained file.",
    appliesTo: "Cinema 4D R25 through 2026, per the Maxon help for the glTF exporter.",
    vendorDomains: ["maxon.net"],
    sources: [
      { label: "Cinema 4D 2026 Help: glTF export", url: "https://help.maxon.net/c4d/2026/en-us/Content/html/FGLTFEXPORTER.html" },
      { label: "Cinema 4D 2026 Help: glTF export settings", url: "https://help.maxon.net/c4d/2026/en-us/Content/html/FGLTFEXPORTER-GLTFEXPORTER_GROUP.html" },
      { label: "Cinema 4D 2026 Help: glTF materials", url: "https://help.maxon.net/c4d/2026/en-us/Content/html/FGLTFEXPORTER-GLTFEXPORTER_GRP_MATERIALS.html" },
    ],
    steps: [
      "Bake any shaders to image textures first. Maxon's help says shaders are not supported by glTF export and must be baked, and node materials are not supported.",
      "Give every textured object UVW mapping. glTF only recognizes UVW projection, and only the first UV map is exported.",
      "Choose File > Export and pick the glTF exporter. Its defaults also live under Preferences > Import/Export > glTF.",
      "Set File Format to GLB (Binary). The default is glTF, which writes separate files.",
      "Turn on Flip Z. glTF follows the right-hand rule and Cinema 4D the left-hand rule, so the model would otherwise come out mirrored along Z.",
      "Keep Textures on so the images are coded into the file, and check Scale so the model comes out at real-world size.",
      CHECK_STEP,
    ],
    settings: [
      { label: "File Format", advice: "GLB (Binary)." },
      { label: "Flip Z", advice: "On, when you work in Cinema 4D's default coordinate system." },
      { label: "Resize Textures", advice: "Use it with Width and Height to bring very large textures down to 2048 or 4096 pixels." },
      { label: "Cameras", advice: "Off. Valora3D sets up its own camera." },
    ],
    pitfalls: [
      "GLB is not the default format. Exporting with the default settings gives you a .gltf plus separate files.",
      "Export Selected Object As… exports no materials, per Maxon's help. Use the full export and remove what you don't need from the scene instead.",
      "Lights are not exported. That's fine here: Valora3D lights the shot.",
    ],
  },
  {
    slug: "export-glb-from-rhino",
    app: "Rhino",
    vendor: "Robert McNeel & Associates",
    title: "Export a .glb from Rhino",
    summary: "Save a Rhino 8 model as binary glTF with Z mapped to Y, materials embedded and Draco compression off.",
    appliesTo: "Rhino 8, per the McNeel help page for glTF import and export.",
    vendorDomains: ["mcneel.com", "rhino3d.com"],
    sources: [{ label: "Rhino 8 Help: glTF import and export", url: "https://docs.mcneel.com/rhino/8/help/en-us/fileio/gltf_import_export.htm" }],
    steps: [
      "Select the objects to export, then choose File > Export Selected (or File > Save As for the whole model).",
      "In Files of type, choose the glTF binary format so the file is saved as .glb, then click Options.",
      "Tick Map Rhino Z to glTF Y. glTF is a Y-up format, and this rotates the model so it stands upright.",
      "Tick Export materials so materials and textures are embedded in the file.",
      "Tick Export open meshes if the model has surfaces that aren't closed solids. Otherwise only closed objects are exported.",
      "Leave Use Draco compression off, then save.",
      CHECK_STEP,
    ],
    settings: [
      { label: "Map Rhino Z to glTF Y", advice: "On." },
      { label: "Export materials", advice: "On. Rhino converts materials to glTF's PBR materials." },
      { label: "Export open meshes", advice: "On for models with open surfaces." },
      { label: "Use Draco compression", advice: "Off. Valora3D's preview does not decode Draco." },
      { label: "SubD Meshing", advice: "Raise the subdivision level if SubD objects look faceted in the export." },
    ],
    pitfalls: [
      "NURBS surfaces are exported using the document's render mesh settings. If curved surfaces look faceted, raise the render mesh quality before exporting.",
      "Curves don't export unless they have piping applied.",
      "Rhino's help doesn't describe unit conversion, so model in meters where you can and confirm the size with the checker.",
    ],
  },
  {
    slug: "export-glb-from-unreal-engine",
    app: "Unreal Engine",
    vendor: "Epic Games",
    title: "Export a .glb from Unreal Engine",
    summary: "Export an asset, a level or selected actors from Unreal Engine to a self-contained .glb with baked materials and meter scale.",
    appliesTo: "Unreal Engine 5.4 and later, per Epic's glTF export documentation.",
    vendorDomains: ["epicgames.com", "unrealengine.com"],
    sources: [
      { label: "Unreal Engine: Exporting content to glTF", url: "https://dev.epicgames.com/documentation/en-us/unreal-engine/exporting-unreal-engine-content-to-gltf" },
      { label: "Unreal Engine: How the glTF exporter handles content", url: "https://dev.epicgames.com/documentation/en-us/unreal-engine/how-the-gltf-exporter-handles-unreal-engine-content" },
    ],
    steps: [
      "Choose what to export: right-click an asset in the Content Browser and pick Asset Actions > Export…, or use File > Export Selected… for actors in the level (File > Export All… exports the whole level).",
      "Set Save as type to .glb. Epic describes .glb as combining the scene description, binary data and textures into one self-contained file.",
      "In glTF Export Options, keep Export Uniform Scale at its default of 0.01, which converts Unreal's centimeters to glTF's meters.",
      "Set Bake Material Inputs so material graphs are baked to textures, and set Texture Image Format to PNG or JPEG.",
      "Leave Use Mesh Quantization off, and turn off Export Lights and Export Cameras.",
      CHECK_STEP,
    ],
    settings: [
      { label: "Export Uniform Scale", advice: "0.01 (the default), so the model comes out in meters." },
      { label: "Bake Material Inputs", advice: "Simple or Use Mesh Data, so complex materials survive as textures." },
      { label: "Texture Image Format", advice: "PNG or JPEG. None leaves the textures out." },
      { label: "Use Mesh Quantization", advice: "Off. Epic notes it may stop the mesh loading in some glTF viewers." },
    ],
    pitfalls: [
      "Only the Default Lit, Clear Coat and Unlit shading models are supported; others are exported as Default Lit.",
      "Specular isn't supported, so very glossy materials may look different after export.",
      "Only one LOD is exported, and collision geometry is left out. Export the highest-quality LOD.",
    ],
  },
  {
    slug: "export-glb-from-unity",
    app: "Unity",
    vendor: "Unity Technologies",
    title: "Export a .glb from Unity",
    summary: "Install Unity's glTFast package and export a scene, prefab or GameObject from the editor as a single glTF-Binary file.",
    appliesTo: "Unity 6 (6000.0) and later with the Unity glTFast package, per the package documentation.",
    vendorDomains: ["unity3d.com", "unity.com"],
    sources: [
      { label: "Unity glTFast: Editor export", url: "https://docs.unity3d.com/Packages/com.unity.cloud.gltfast@6.19/manual/ExportEditor.html" },
      { label: "Unity glTFast: Installation", url: "https://docs.unity3d.com/Packages/com.unity.cloud.gltfast@6.19/manual/installation.html" },
      { label: "Unity glTFast: Features", url: "https://docs.unity3d.com/Packages/com.unity.cloud.gltfast@6.19/manual/features.html" },
    ],
    steps: [
      "Install the package: open the Package Manager, choose Add package by name and enter com.unity.cloud.gltfast.",
      "Select what to export in the Hierarchy or Project window.",
      "Use File > Export Scene, GameObject > Export glTF, or Assets > Export glTF, and choose the glTF-Binary (.glb) option, which writes one .glb with all buffers and textures.",
      "Save the file.",
      CHECK_STEP,
    ],
    settings: [
      { label: "Format", advice: "glTF-Binary (.glb), not glTF (.gltf), which writes separate files." },
      { label: "Draco compression", advice: "Leave it off. It is only available through scripting with the separate Draco for Unity package." },
    ],
    pitfalls: [
      "Material export depends on the shader. URP and HDRP Lit and Unlit and the Built-In Standard and Unlit shaders are supported; other shaders may export only partly.",
      "glTFast works with at most two UV sets, and vertex attributes the materials don't use (such as unused vertex colors) are dropped.",
      "The package needs Unity 6 or newer. Older editors need an older glTFast release; see its documentation for your version.",
    ],
  },
];

export function guideBySlug(slug: string): Guide | undefined {
  return GUIDES.find((g) => g.slug === slug);
}
