// SPDX-License-Identifier: Apache-2.0

/** Shown whenever any stage runs on the fake engine (no credentials). */
export function DryRunBadge() {
  return (
    <p
      role="status"
      className="inline-flex items-center gap-2 rounded-md border border-line bg-surface-raised px-3 py-1.5 text-sm font-semibold"
    >
      <span aria-hidden="true" className="inline-block h-2.5 w-2.5 rounded-full bg-[#f59e0b]" />
      Dry run · simulated captions, no API key
    </p>
  );
}
