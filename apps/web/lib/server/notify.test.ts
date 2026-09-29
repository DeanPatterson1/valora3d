import { describe, expect, it, vi } from "vitest";
import { NOTIFICATION_SETTINGS_PATH, ResendNotifier, renderReadyEmail, type RenderMailContext } from "./notify";

const CONFIG = { resendApiKey: "re_key", from: "Valora3D <renders@valora3d.com>" };
const ctx: RenderMailContext = {
  email: "a@example.com",
  name: "Ann",
  projectId: "p1",
  projectName: "Coupe <v2>",
  emailRenderReady: true,
  posterUrl: "https://r2.example/poster.jpg?X-Amz-Signature=abc&x=1",
  kind: "final",
};

describe("render-ready mail (branded)", () => {
  it("has the poster, a View render link and an off switch, in both parts", () => {
    const mail = renderReadyEmail(ctx, "https://valora3d.com");
    expect(mail.html).toContain('src="https://r2.example/poster.jpg?X-Amz-Signature=abc&amp;x=1"');
    expect(mail.html).toContain(">View render</a>");
    expect(mail.html).toContain('href="https://valora3d.com/projects/p1"');
    expect(mail.html).toContain(`href="https://valora3d.com${NOTIFICATION_SETTINGS_PATH}"`);
    expect(mail.html).toContain("Coupe &lt;v2&gt;");
    expect(mail.html).not.toContain("<v2>");
    expect(mail.html).toContain('role="presentation"');
    expect(mail.text).toContain("View it: https://valora3d.com/projects/p1");
    expect(mail.text).toContain(`Turn them off in Settings: https://valora3d.com${NOTIFICATION_SETTINGS_PATH}`);
    expect(mail.text).not.toMatch(/<(strong|a|p|table|img)\b/);
  });

  it("works without a poster", () => {
    const mail = renderReadyEmail({ ...ctx, posterUrl: null }, "https://valora3d.com");
    expect(mail.html.replace(/<!--[\s\S]*?-->/g, "")).not.toContain("<img");
  });
});

describe("render-ready preference", () => {
  it("sends when the user left it on (or it is unset)", async () => {
    for (const pref of [true, undefined]) {
      const fetchImpl = vi.fn(async () => Response.json({ id: "m" }));
      const n = new ResendNotifier(CONFIG, async () => ({ ...ctx, emailRenderReady: pref }), fetchImpl as unknown as typeof fetch);
      await n.notifyRenderReady("u", "j");
      expect(fetchImpl).toHaveBeenCalledTimes(1);
      const body = JSON.parse(String((fetchImpl.mock.calls[0] as unknown as [string, RequestInit])[1].body));
      expect(body.text).toContain("View it:");
      expect(body.html).toContain("View render");
    }
  });

  it("sends nothing when the user turned it off in Settings", async () => {
    const fetchImpl = vi.fn();
    const n = new ResendNotifier(CONFIG, async () => ({ ...ctx, emailRenderReady: false }), fetchImpl as unknown as typeof fetch);
    await n.notifyRenderReady("u", "j");
    expect(fetchImpl).not.toHaveBeenCalled();
  });
});
