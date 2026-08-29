"use client";

import React from "react";

export function CvEditorSplitScreen({
  form,
  preview,
}: {
  form: React.ReactNode;
  preview: React.ReactNode;
}) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
      <div className="space-y-6">{form}</div>
      <div className="lg:sticky lg:top-6 h-[75vh]">{preview}</div>
    </div>
  );
}
