import { describe, it, expect } from "vitest";
import { WORDS, SHOT_WORDS, parseOutputMentions } from "./vocabulary";

describe("WORDS", () => {
  it("city includes downtown and plural cities but not 'street' inside a word", () => {
    expect(WORDS.city.test("downtown at night")).toBe(true);
    expect(WORDS.city.test("through the cities")).toBe(true);
    expect(WORDS.city.test("streetwise")).toBe(false);
  });
  it("road includes mountain and plural highways", () => {
    expect(WORDS.road.test("mountain pass")).toBe(true);
    expect(WORDS.road.test("on the highways")).toBe(true);
    expect(WORDS.road.test("roadster")).toBe(false);
  });
  it("rain matches inflections but not 'train' or 'brain'", () => {
    for (const w of ["rain", "rainy", "raining", "rains"]) expect(WORDS.rain.test(w), w).toBe(true);
    expect(WORDS.rain.test("train")).toBe(false);
    expect(WORDS.rain.test("brain")).toBe(false);
  });
  it("time words", () => {
    expect(WORDS.night.test("2am")).toBe(true);
    expect(WORDS.dusk.test("golden hour")).toBe(true);
    expect(WORDS.day.test("daytime")).toBe(true);
    expect(WORDS.day.test("today")).toBe(false);
  });
  it("studio white is only the adjacent phrase", () => {
    expect(WORDS.studioWhite.test("white studio")).toBe(true);
    expect(WORDS.studioWhite.test("studio white")).toBe(true);
    expect(WORDS.studioWhite.test("studio with a white car")).toBe(false);
    expect(WORDS.studio.test("studio with a white car")).toBe(true);
  });
  it("camera style words", () => {
    expect(WORDS.handheld.test("hand-held")).toBe(true);
    expect(WORDS.smooth.test("steady cam")).toBe(true);
    expect(WORDS.fog.test("haze")).toBe(true);
  });
});

describe("SHOT_WORDS", () => {
  it("covers inflections", () => {
    expect(SHOT_WORDS.orbit.test("circling")).toBe(true);
    expect(SHOT_WORDS.pushIn.test("push-in")).toBe(true);
    expect(SHOT_WORDS.tracking.test("track")).toBe(true);
    expect(SHOT_WORDS.walkToward.test("walking towards")).toBe(true);
  });
});

describe("parseOutputMentions", () => {
  it("returns nothing for an unrelated prompt", () => {
    expect(parseOutputMentions("make it darker")).toEqual({});
  });
  it("rounds duration to the nearest offered length (8/10/12)", () => {
    expect(parseOutputMentions("12 seconds")).toEqual({ durationS: 12 });
    expect(parseOutputMentions("8 sec")).toEqual({ durationS: 8 });
    expect(parseOutputMentions("10 sec")).toEqual({ durationS: 10 });
    expect(parseOutputMentions("100s")).toEqual({ durationS: 12 });
    expect(parseOutputMentions("1 s")).toEqual({ durationS: 8 });
  });
  it("maps size words to the tier that renders nearest, never beyond 1080p", () => {
    expect(parseOutputMentions("4k at 60 fps")).toEqual({ tier: "final" });
    expect(parseOutputMentions("8K UHD")).toEqual({ tier: "final" });
    expect(parseOutputMentions("1080p")).toEqual({ tier: "final" });
    expect(parseOutputMentions("1440")).toEqual({ tier: "final" });
    expect(parseOutputMentions("2160p")).toEqual({ tier: "final" });
    expect(parseOutputMentions("720p 24fps")).toEqual({ tier: "preview" });
    expect(parseOutputMentions("540p")).toEqual({ tier: "preview" });
  });
  it("reads the format", () => {
    expect(parseOutputMentions("vertical for tiktok")).toEqual({ aspect: "9:16" });
    expect(parseOutputMentions("9:16")).toEqual({ aspect: "9:16" });
    expect(parseOutputMentions("widescreen 16:9")).toEqual({ aspect: "16:9" });
    expect(parseOutputMentions("landscape")).toEqual({ aspect: "16:9" });
  });
  it("does not confuse fps or shot counts with duration", () => {
    expect(parseOutputMentions("30 fps")).toEqual({});
    expect(parseOutputMentions("2 shots")).toEqual({});
  });
});
