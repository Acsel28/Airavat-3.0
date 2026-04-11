import React from "react";

export function Panel({ children, className = "" }) {
  return <div className={`panel-dark rounded-3xl ${className}`}>{children}</div>;
}

export function Chip({ children, className = "" }) {
  return <div className={`chip-dark rounded-full px-3 py-2 ${className}`}>{children}</div>;
}

export function Title({ children, className = "" }) {
  return (
    <h3 className={`text-sm font-semibold tracking-wide uppercase text-slate-200 ${className}`}>
      {children}
    </h3>
  );
}

