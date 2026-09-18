// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Project } from "@/lib/schema";
import { useAuthStore } from "@/lib/stores/auth";
import { useCreditsStore } from "@/lib/stores/credits";
import { useProjectsStore } from "@/lib/stores/projects";
import { services } from "@/lib/services";
import { ProfileScreen } from "./ProfileScreen";
import { initials } from "./Avatar";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

const now = Date.now();
function project(id: string, name: string, updatedAt: number): Project {
  return { id, name, createdAt: updatedAt, updatedAt, assetId: null, analysis: null, selectedVersionId: null };
}

beforeEach(async () => {
  localStorage.clear();
  await services.auth.signUp("ada@example.com", "longenough", "Ada Lovelace");
  await useAuthStore.getState().refresh();
  useProjectsStore.setState({
    projects: [
      project("p1", "Coupe", now - 1000),
      project("p2", "Sneaker", now - 5000),
      project("p3", "Bottle", now - 9000),
      project("p4", "Sedan", now - 13000),
      project("p5", "Lamp", now - 17000),
      project("p6", "Old one", now - 21000),
    ],
    versionCounts: { p1: 3, p2: 1, p3: 0, p4: 2, p5: 0, p6: 4 },
    loaded: true,
    error: null,
  });
  useCreditsStore.setState({
    balance: 91,
    ledger: [
      { id: "t1", amount: 100, reason: "starting_balance", projectId: null, createdAt: now - 30000 },
      { id: "t2", amount: -2, reason: "scene_generation", projectId: "p1", createdAt: now - 20000 },
      { id: "t3", amount: -1, reason: "prompt_edit", projectId: "p1", createdAt: now - 10000 },
      { id: "t4", amount: -6, reason: "scene_generation", projectId: "p2", createdAt: now - 5000 },
    ],
    loaded: true,
    error: null,
  });
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("ProfileScreen", () => {
  it("renders the real counts from the stores", () => {
    render(<ProfileScreen />);
    const usage = screen.getByRole("group", { name: "Usage" });
    const stat = (label: string) => within(usage).getByText(label).previousElementSibling?.textContent;
    expect(stat("Projects")).toBe("6");
    expect(stat("Scene versions")).toBe("10");
    expect(stat("Credits left")).toBe("91");
    expect(stat("Credits spent")).toBe("9");
  });

  it("lists the five most recent projects with links", () => {
    render(<ProfileScreen />);
    const list = screen.getByRole("list");
    const links = within(list).getAllByRole("link");
    expect(links.map((l) => l.firstElementChild?.textContent)).toEqual(["Coupe", "Sneaker", "Bottle", "Sedan", "Lamp"]);
    expect(links[0]?.textContent).toContain("3 versions");
    expect(links[0]?.getAttribute("href")).toBe("/projects/p1");
    expect(screen.queryByText("Old one")).toBeNull();
  });

  it("shows avatar initials, email and plan", () => {
    render(<ProfileScreen />);
    expect(screen.getByText("AL")).toBeTruthy();
    expect(screen.getByText("ada@example.com")).toBeTruthy();
    expect(screen.getByText("Free")).toBeTruthy();
  });

  it("edits the name inline and persists it", async () => {
    render(<ProfileScreen />);
    fireEvent.click(screen.getByRole("button", { name: "Edit name" }));
    const input = screen.getByLabelText("Name");
    fireEvent.change(input, { target: { value: " " } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(screen.getByText("Enter your name.")).toBeTruthy();
    fireEvent.change(input, { target: { value: "Grace Hopper" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Grace Hopper" })).toBeTruthy());
    const cur = await services.auth.current();
    expect(cur.ok && cur.value?.name).toBe("Grace Hopper");
    expect(screen.getByText("GH")).toBeTruthy();
  });
});

describe("initials", () => {
  it("takes first and last initials", () => {
    expect(initials("Ada Lovelace")).toBe("AL");
    expect(initials("Guest")).toBe("G");
    expect(initials("  ")).toBe("?");
    expect(initials("mary ann evans")).toBe("ME");
  });
});
