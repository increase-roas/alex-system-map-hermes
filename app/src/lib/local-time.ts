/** Show a stored UTC time in the viewer's own clock (Alex, 2026-10-14: "catalog sync was on 10-14??" when it was still
 * 10-13 for him). The raw UTC string stays available for a title tooltip. Unparseable input is returned unchanged. */
export function localTime(iso: string | null | undefined): string {
  if (!iso) return 'unknown';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZoneName: 'short' }).format(d);
}
