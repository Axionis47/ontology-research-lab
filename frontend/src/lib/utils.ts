import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
export function label(value: unknown): string {
  return String(value ?? "")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/_/g, " ")
    .replace(/^./, (c) => c.toUpperCase());
}
export function short(value: string | null | undefined): string {
  return value ? value.slice(0, 10) : "Not recorded";
}
export function object(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}
export function array(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value)
    ? value.filter((v) => v && typeof v === "object")
    : [];
}
export function display(value: unknown): string {
  return typeof value === "string"
    ? value
    : (JSON.stringify(value, null, 2) ?? "Not recorded");
}
export function money(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(value);
}
export function cursorCompare(a: string, b: string): number {
  const aa = BigInt(a),
    bb = BigInt(b);
  return aa < bb ? -1 : aa > bb ? 1 : 0;
}
