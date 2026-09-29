import { ogCard, OG_SIZE } from "@/lib/og";

export const alt = "Valora3D help center";
export const size = OG_SIZE;
export const contentType = "image/png";

export default function HelpOpenGraphImage() {
  return ogCard({ eyebrow: "Help", title: "Help center", lead: "Prepare your model, write a shot prompt and manage your renders." });
}
