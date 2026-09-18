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
  it("rounds duration to the nearest of 5/10/15/30", () => {
    expect(parseOutputMentions("12 seconds")).toEqual({ durationS: 10 });
    expect(parseOutputMentions("13 sec")).toEqual({ durationS: 15 });
    expect(parseOutputMentions("100s")).toEqual({ durationS: 30 });
    expect(parseOutputMentions("1 s")).toEqual({ durationS: 5 });
  });
  it("reads resolution and fps", () => {
    expect(parseOutputMentions("4k at 60 fps")).toEqual({ resolution: "4k", fps: 60 });
    expect(parseOutputMentions("1080p")).toEqual({ resolution: "1080p" });
    expect(parseOutputMentions("1440")).toEqual({ resolution: "1440p" });
    expect(parseOutputMentions("720p 24fps")).toEqual({ resolution: "720p", fps: 24 });
  });
  it("does not confuse fps or shot counts with duration", () => {
    expect(parseOutputMentions("30 fps")).toEqual({ fps: 30 });
    expect(parseOutputMentions("2 shots")).toEqual({});
  });
});
