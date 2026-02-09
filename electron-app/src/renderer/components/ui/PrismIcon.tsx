import React from 'react';
import { cn } from "../../lib/utils";

interface PrismIconProps {
  className?: string;
}

export function PrismIcon({ className }: PrismIconProps) {
  return (
    <svg 
      viewBox="0 0 24 24" 
      fill="none" 
      xmlns="http://www.w3.org/2000/svg"
      className={cn("w-6 h-6", className)}
    >
      <path 
        d="M12 3L2 21H22L12 3Z" 
        fill="url(#prism_main_gradient_electron)"
      />
      <path 
        d="M12 3L22 21L12 13L2 21L12 3Z" 
        fill="white" 
        fillOpacity="0.15"
      />
      <path 
        d="M12 3L12 13" 
        stroke="white" 
        strokeWidth="0.5" 
        strokeOpacity="0.3"
      />
          <defs>
            <linearGradient id="prism_main_gradient_electron" x1="2" y1="21" x2="22" y2="3" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="#4285F4" />
              <stop offset="33%" stopColor="#EA4335" />
              <stop offset="66%" stopColor="#FBBC05" />
              <stop offset="100%" stopColor="#34A853" />
            </linearGradient>
          </defs>
    </svg>
  );
}
