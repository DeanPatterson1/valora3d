"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button, Dialog, Field, useToastStore } from "@/components/ui";
import { useProjectsStore } from "@/lib/stores/projects";

const DEFAULT_NAME = "Untitled project";

export type NewProjectDialogProps = {
  open: boolean;
  onClose: () => void;
};

export function NewProjectDialog({ open, onClose }: NewProjectDialogProps) {
  const router = useRouter();
  const create = useProjectsStore((s) => s.create);
  const [name, setName] = useState(DEFAULT_NAME);
  const [busy, setBusy] = useState(false);

  // The dialog element persists between opens, so the field resets on close.
  const close = () => {
    setName(DEFAULT_NAME);
    setBusy(false);
    onClose();
  };

  const submit = async () => {
    if (busy) return;
    const trimmed = name.trim() || DEFAULT_NAME;
    setBusy(true);
    const project = await create(trimmed);
    if (!project) {
      setBusy(false);
      const err = useProjectsStore.getState().error;
      useToastStore.getState().push({ kind: "danger", message: err?.message ?? "Could not create the project." });
      return;
    }
    close();
    router.push(`/projects/${project.id}`);
  };

  return (
    <Dialog
      open={open}
      onClose={() => {
        if (!busy) close();
      }}
      title="New project"
      footer={
        <>
          <Button variant="ghost" onClick={close} disabled={busy}>
            Cancel
          </Button>
          <Button variant="primary" form="new-project-form" type="submit" loading={busy}>
            Create
          </Button>
        </>
      }
    >
      <form
        id="new-project-form"
        onSubmit={(e) => {
          e.preventDefault();
          void submit();
        }}
      >
        <Field
          label="Name"
          value={name}
          autoFocus
          maxLength={80}
          onChange={(e) => setName(e.target.value)}
          onFocus={(e) => e.target.select()}
        />
      </form>
    </Dialog>
  );
}
