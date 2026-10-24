import { useLocation } from "@tanstack/react-router";
import { Menu } from "lucide-react";
import { type ReactNode, useState } from "react";
import { useTranslation } from "react-i18next";
import { buttonVariants } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";

/** Menu button opening a navigation drawer, which closes once the route changes. */
export function NavSheet({
  side,
  className,
  titleClassName,
  children,
}: {
  side: "left" | "right";
  className?: string;
  titleClassName?: string;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  const pathname = useLocation({ select: (l) => l.pathname });
  const [openedOn, setOpenedOn] = useState<string | null>(null);
  const label = t("nav.menu", { defaultValue: "Menu" });

  return (
    <Sheet
      open={openedOn === pathname}
      onOpenChange={(open) => setOpenedOn(open ? pathname : null)}
    >
      <SheetTrigger className={buttonVariants({ variant: "ghost", size: "icon" })}>
        <Menu />
        <span className="sr-only">{label}</span>
      </SheetTrigger>
      <SheetContent side={side} className={className}>
        <SheetTitle className={titleClassName}>{label}</SheetTitle>
        {children}
      </SheetContent>
    </Sheet>
  );
}
