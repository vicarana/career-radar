/* pipeline.js - application-tracking data layer for career-radar.
 * Pure logic + localStorage only, no DOM access, same separation-of-concerns
 * pattern as match.js. index.html owns all rendering; this file owns the
 * status model and persistence.
 *
 * Storage key: 'cr_pipeline' -> { [jobId]: PipelineEntry }
 * PipelineEntry = { status, note, updatedAt, appliedAt, job }
 *   job is a frozen snapshot (title/company/location/url) taken the moment
 *   a job is first saved, so a job that later disappears from a daily crawl
 *   (position filled, posting expired) doesn't vanish from your tracker
 *   while you're mid-interview with them.
 */

const CR_STATUSES = [
  { key: "saved", label: "Saved" },
  { key: "applied", label: "Applied" },
  { key: "screening", label: "Screening" },
  { key: "interview", label: "Interview" },
  { key: "offer", label: "Offer" },
  { key: "rejected", label: "Rejected" },
  { key: "ghosted", label: "Ghosted" },
];

/* One-time migration from the old flat cr_saved array (pre-tracker) into
 * the new cr_pipeline object shape. Safe to call every load, no-ops once
 * cr_saved is gone. */
function crMigrateLegacySaved() {
  const legacyRaw = localStorage.getItem("cr_saved");
  if (legacyRaw === null) return;
  try {
    const legacyIds = JSON.parse(legacyRaw);
    if (Array.isArray(legacyIds) && legacyIds.length) {
      const p = crReadPipelineRaw();
      const now = new Date().toISOString();
      for (const id of legacyIds) {
        if (!p[id]) {
          p[id] = { status: "saved", note: "", updatedAt: now, appliedAt: null, job: null };
        }
      }
      crWritePipeline(p);
    }
  } catch {
    /* corrupt legacy value, nothing worth salvaging */
  }
  localStorage.removeItem("cr_saved");
}

function crReadPipelineRaw() {
  try {
    return JSON.parse(localStorage.getItem("cr_pipeline") || "{}");
  } catch {
    return {};
  }
}
function crWritePipeline(p) {
  localStorage.setItem("cr_pipeline", JSON.stringify(p));
}
function crGetPipeline() {
  crMigrateLegacySaved();
  return crReadPipelineRaw();
}

function crIsSaved(id) {
  return Object.prototype.hasOwnProperty.call(crGetPipeline(), id);
}

function crToggleSaved(id, jobSnapshot) {
  const p = crGetPipeline();
  if (p[id]) {
    delete p[id];
  } else {
    p[id] = {
      status: "saved",
      note: "",
      updatedAt: new Date().toISOString(),
      appliedAt: null,
      job: jobSnapshot || null,
    };
  }
  crWritePipeline(p);
}

function crSetStatus(id, status) {
  const p = crGetPipeline();
  const prev = p[id];
  if (!prev) return;
  const now = new Date().toISOString();
  p[id] = {
    ...prev,
    status,
    updatedAt: now,
    appliedAt: status === "applied" && !prev.appliedAt ? now : prev.appliedAt,
  };
  crWritePipeline(p);
}

function crSetNote(id, note) {
  const p = crGetPipeline();
  if (!p[id]) return;
  p[id] = { ...p[id], note, updatedAt: new Date().toISOString() };
  crWritePipeline(p);
}

function crRemoveFromPipeline(id) {
  const p = crGetPipeline();
  delete p[id];
  crWritePipeline(p);
}

function crPipelineCount() {
  return Object.keys(crGetPipeline()).length;
}

/* Resolves a display-ready job object for a pipeline entry: prefer the
 * frozen snapshot, fall back to today's live data (in case an old,
 * pre-snapshot migrated entry has no job info yet), fall back to just the
 * id string as a last resort so nothing ever crashes on missing data. */
function crResolveJob(id, entry, liveJobsById) {
  if (entry && entry.job) return entry.job;
  if (liveJobsById && liveJobsById[id]) return liveJobsById[id];
  const [title, company] = id.split("|");
  return { title: title || "Unknown role", company: company || "", location: "", url: "#" };
}

function crStatusLabel(key) {
  const s = CR_STATUSES.find((x) => x.key === key);
  return s ? s.label : key;
}
