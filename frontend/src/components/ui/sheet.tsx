import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { ReactNode } from "react";
export function Sheet({
  title,
  description,
  children,
  onClose,
  open,
}: {
  title: string;
  description?: string;
  children: ReactNode;
  onClose: () => void;
  open: boolean;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={(v) => !v && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="sheet-overlay" />
        <Dialog.Content className="sheet-content">
          <div className="sheet-header">
            <div>
              <Dialog.Title>{title}</Dialog.Title>
              <Dialog.Description>
                {description ?? "Recorded details and supporting evidence"}
              </Dialog.Description>
            </div>
            <Dialog.Close
              className="button button-ghost button-icon"
              aria-label="Close details"
            >
              <X size={18} />
            </Dialog.Close>
          </div>
          <div className="sheet-body">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
