import { Dialog as SheetPrimitive } from "@base-ui/react/dialog";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

function Sheet(props: SheetPrimitive.Root.Props) {
  return <SheetPrimitive.Root {...props} />;
}

function SheetTrigger(props: SheetPrimitive.Trigger.Props) {
  return <SheetPrimitive.Trigger {...props} />;
}

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
      <SheetPrimitive.Backdrop className="fixed inset-0 z-50 bg-black/50 transition-opacity data-[starting-style]:opacity-0 data-[ending-style]:opacity-0" />
      <SheetPrimitive.Popup
        className={cn(
          "fixed inset-y-0 z-50 flex w-72 max-w-[85vw] flex-col overflow-y-auto bg-background shadow-lg transition-transform duration-200",
          SIDE_CLS[side],
          className,
        )}
        {...props}
      >
        {children}
        <SheetPrimitive.Close className="absolute right-3 top-4 rounded-sm p-0.5 text-muted-foreground opacity-70 transition-opacity hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          <X className="size-4" />
        </SheetPrimitive.Close>
      </SheetPrimitive.Popup>
    </SheetPrimitive.Portal>
  );
}

function SheetTitle({ className, ...props }: SheetPrimitive.Title.Props) {
  return <SheetPrimitive.Title className={cn("text-base font-semibold", className)} {...props} />;
}

export { Sheet, SheetContent, SheetTitle, SheetTrigger };
