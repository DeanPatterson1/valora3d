import { create } from "zustand";
import { services } from "@/lib/services";
import type { Project } from "@/lib/schema";
import type { ServiceError } from "@/lib/services";

type ProjectsState = {
  projects: Project[];
  versionCounts: Record<string, number>;
  loaded: boolean;
  error: ServiceError | null;
  refresh: () => Promise<void>;
  create: (name: string) => Promise<Project | null>;
  rename: (id: string, name: string) => Promise<void>;
  remove: (id: string) => Promise<void>;
};

export const useProjectsStore = create<ProjectsState>((set, get) => ({
  projects: [], versionCounts: {}, loaded: false, error: null,
  refresh: async () => {
    const r = await services.projects.listProjects();
    if (!r.ok) { set({ error: r.error, loaded: true }); return; }
    const counts: Record<string, number> = {};
    await Promise.all(r.value.map(async (p) => { const v = await services.projects.listVersions(p.id); counts[p.id] = v.ok ? v.value.length : 0; }));
    set({ projects: r.value, versionCounts: counts, loaded: true, error: null });
  },
  create: async (name) => {
    const r = await services.projects.createProject(name);
    if (!r.ok) { set({ error: r.error }); return null; }
    await get().refresh();
    return r.value;
  },
  rename: async (id, name) => { await services.projects.updateProject(id, { name }); await get().refresh(); },
  remove: async (id) => { await services.projects.deleteProject(id); await get().refresh(); },
}));
