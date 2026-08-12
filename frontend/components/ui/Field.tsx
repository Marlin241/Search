import { forwardRef, type InputHTMLAttributes, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";

const fieldClassName =
  "rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-900 focus:outline-none dark:border-ink-800 dark:bg-ink-900 dark:text-slate-50 dark:placeholder:text-slate-500 dark:focus:border-slate-50";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className = "", ...props }, ref) => <input ref={ref} className={`${fieldClassName} ${className}`} {...props} />
);
Input.displayName = "Input";

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className = "", ...props }, ref) => (
    <textarea ref={ref} className={`${fieldClassName} ${className}`} {...props} />
  )
);
Textarea.displayName = "Textarea";

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className = "", ...props }, ref) => <select ref={ref} className={`${fieldClassName} ${className}`} {...props} />
);
Select.displayName = "Select";
