import { describe, expect, it } from "vitest";
import * as THREE from "three";
import { assignNodeIds, buildOutline, findNode, meshIdsUnder, nodeId } from "./meshTree";
import { NO_EDITS, applyEdits, deleteNode, isEmpty, setNodeHidden, splitNode } from "./meshEdits";

/** Root > Body(group) > [Shell(mesh), Trim(mesh)], Wheels(group) > Wheel(mesh with two islands). */
function car(): THREE.Object3D {
  const root = new THREE.Group();
  root.name = "Car";

  const body = new THREE.Group();
  body.name = "Body";
  const shell = new THREE.Mesh(new THREE.BoxGeometry(4, 1, 2));
  shell.name = "Shell";
  const trim = new THREE.Mesh(new THREE.BoxGeometry(0.2, 0.2, 2));
  trim.name = "Trim";
  body.add(shell, trim);

  const wheels = new THREE.Group();
  wheels.name = "Wheels";
  const pair = new THREE.Mesh(twoDisjointBoxes());
  pair.name = "WheelPair";
  wheels.add(pair);

  root.add(body, wheels);
  assignNodeIds(root);
  return root;
}

function twoDisjointBoxes(): THREE.BufferGeometry {
  const parts = [new THREE.BoxGeometry(1, 1, 1).translate(-4, 0, 0), new THREE.BoxGeometry(1, 1, 1).translate(4, 0, 0)];
  const positions: number[] = [];
  for (const part of parts) {
    const flat = part.toNonIndexed();
    const position = flat.getAttribute("position");
    for (let i = 0; i < position.count; i++) positions.push(position.getX(i), position.getY(i), position.getZ(i));
  }
  const merged = new THREE.BufferGeometry();
  merged.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  return merged;
}

describe("node ids", () => {
  it("are the child-index path from the root", () => {
    const root = car();
    expect(nodeId(root)).toBe("root");
    expect(nodeId(root.children[0])).toBe("0");
    expect(nodeId(root.children[0].children[1])).toBe("0/1");
  });

  it("are reproduced identically by a second load of the same shape", () => {
    const ids = (root: THREE.Object3D) => {
      const out: string[] = [];
      root.traverse((o) => out.push(nodeId(o) ?? "?"));
      return out;
    };
    expect(ids(car())).toEqual(ids(car()));
  });

  it("resolve back to their node", () => {
    const root = car();
    expect(findNode(root, "0/1")?.name).toBe("Trim");
    expect(findNode(root, "nope")).toBeNull();
  });
});

describe("buildOutline", () => {
  it("lists the groups and their meshes", () => {
    const outline = buildOutline(car());
    expect(outline.map((n) => n.name)).toEqual(["Body", "Wheels"]);
    expect(outline[0].children.map((n) => n.name)).toEqual(["Shell", "Trim"]);
    expect(outline[0].kind).toBe("group");
    expect(outline[0].children[0].kind).toBe("mesh");
  });

  it("sums triangles up the tree", () => {
    const outline = buildOutline(car());
    const body = outline[0];
    expect(body.triangles).toBe(body.children[0].triangles + body.children[1].triangles);
  });

  it("drops transform nodes that hold no mesh", () => {
    const root = car();
    root.add(new THREE.Group());
    assignNodeIds(root);
    expect(buildOutline(root)).toHaveLength(2);
  });
});

describe("splitNode", () => {
  it("replaces a mesh with one child per island", () => {
    const root = car();
    const outcome = splitNode(root, "1/0");
    expect(outcome.ok).toBe(true);
    expect(outcome.ok && outcome.parts).toBe(2);
    const group = findNode(root, "1/0")!;
    expect(group.children).toHaveLength(2);
    expect(nodeId(group.children[0])).toBe("1/0#0");
  });

  it("refuses a mesh that is already one island", () => {
    expect(splitNode(car(), "0/0")).toEqual({ ok: false, reason: "single_island" });
  });

  it("refuses a group", () => {
    expect(splitNode(car(), "0")).toEqual({ ok: false, reason: "not_a_mesh" });
  });
});

describe("deleteNode", () => {
  it("removes the node from its parent", () => {
    const root = car();
    expect(deleteNode(root, "0/0")).not.toBeNull();
    expect(findNode(root, "0/0")).toBeNull();
    expect(findNode(root, "0")?.children).toHaveLength(1);
  });

  it("puts the node back, in place, on revert", () => {
    const root = car();
    const step = deleteNode(root, "0/0")!;
    step.revert();
    expect(findNode(root, "0/0")?.name).toBe("Shell");
    expect(findNode(root, "0")!.children.map((c) => c.name)).toEqual(["Shell", "Trim"]);
  });

  it("removes a whole group", () => {
    const root = car();
    deleteNode(root, "0");
    expect(meshIdsUnder(root, "root")).toEqual(["1/0"]);
  });

  it("refuses the root", () => {
    const root = car();
    expect(deleteNode(root, "root")).toBeNull();
  });
});

describe("applyEdits", () => {
  it("is a no-op with no edits", () => {
    const root = car();
    applyEdits(root, NO_EDITS);
    expect(meshIdsUnder(root, "root")).toEqual(["0/0", "0/1", "1/0"]);
  });

  it("replays a split followed by a delete of one island", () => {
    const root = car();
    applyEdits(root, { split: ["1/0"], deleted: ["1/0#1"], hidden: [] });
    expect(findNode(root, "1/0#1")).toBeNull();
    expect(findNode(root, "1/0#0")).not.toBeNull();
  });

  it("splits parents before their islands regardless of array order", () => {
    const root = car();
    applyEdits(root, { split: ["1/0"], deleted: [], hidden: [] });
    const nested = splitNode(root, "1/0#0");
    expect(nested.ok).toBe(false);
  });

  it("restores a split mesh on revert", () => {
    const root = car();
    const outcome = splitNode(root, "1/0");
    expect(outcome.ok).toBe(true);
    if (outcome.ok) outcome.undo.revert();
    expect(findNode(root, "1/0")!.children).toHaveLength(0);
    expect((findNode(root, "1/0") as THREE.Mesh).isMesh).toBe(true);
  });

  it("hides without deleting", () => {
    const root = car();
    applyEdits(root, { split: [], deleted: [], hidden: ["0/0"] });
    expect(findNode(root, "0/0")!.visible).toBe(false);
    expect(findNode(root, "0/1")!.visible).toBe(true);
  });

  it("skips ids a delete has already removed", () => {
    const root = car();
    expect(() => applyEdits(root, { split: ["0/0"], deleted: ["0", "0/1"], hidden: ["0/0"] })).not.toThrow();
    expect(findNode(root, "0")).toBeNull();
  });

  it("toggles visibility without touching the tree", () => {
    const root = car();
    expect(setNodeHidden(root, "0/0", true)).toBe(true);
    expect(findNode(root, "0/0")!.visible).toBe(false);
    setNodeHidden(root, "0/0", false);
    expect(findNode(root, "0/0")!.visible).toBe(true);
    expect(setNodeHidden(root, "missing", true)).toBe(false);
  });

  it("reports an empty scene once every mesh is gone", () => {
    const root = car();
    expect(isEmpty(root)).toBe(false);
    applyEdits(root, { split: [], deleted: ["0", "1"], hidden: [] });
    expect(isEmpty(root)).toBe(true);
  });
});
