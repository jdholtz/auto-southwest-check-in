import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold",
  {
    variants: {
      variant: {
        default: "bg-gray-100 text-gray-800",
        pending: "bg-gray-100 text-gray-600",
        scheduled: "bg-blue-100 text-blue-700",
        checking_in: "bg-yellow-100 text-yellow-700",
        success: "bg-green-100 text-green-700",
        failed: "bg-red-100 text-red-700",
        active: "bg-green-100 text-green-700",
        inactive: "bg-gray-100 text-gray-500",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
