import { Dialog as SheetPrimitive } from "@base-ui/react/dialog";
import { cn } from "@/lib/utils";
import { DialogBackdrop, DialogCloseButton } from "./dialog";

const SIDE_CLS = {
  left: "left-0 border-r data-[starting-style]:-translate-x-full data-[ending-style]:-translate-x-full",
  right:
    "right-0 border-l data-[starting-style]:translate-x-full data-[ending-style]:translate-x-full",
} as const;

/** Off-canvas panel sliding in from one edge of the viewport. */
function SheetContent({
  className,
  children,
  side = "right",
  ...props
}: SheetPrimitive.Popup.Props & { side?: keyof typeof SIDE_CLS }) {
  return (
    <SheetPrimitive.Portal>
      <DialogBackdrop />
      <SheetPrimitive.Popup
        className={cn(
          "fixed inset-y-0 z-50 flex w-72 max-w-[85vw] flex-col overflow-y-auto bg-background shadow-lg transition-transform duration-200",
          SIDE_CLS[side],
          className,
        )}
        {...props}
      >
        {children}
        <DialogCloseButton />
      </SheetPrimitive.Popup>
    </SheetPrimitive.Portal>
  );
}

export {
  Dialog as Sheet,
  DialogTitle as SheetTitle,
  DialogTrigger as SheetTrigger,
} from "./dialog";
export { SheetContent };
