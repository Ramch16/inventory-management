import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const alertVariants = cva("relative w-full rounded-lg border p-4 text-sm", {
  variants: {
    variant: {
      default: "bg-card text-card-foreground",
      info: "border-primary/30 bg-primary/5 text-foreground",
      warning: "border-warning/40 bg-warning/10 text-foreground",
      destructive: "border-destructive/40 bg-destructive/10 text-foreground",
      success: "border-success/40 bg-success/10 text-foreground",
    },
  },
  defaultVariants: { variant: "default" },
});

export interface AlertProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof alertVariants> {}

const Alert = React.forwardRef<HTMLDivElement, AlertProps>(
  ({ className, variant, ...props }, ref) => (
    <div ref={ref} role="alert" className={cn(alertVariants({ variant }), className)} {...props} />
  ),
);
Alert.displayName = "Alert";

const AlertTitle = ({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) => (
  <h5 className={cn("mb-1 font-medium leading-none tracking-tight", className)} {...props} />
);

const AlertDescription = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("text-sm text-muted-foreground [&_p]:leading-relaxed", className)} {...props} />
);

export { Alert, AlertDescription, AlertTitle };
