// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAuthStore } from "@/lib/stores/auth";
import { services } from "@/lib/services";
import { collectLocalData, SettingsScreen } from "./SettingsScreen";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace }),
}));

// jsdom has no <dialog> methods; mirror the open attribute so queries work.
beforeEach(async () => {
  const proto = HTMLDialogElement.prototype as HTMLDialogElement & { showModal?: () => void; close?: () => void };
  proto.showModal = function (this: HTMLDialogElement) {
    this.setAttribute("open", "");
  };
  proto.close = function (this: HTMLDialogElement) {
    this.removeAttribute("open");
    this.dispatchEvent(new Event("close"));
  };
  localStorage.clear();
  replace.mockClear();
  await services.auth.signUp("ada@example.com", "longenough", "Ada");
  await useAuthStore.getState().refresh();
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("SettingsScreen", () => {
  it("General shows honest fixed values, no fake controls", () => {
    render(<SettingsScreen />);
    expect(screen.getByText("Dark")).toBeTruthy();
    expect(screen.getByText("English")).toBeTruthy();
    expect(screen.queryByRole("switch")).toBeNull();
  });

  it("Rendering offers only what the worker renders: Preview 540p / Final 1080p and 9:16 / 16:9", async () => {
    render(<SettingsScreen initialSection="rendering" />);
    const quality = screen.getByRole("radiogroup", { name: "Default quality" });
    expect([...quality.querySelectorAll('[role="radio"]')].map((b) => b.textContent)).toEqual(["Preview 540p", "Final 1080p"]);
    expect(quality.querySelector('[aria-checked="true"]')?.textContent).toBe("Preview 540p");
    // Free has no Final renders, so it cannot be a default.
    expect((screen.getByRole("radio", { name: "Final 1080p" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByText(/4k|1440|720p|fps|frame rate/i)).toBeNull();

    const format = screen.getByRole("radiogroup", { name: "Default format" });
    fireEvent.click(screen.getByRole("radio", { name: "Landscape 16:9" }));
    await waitFor(() => expect(useAuthStore.getState().user?.prefs.defaultOutput.aspect).toBe("16:9"));
    const stored = await services.auth.current();
    expect(stored.ok && stored.value?.prefs.defaultOutput).toEqual({ tier: "preview", aspect: "16:9" });
    expect(format.querySelector('[aria-checked="true"]')?.textContent).toBe("Landscape 16:9");
  });

  it("Local renderer is unavailable at launch and Connect is disabled", () => {
    render(<SettingsScreen initialSection="local" />);
    expect(screen.getByText("Cloud rendering at launch")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Connect" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("Delete all asks first, then calls the service, signs out and goes to /login", async () => {
    const del = vi.spyOn(services.auth, "deleteAllData");
    render(<SettingsScreen initialSection="data" />);
    fireEvent.click(screen.getByRole("button", { name: "Delete all" }));
    expect(del).not.toHaveBeenCalled();
    const dialog = screen.getByRole("dialog");
    expect(dialog.getAttribute("open")).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Delete all data" }));
    await waitFor(() => expect(del).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
    expect(useAuthStore.getState().user).toBeNull();
    expect(localStorage.getItem("rs.users")).toBeNull();
  });

  it("Cancel closes the confirm without deleting", () => {
    const del = vi.spyOn(services.auth, "deleteAllData");
    render(<SettingsScreen initialSection="data" />);
    fireEvent.click(screen.getByRole("button", { name: "Delete all" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.getByRole("dialog", { hidden: true }).getAttribute("open")).toBeNull();
    expect(del).not.toHaveBeenCalled();
  });

  it("Account shows the email and plan, and Log out signs out", async () => {
    render(<SettingsScreen initialSection="account" />);
    expect(screen.getByText("ada@example.com")).toBeTruthy();
    expect(screen.getByText("Free")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Manage plan" }).getAttribute("href")).toBe("/pricing");
    fireEvent.click(screen.getByRole("button", { name: "Log out" }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
    expect(useAuthStore.getState().user).toBeNull();
    const cur = await services.auth.current();
    expect(cur.ok && cur.value).toBeNull();
  });
});

describe("collectLocalData", () => {
  it("gathers only rs.* keys, parsed", () => {
    localStorage.setItem("other", "1");
    localStorage.setItem("rs.raw", "not json");
    const data = collectLocalData();
    expect(Object.keys(data).every((k) => k.startsWith("rs."))).toBe(true);
    expect(Array.isArray(data["rs.users"])).toBe(true);
    expect(data["rs.raw"]).toBe("not json");
  });
});
