import { toast } from "sonner";

export function notifyGenerationSuccess(message: string) {
  toast.success(message);
}

export function notifyGenerationError(message: string) {
  toast.error(message);
}
