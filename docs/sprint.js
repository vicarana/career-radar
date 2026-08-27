/* sprint.js - 60-day application sprint tracker for career-radar.
 * Pure logic + localStorage only, same separation-of-concerns pattern as
 * match.js and pipeline.js: this file owns the sprint model, index.html
 * owns rendering. Reads pipeline.js's crGetPipeline(), doesn't duplicate
 * pipeline storage, a sprint is just a lens on top of existing pipeline
 * entries (which appliedAt fall in the window, at what grade).
 *
 * Storage key: 'cr_sprint' -> { startDate, targetPerDay, minGrade }
 * Grade comparison is plain string comparison ('A' <= 'B' <= 'C' <= 'D' <=
 * 'F'), which happens to already sort correctly by quality since the
 * letters themselves are in quality order alphabetically. */

const CR_SPRINT_KEY = "cr_sprint";
const CR_SPRINT_DAYS = 60;

function crGetSprint() {
  try {
    return JSON.parse(localStorage.getItem(CR_SPRINT_KEY) || "null");
  } catch {
    return null;
  }
}

function crStartSprint(targetPerDay, minGrade) {
  const cfg = {
    startDate: new Date().toISOString().slice(0, 10),
    targetPerDay: targetPerDay || 5,
    minGrade: minGrade || "B",
  };
  localStorage.setItem(CR_SPRINT_KEY, JSON.stringify(cfg));
  return cfg;
}

function crEndSprint() {
  localStorage.removeItem(CR_SPRINT_KEY);
}

function crIsoDate(d) {
  return d.slice(0, 10);
}

/* The real progress math. Counts a pipeline entry toward the sprint only
 * if: it has an appliedAt timestamp (status reached "applied" or beyond),
 * that date falls within the sprint window, and the frozen job snapshot's
 * grade clears the sprint's minGrade floor. A job saved but never actually
 * applied to doesn't count, this tracks applications, not saves. */
function crSprintProgress(cfg) {
  if (!cfg) return null;
  const p = crGetPipeline();
  const today = crIsoDate(new Date().toISOString());
  const start = new Date(cfg.startDate + "T00:00:00Z");
  const dayMs = 86400000;
  const dayIndex = Math.floor((Date.now() - start.getTime()) / dayMs) + 1; // 1-indexed
  const daysElapsed = Math.max(1, Math.min(dayIndex, CR_SPRINT_DAYS));
  const daysRemaining = Math.max(0, CR_SPRINT_DAYS - daysElapsed);

  let appliedToday = 0;
  let appliedTotal = 0;
  for (const entry of Object.values(p)) {
    if (!entry.appliedAt) continue;
    const grade = entry.job && entry.job.grade;
    if (!grade || grade > cfg.minGrade) continue; // string compare: worse than floor
    const appliedDate = crIsoDate(entry.appliedAt);
    if (appliedDate < cfg.startDate) continue;
    appliedTotal += 1;
    if (appliedDate === today) appliedToday += 1;
  }

  const targetTotal = cfg.targetPerDay * CR_SPRINT_DAYS;
  const expectedByNow = cfg.targetPerDay * daysElapsed;
  const remainingToGoal = Math.max(0, targetTotal - appliedTotal);
  const requiredPerDay = daysRemaining > 0
    ? Math.ceil(remainingToGoal / daysRemaining)
    : remainingToGoal;

  return {
    dayIndex: daysElapsed,
    totalDays: CR_SPRINT_DAYS,
    daysRemaining,
    appliedToday,
    appliedTotal,
    targetPerDay: cfg.targetPerDay,
    targetTotal,
    expectedByNow,
    onPace: appliedTotal >= expectedByNow,
    requiredPerDay,
    minGrade: cfg.minGrade,
    complete: daysElapsed >= CR_SPRINT_DAYS,
  };
}

/* Today's real supply at the sprint's quality floor, so the UI can show
 * the honest gap between "what you're asking for" and "what the tool
 * actually surfaced today" instead of silently hiding a shortfall. */
function crSprintTodaySupply(data, minGrade) {
  if (!data || !data.tracks) return 0;
  let n = 0;
  for (const tk of ["B", "C", "D"]) {
    for (const j of data.tracks[tk] || []) {
      if (j.grade && j.grade <= minGrade) n += 1;
    }
  }
  return n;
}
