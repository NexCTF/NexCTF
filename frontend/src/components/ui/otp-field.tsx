import { OTPFieldPreview as OTPField } from "@base-ui/react/otp-field";
import type * as React from "react";

import { cn } from "@/lib/utils";

function OtpFieldRoot({ className, ...props }: React.ComponentProps<typeof OTPField.Root>) {
  return (
    <OTPField.Root
      data-slot="otp-field"
      className={cn("flex items-center gap-2", className)}
      {...props}
    />
  );
}

function OtpFieldInput({ className, ...props }: React.ComponentProps<typeof OTPField.Input>) {
  return (
    <OTPField.Input
      data-slot="otp-field-input"
      className={cn(
        "h-10 w-10 rounded-lg border border-input bg-transparent text-center text-base font-mono transition-colors outline-none",
        "focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50",
        "data-[active]:border-ring data-[active]:ring-3 data-[active]:ring-ring/50",
        "disabled:pointer-events-none disabled:opacity-50",
        "aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20",
        "dark:bg-input/30",
        className,
      )}
      {...props}
    />
  );
}

function OtpFieldSeparator({
  className,
  ...props
}: React.ComponentProps<typeof OTPField.Separator>) {
  return (
    <OTPField.Separator
      data-slot="otp-field-separator"
      className={cn("text-muted-foreground select-none", className)}
      {...props}
    >
      –
    </OTPField.Separator>
  );
}

export { OtpFieldInput, OtpFieldRoot, OtpFieldSeparator };
