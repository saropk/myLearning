// The eye-strain score (0..1) that drives the sclera's reddening.
// A well-paced long day stays near 0; marathons, skipped breaks, and
// late-night use push it up. Mirrors the suggestion engine's rules.

export function computeStrain(report) {
  if (!report) return 0.2;

  const longest = report.longestSession?.seconds ?? 0;
  const marathon = Math.min(longest / (3 * 3600), 1);

  const late = (report.hourly ?? [])
    .filter((h) => h.hour >= 23 || h.hour < 5)
    .reduce((sum, h) => sum + h.activeSeconds, 0);
  const lateNight = Math.min(late / (2 * 3600), 1);

  const b = report.breaks;
  const skipped =
    b && b.prompted > 0 ? (b.skipped + b.snoozed) / b.prompted : 0;

  const heavy = Math.min((report.totals?.activeSeconds ?? 0) / (12 * 3600), 1);

  return Math.min(
    1,
    0.4 * marathon + 0.25 * lateNight + 0.2 * skipped + 0.15 * heavy
  );
}

export async function loadReport(day) {
  try {
    const q = day ? `?day=${day}` : "";
    const res = await fetch(`/api/report${q}`);
    if (!res.ok) throw new Error(res.statusText);
    return await res.json();
  } catch {
    return null;
  }
}
