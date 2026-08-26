/* match.js - client-side JD matcher for career-radar.
 * Runs entirely in the browser. No network calls, no data leaves the phone.
 * Mirrors the scoring shape of radar/radar.py's score()/grade_of() so both
 * pipelines agree on what "a good match" means. */

/* Common SRE/DevOps/Cloud/AI-eng keywords used purely to spot GAPS - things
 * the JD asks for that aren't in Vic's own skill lists. This is intentionally
 * broader than profile.json's strong/good skills. */
const CR_KEYWORD_DICT = [
  "kubernetes","k8s","docker","terraform","ansible","puppet","chef",
  "aws","gcp","azure","ci/cd","cicd","jenkins","github actions","gitlab ci",
  "argocd","helm","prometheus","grafana","datadog","splunk","elk","elasticsearch",
  "kafka","rabbitmq","python","golang","bash","sql","nosql","mongodb",
  "postgresql","mysql","redis","incident management","on-call","sla","slo","sli",
  "chaos engineering","disaster recovery","load balancing","networking","dns",
  "tls","ssl","security","iam","rbac","compliance","soc2","agile","scrum",
  "jira","confluence","linux","vmware","service mesh","istio","envoy",
  "microservices","api gateway","rest api","graphql","grpc","machine learning",
  "llm","mlops","airflow","spark","bigquery","snowflake","data pipeline",
  "observability","apm","distributed tracing","opentelemetry","finops",
  "infrastructure as code","gitops","blue-green deployment","canary deployment",
  "rollback","capacity planning","performance tuning","autoscaling","serverless",
  "lambda","event-driven","message queue","monitoring","alerting","pagerduty",
  "opsgenie",
];

/* Strips common LinkedIn/Indeed page-chrome noise so paste-dumps clean up
 * before analysis. Best-effort, not exhaustive. */
function crCleanJD(raw) {
  const dropPatterns = [
    /^show (more|less)$/i,
    /^about the job$/i,
    /^\d+\s+(applicants|people clicked apply)/i,
    /^(save|apply|easy apply)$/i,
    /^(skip to (main content|search|navigation))/i,
    /^people also viewed$/i,
    /^similar jobs$/i,
    /^report this job$/i,
  ];
  return (raw || "")
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l.length > 0 && !dropPatterns.some((re) => re.test(l)))
    .join("\n");
}

/* Same weighting shape as radar.py: score() + grade_of(). */
function crScore(text, title, profile) {
  const t = (text || "").toLowerCase();
  const ti = (title || "").toLowerCase();
  if ((profile.avoid_skills || []).some((s) => ti.includes(s))) return -99;
  let sc = 0;
  sc += (profile.target_titles || []).filter((s) => ti.includes(s)).length * 2;
  sc += (profile.strong_skills || []).filter((s) => t.includes(s)).length * 2;
  sc += (profile.good_skills || []).filter((s) => t.includes(s)).length * 1;
  return sc;
}
function crGradeOf(score) {
  let g;
  if (score >= 14) g = "A";
  else if (score >= 10) g = "B";
  else if (score >= 7) g = "C";
  else if (score >= 4) g = "D";
  else g = "F";
  const pct = Math.max(35, Math.min(99, Math.round((score / 20) * 100)));
  return { g, pct };
}

/* The actual "what's the ATS/hiring manager looking for" gap analysis:
 * dictionary terms present in the JD but absent from Vic's own skill lists. */
function crGapAnalysis(text, profile) {
  const t = (text || "").toLowerCase();
  const known = new Set([
    ...(profile.strong_skills || []),
    ...(profile.good_skills || []),
  ]);
  const matched = [];
  const gap = [];
  for (const kw of CR_KEYWORD_DICT) {
    if (!t.includes(kw)) continue;
    if (known.has(kw)) matched.push(kw);
    else gap.push(kw);
  }
  return { matched, gap };
}

/* Public entry point used by index.html. */
function crAnalyzeJD(rawText, title, company, profile) {
  const cleaned = crCleanJD(rawText);
  const score = crScore(cleaned, title, profile);
  const { g, pct } = crGradeOf(score);
  const { matched, gap } = crGapAnalysis(cleaned, profile);
  return { cleaned, score, grade: g, match: pct, matched, gap };
}
