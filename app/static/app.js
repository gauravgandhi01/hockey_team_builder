const SLOT_SEQUENCE = ["C", "W", "W", "D", "D", "G"];
const RUN_HISTORY_STORAGE_KEY = "linecraft_run_history_v1";
const RUN_STATS_STORAGE_KEY = "linecraft_run_stats_v1";
const THEME_STORAGE_KEY = "linecraft_theme_v1";
const RUN_HISTORY_LIMIT = 8;
const CUMULATIVE_AWARD_ORDER = ["cup", "mvp", "art-ross", "rocket", "selke", "norris", "vezina"];
const TRACKED_MODE_KEYS = ["standard", "hard", "twenties", "hard_twenties"];
const BEST_LINEUP_METRIC_KEYS = ["points", "goals", "assists", "awards"];
const MODE_LABELS = {
  standard: "Standard",
  hard: "Hard Mode",
  twenties: "2020s Mode",
  hard_twenties: "Hard + 2020s",
};
const BEST_LINEUP_METRIC_LABELS = {
  points: "Most combined points",
  goals: "Most combined goals",
  assists: "Most combined assists",
  awards: "Most awards",
};
const SLOT_LABELS = {
  C: "Center",
  W: "Winger",
  D: "Defenseman",
  G: "Goalie",
};
const SLOT_PLURALS = {
  C: "Centers",
  W: "Wingers",
  D: "Defensemen",
  G: "Goalies",
};
const SUPPORTED_DECADES = ["1980s", "1990s", "2000s", "2010s", "2020s"];
const SHUFFLE_TEAMS = [
  { abbrev: "ANA", name: "Anaheim Ducks" },
  { abbrev: "BOS", name: "Boston Bruins" },
  { abbrev: "BUF", name: "Buffalo Sabres" },
  { abbrev: "CGY", name: "Calgary Flames" },
  { abbrev: "CAR", name: "Carolina Hurricanes" },
  { abbrev: "CHI", name: "Chicago Blackhawks" },
  { abbrev: "COL", name: "Colorado Avalanche" },
  { abbrev: "CBJ", name: "Columbus Blue Jackets" },
  { abbrev: "DAL", name: "Dallas Stars" },
  { abbrev: "DET", name: "Detroit Red Wings" },
  { abbrev: "EDM", name: "Edmonton Oilers" },
  { abbrev: "FLA", name: "Florida Panthers" },
  { abbrev: "LAK", name: "Los Angeles Kings" },
  { abbrev: "MIN", name: "Minnesota Wild" },
  { abbrev: "MTL", name: "Montreal Canadiens" },
  { abbrev: "NSH", name: "Nashville Predators" },
  { abbrev: "NJD", name: "New Jersey Devils" },
  { abbrev: "NYI", name: "New York Islanders" },
  { abbrev: "NYR", name: "New York Rangers" },
  { abbrev: "OTT", name: "Ottawa Senators" },
  { abbrev: "PHI", name: "Philadelphia Flyers" },
  { abbrev: "PIT", name: "Pittsburgh Penguins" },
  { abbrev: "SJS", name: "San Jose Sharks" },
  { abbrev: "SEA", name: "Seattle Kraken" },
  { abbrev: "STL", name: "St. Louis Blues" },
  { abbrev: "TBL", name: "Tampa Bay Lightning" },
  { abbrev: "TOR", name: "Toronto Maple Leafs" },
  { abbrev: "UTA", name: "Utah Mammoth" },
  { abbrev: "VAN", name: "Vancouver Canucks" },
  { abbrev: "VGK", name: "Vegas Golden Knights" },
  { abbrev: "WSH", name: "Washington Capitals" },
  { abbrev: "WPG", name: "Winnipeg Jets" },
].map((team) => ({
  ...team,
  logo: `https://assets.nhle.com/logos/nhl/svg/${team.abbrev}_light.svg`,
}));

const LOCAL_LOGO_OVERRIDES = {
  ATL: "/static/thrashers.gif",
  MNS: "/static/north_stars.png",
  QUE: "/static/nordiques.png",
};

const state = {
  lineup: [],
  acceptedBoards: [],
  runHistory: [],
  runStats: null,
  currentIndex: 0,
  currentDraw: null,
  result: null,
  bestPossible: null,
  bestPossibleVisible: false,
  bestPossibleLoading: false,
  bestPossibleError: null,
  loadingKind: null,
  error: null,
  shuffleFrame: null,
  hardMode: false,
  hardModeLocked: false,
  twentiesMode: false,
  twentiesModeLocked: false,
  rerollDrawUsed: false,
  rerollTeamUsed: false,
  rerollDecadeUsed: false,
  candidateFilter: "ALL",
  theme: "dark",
};

const SHUFFLE_TEAM_TICKER_COUNT = 10;
const SHUFFLE_DECADE_TICKER_COUNT = 8;

const lineupBoard = document.getElementById("lineup-board");
const promptTitle = document.getElementById("prompt-title");
const turnIndicator = document.getElementById("turn-indicator");
const teamRoll = document.getElementById("team-roll");
const candidateFilters = document.getElementById("candidate-filters");
const candidateGrid = document.getElementById("candidate-grid");
const resultPanel = document.getElementById("result-panel");
const statusBanner = document.getElementById("status-banner");
const themeToggleButton = document.getElementById("theme-toggle-button");
const hardModeToggleButton = document.getElementById("hard-mode-toggle");
const twentiesModeToggleButton = document.getElementById("twenties-mode-toggle");
const newRunButton = document.getElementById("new-run-button");
const promptActions = document.querySelector(".prompt-actions");
const drawButton =
  document.getElementById("draw-matchup-button") ||
  document.getElementById("draw-draw-button");
const rerollTeamButton = document.getElementById("reroll-team-button");
const rerollDecadeButton = document.getElementById("reroll-decade-button");


newRunButton.addEventListener("click", () => {
  startNewRun();
});

if (themeToggleButton) {
  themeToggleButton.addEventListener("click", () => {
    toggleTheme();
  });
}

if (hardModeToggleButton) {
  hardModeToggleButton.addEventListener("click", () => {
    toggleHardMode();
  });
}

if (twentiesModeToggleButton) {
  twentiesModeToggleButton.addEventListener("click", () => {
    toggleTwentiesMode();
  });
}

if (drawButton) {
  drawButton.addEventListener("click", () => {
    drawTeamAndDecade();
  });
}

rerollTeamButton.addEventListener("click", () => {
  handlePrimaryReroll();
});

rerollDecadeButton.addEventListener("click", () => {
  rerollDecade();
});

async function apiPost(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || "Request failed.");
  }
  return data;
}

function delay(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function loadRunHistory() {
  try {
    const raw = window.localStorage.getItem(RUN_HISTORY_STORAGE_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch (_error) {
    return [];
  }
}

function emptyRunStats() {
  return {
    totalRuns: 0,
    bestOverall: null,
    runsByMode: Object.fromEntries(TRACKED_MODE_KEYS.map((key) => [key, 0])),
    bestByMode: Object.fromEntries(TRACKED_MODE_KEYS.map((key) => [key, null])),
    bestByMetric: Object.fromEntries(BEST_LINEUP_METRIC_KEYS.map((key) => [key, null])),
  };
}

function normalizeLineupTotals(rawTotals) {
  if (!rawTotals || typeof rawTotals !== "object") {
    return {
      points: null,
      goals: null,
      assists: null,
      awards: null,
    };
  }

  const normalized = {};
  for (const key of BEST_LINEUP_METRIC_KEYS) {
    const value = Number(rawTotals[key]);
    normalized[key] = Number.isFinite(value) ? value : null;
  }
  return normalized;
}

function modeKeyFromFlags(hardMode, twentiesMode) {
  if (hardMode && twentiesMode) {
    return "hard_twenties";
  }
  if (hardMode) {
    return "hard";
  }
  if (twentiesMode) {
    return "twenties";
  }
  return "standard";
}

function normalizeRunStats(raw) {
  const base = emptyRunStats();
  if (!raw || typeof raw !== "object") {
    return base;
  }

  const bestOverall = raw.bestOverall && typeof raw.bestOverall === "object" ? raw.bestOverall : null;
  const runsByMode = { ...base.runsByMode };
  const bestByMode = { ...base.bestByMode };
  const bestByMetric = { ...base.bestByMetric };

  for (const key of TRACKED_MODE_KEYS) {
    const count = Number(raw.runsByMode?.[key]);
    runsByMode[key] = Number.isFinite(count) && count > 0 ? Math.floor(count) : 0;
    bestByMode[key] = raw.bestByMode?.[key] && typeof raw.bestByMode[key] === "object"
      ? raw.bestByMode[key]
      : null;
  }

  for (const key of BEST_LINEUP_METRIC_KEYS) {
    bestByMetric[key] = raw.bestByMetric?.[key] && typeof raw.bestByMetric[key] === "object"
      ? raw.bestByMetric[key]
      : null;
  }

  const totalRuns = Number(raw.totalRuns);
  return {
    totalRuns: Number.isFinite(totalRuns) && totalRuns > 0
      ? Math.floor(totalRuns)
      : Object.values(runsByMode).reduce((sum, value) => sum + value, 0),
    bestOverall,
    runsByMode,
    bestByMode,
    bestByMetric,
  };
}

function buildRunStatEntry(entry) {
  if (!entry) {
    return null;
  }
  const picks = Array.isArray(entry.picks) ? entry.picks : [];
  return {
    savedAt: entry.savedAt || new Date().toISOString(),
    hardMode: Boolean(entry.hardMode),
    twentiesMode: Boolean(entry.twentiesMode),
    letterGrade: entry.letterGrade || "F",
    totalScore: Number(entry.totalScore || 0),
    decades: Array.isArray(entry.decades) ? entry.decades : [],
    playerLastNames: picks
      .map((pick) => String(pick?.fullName || "").trim().split(/\s+/).pop())
      .filter(Boolean),
    lineupTotals: normalizeLineupTotals(entry.lineupTotals),
    modeKey: modeKeyFromFlags(Boolean(entry.hardMode), Boolean(entry.twentiesMode)),
  };
}

function metricValue(entry, metricKey) {
  const value = Number(entry?.lineupTotals?.[metricKey]);
  return Number.isFinite(value) ? value : null;
}

function pickBetterMetricRun(metricKey, current, candidate) {
  if (!candidate) {
    return current;
  }
  const candidateValue = metricValue(candidate, metricKey);
  if (candidateValue === null) {
    return current;
  }
  if (!current) {
    return candidate;
  }
  const currentValue = metricValue(current, metricKey);
  if (currentValue === null || candidateValue > currentValue) {
    return candidate;
  }
  if (candidateValue < currentValue) {
    return current;
  }
  const currentScore = Number(current.totalScore || 0);
  const candidateScore = Number(candidate.totalScore || 0);
  if (candidateScore !== currentScore) {
    return candidateScore > currentScore ? candidate : current;
  }
  return new Date(candidate.savedAt).getTime() >= new Date(current.savedAt).getTime()
    ? candidate
    : current;
}

function sameModeKeyForEntry(entry, modeKey) {
  return modeKeyFromFlags(Boolean(entry?.hardMode), Boolean(entry?.twentiesMode)) === modeKey;
}

function findMatchingHistoryEntry(target, historyEntries = []) {
  if (!target) {
    return null;
  }

  const targetScore = Number(target.totalScore || 0);
  const modeKey = target.modeKey || modeKeyFromFlags(Boolean(target.hardMode), Boolean(target.twentiesMode));

  let exact = historyEntries.find((entry) => entry?.savedAt && entry.savedAt === target.savedAt);
  if (exact) {
    return exact;
  }

  exact = historyEntries.find((entry) => (
    sameModeKeyForEntry(entry, modeKey)
    && Number(entry.totalScore || 0) === targetScore
    && String(entry.letterGrade || "") === String(target.letterGrade || "")
  ));
  if (exact) {
    return exact;
  }

  const ranked = historyEntries
    .filter((entry) => sameModeKeyForEntry(entry, modeKey))
    .sort((left, right) => Number(right.totalScore || 0) - Number(left.totalScore || 0));
  return ranked[0] || null;
}

function hydrateStatEntry(entry, historyEntries = []) {
  if (!entry) {
    return null;
  }
  if (Array.isArray(entry.playerLastNames) && entry.playerLastNames.length) {
    return entry;
  }
  const match = findMatchingHistoryEntry(entry, historyEntries);
  if (!match) {
    return entry;
  }
  const hydrated = buildRunStatEntry(match);
  return {
    ...entry,
    playerLastNames: hydrated.playerLastNames,
    savedAt: entry.savedAt || hydrated.savedAt,
  };
}

function hydrateRunStats(stats, historyEntries = []) {
  const hydrated = {
    ...stats,
    bestOverall: hydrateStatEntry(stats.bestOverall, historyEntries),
    bestByMode: { ...stats.bestByMode },
    bestByMetric: { ...stats.bestByMetric },
  };

  for (const modeKey of TRACKED_MODE_KEYS) {
    hydrated.bestByMode[modeKey] = hydrateStatEntry(stats.bestByMode?.[modeKey], historyEntries);
  }

  for (const metricKey of BEST_LINEUP_METRIC_KEYS) {
    hydrated.bestByMetric[metricKey] = hydrateStatEntry(stats.bestByMetric?.[metricKey], historyEntries);
  }

  if (!hydrated.bestOverall) {
    const bestCandidates = Object.values(hydrated.bestByMode).filter(Boolean);
    hydrated.bestOverall = bestCandidates.reduce((best, candidate) => pickBetterRun(best, candidate), null);
  }

  return hydrated;
}

function pickBetterRun(current, candidate) {
  if (!candidate) {
    return current;
  }
  if (!current) {
    return candidate;
  }
  const currentScore = Number(current.totalScore || 0);
  const candidateScore = Number(candidate.totalScore || 0);
  if (candidateScore > currentScore) {
    return candidate;
  }
  if (candidateScore < currentScore) {
    return current;
  }
  return new Date(candidate.savedAt).getTime() >= new Date(current.savedAt).getTime()
    ? candidate
    : current;
}

function deriveRunStats(historyEntries) {
  const stats = emptyRunStats();
  for (const entry of historyEntries || []) {
    const statEntry = buildRunStatEntry(entry);
    if (!statEntry) {
      continue;
    }
    stats.totalRuns += 1;
    stats.runsByMode[statEntry.modeKey] += 1;
    stats.bestOverall = pickBetterRun(stats.bestOverall, statEntry);
    stats.bestByMode[statEntry.modeKey] = pickBetterRun(stats.bestByMode[statEntry.modeKey], statEntry);
    for (const metricKey of BEST_LINEUP_METRIC_KEYS) {
      stats.bestByMetric[metricKey] = pickBetterMetricRun(metricKey, stats.bestByMetric[metricKey], statEntry);
    }
  }
  return stats;
}

function loadRunStats(historyEntries = []) {
  try {
    const raw = window.localStorage.getItem(RUN_STATS_STORAGE_KEY);
    if (!raw) {
      const derived = deriveRunStats(historyEntries);
      const hydratedDerived = hydrateRunStats(derived, historyEntries);
      if (hydratedDerived.totalRuns) {
        window.localStorage.setItem(RUN_STATS_STORAGE_KEY, JSON.stringify(hydratedDerived));
      }
      return hydratedDerived;
    }
    const normalized = normalizeRunStats(JSON.parse(raw));
    const hydrated = hydrateRunStats(normalized, historyEntries);
    if (JSON.stringify(hydrated) !== JSON.stringify(normalized)) {
      window.localStorage.setItem(RUN_STATS_STORAGE_KEY, JSON.stringify(hydrated));
    }
    return hydrated;
  } catch (_error) {
    return hydrateRunStats(deriveRunStats(historyEntries), historyEntries);
  }
}

function loadTheme() {
  try {
    const raw = window.localStorage.getItem(THEME_STORAGE_KEY);
    return raw === "light" ? "light" : "dark";
  } catch (_error) {
    return "dark";
  }
}

function persistTheme(theme) {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch (_error) {
    // Ignore storage failures; theme persistence is a UX enhancement only.
  }
}

function persistRunStats(stats) {
  state.runStats = stats;
  try {
    window.localStorage.setItem(RUN_STATS_STORAGE_KEY, JSON.stringify(stats));
  } catch (_error) {
    // Ignore storage failures; local stat tracking is a UX enhancement only.
  }
}

function buildLineupTotalsSummary(result) {
  const breakdown = result?.lineupBreakdown || [];
  const totals = cumulativeLineupTotals(breakdown);
  const awards = cumulativeLineupAwards(breakdown);
  return {
    points: totals.points,
    goals: totals.goals,
    assists: totals.assists,
    awards: awards.reduce((sum, award) => sum + Number(award.count || 0), 0),
  };
}

function persistRunHistory(entries) {
  state.runHistory = entries;
  try {
    window.localStorage.setItem(RUN_HISTORY_STORAGE_KEY, JSON.stringify(entries));
  } catch (_error) {
    // Ignore storage failures; history is a UX enhancement only.
  }
}

function recordRunHistory(result) {
  if (!result) {
    return;
  }
  const breakdown = result.lineupBreakdown || [];
  const entry = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    savedAt: new Date().toISOString(),
    hardMode: state.hardMode,
    twentiesMode: state.twentiesMode,
    letterGrade: result.letterGrade,
    totalScore: result.totalScore,
    decades: [...new Set(breakdown.map((item) => item.decade))],
    lineupTotals: buildLineupTotalsSummary(result),
    picks: breakdown.map((item) => ({
      slot: item.slot,
      fullName: item.fullName,
      teamAbbrev: item.teamAbbrev,
      decade: item.decade,
    })),
  };
  const nextHistory = [entry, ...loadRunHistory()].slice(0, RUN_HISTORY_LIMIT);
  persistRunHistory(nextHistory);

  const nextStats = normalizeRunStats(state.runStats || emptyRunStats());
  const statEntry = buildRunStatEntry(entry);
  nextStats.totalRuns += 1;
  nextStats.runsByMode[statEntry.modeKey] += 1;
  nextStats.bestOverall = pickBetterRun(nextStats.bestOverall, statEntry);
  nextStats.bestByMode[statEntry.modeKey] = pickBetterRun(nextStats.bestByMode[statEntry.modeKey], statEntry);
  for (const metricKey of BEST_LINEUP_METRIC_KEYS) {
    nextStats.bestByMetric[metricKey] = pickBetterMetricRun(metricKey, nextStats.bestByMetric[metricKey], statEntry);
  }
  persistRunStats(nextStats);
}

function clearRunHistory() {
  persistRunHistory([]);
  renderResults();
}

function resetRunStats() {
  persistRunStats(emptyRunStats());
  renderResults();
}

function toggleTheme() {
  state.theme = state.theme === "light" ? "dark" : "light";
  persistTheme(state.theme);
  render();
}

function canToggleRunModes() {
  return (
    !state.hardModeLocked &&
    !state.twentiesModeLocked &&
    state.currentIndex === 0 &&
    !state.currentDraw &&
    !state.loadingKind &&
    !state.result
  );
}

function toggleHardMode() {
  if (!canToggleRunModes()) {
    return;
  }
  state.hardMode = !state.hardMode;
  render();
}

function toggleTwentiesMode() {
  if (!canToggleRunModes()) {
    return;
  }
  state.twentiesMode = !state.twentiesMode;
  render();
}

function initializeLineup() {
  state.lineup = SLOT_SEQUENCE.map((slot, index) => ({
    key: `${slot}-${index}`,
    slot,
    pick: null,
  }));
}

function openSlots() {
  return state.lineup.filter((entry) => !entry.pick).map((entry) => entry.slot);
}

function selectedCandidateKeys() {
  return state.lineup
    .filter((entry) => entry.pick)
    .map((entry) => entry.pick.candidateKey);
}

function findOpenSlotIndex(slot) {
  return state.lineup.findIndex((entry) => entry.slot === slot && !entry.pick);
}

function openSlotSummary() {
  const counts = { C: 0, W: 0, D: 0, G: 0 };
  openSlots().forEach((slot) => {
    counts[slot] += 1;
  });

  return Object.entries(counts)
    .filter(([, count]) => count > 0)
    .map(([slot, count]) => {
      return count > 1 ? `${count} ${SLOT_PLURALS[slot]}` : SLOT_LABELS[slot];
    })
    .join(" • ");
}

function randomShuffleTeam(excludedAbbrevs = []) {
  const excluded = new Set(excludedAbbrevs);
  const eligible = SHUFFLE_TEAMS.filter((team) => !excluded.has(team.abbrev));
  const pool = eligible.length ? eligible : SHUFFLE_TEAMS;
  return pool[Math.floor(Math.random() * pool.length)];
}

function buildShuffleTicker(sourceValues, count, excludedValues = []) {
  const excluded = new Set(excludedValues);
  const ticker = [];
  while (ticker.length < count) {
    const next = sourceValues[Math.floor(Math.random() * sourceValues.length)];
    if (excluded.has(next) && sourceValues.length > excluded.size) {
      continue;
    }
    if (ticker[ticker.length - 1] === next && sourceValues.length > 1) {
      continue;
    }
    ticker.push(next);
  }
  return ticker;
}

function buildShuffleDisplay({ loadingKind, previousDraw, lockDecade }) {
  const fixedDecade = state.twentiesMode
    ? "2020s"
    : loadingKind === "reroll-team"
      ? (lockDecade || previousDraw?.decade || null)
      : null;
  const fixedTeam = loadingKind === "reroll-decade" ? previousDraw?.historicalTeam || null : null;

  return {
    teamTicker: buildShuffleTicker(
      SHUFFLE_TEAMS.map((team) => team.abbrev),
      SHUFFLE_TEAM_TICKER_COUNT,
      fixedTeam ? [fixedTeam.abbrev] : [],
    ),
    decadeTicker: fixedDecade
      ? []
      : buildShuffleTicker(SUPPORTED_DECADES, SHUFFLE_DECADE_TICKER_COUNT),
    fixedTeam,
    fixedDecade,
  };
}

function isShuffleLoadingKind(kind) {
  return ["offer", "reroll-team", "reroll-decade", "reroll-draw"].includes(kind);
}

async function startNewRun() {
  initializeLineup();
  state.acceptedBoards = [];
  state.runHistory = loadRunHistory();
  state.runStats = loadRunStats(state.runHistory);
  state.currentIndex = 0;
  state.currentDraw = null;
  state.result = null;
  state.bestPossible = null;
  state.bestPossibleVisible = false;
  state.bestPossibleLoading = false;
  state.bestPossibleError = null;
  state.loadingKind = null;
  state.error = null;
  state.shuffleFrame = null;
  state.hardMode = false;
  state.hardModeLocked = false;
  state.twentiesMode = false;
  state.twentiesModeLocked = false;
  state.rerollDrawUsed = false;
  state.rerollTeamUsed = false;
  state.rerollDecadeUsed = false;
  state.candidateFilter = "ALL";
  render();
}

async function requestDraw({ lockFranchiseAbbrev = null, lockDecade = null, excludePairKey = null, loadingKind = "offer" } = {}) {
  if (state.loadingKind || state.result || !openSlots().length) {
    return;
  }

  const previousDraw = state.currentDraw;
  state.loadingKind = loadingKind;
  state.error = null;
  state.currentDraw = null;
  state.shuffleFrame = buildShuffleDisplay({ loadingKind, previousDraw, lockDecade });
  render();
  const effectiveLockDecade = state.twentiesMode ? "2020s" : lockDecade;

  try {
    const [draw] = await Promise.all([
      apiPost("/api/game/draw", {
        openSlots: openSlots(),
        excludeCandidateKeys: selectedCandidateKeys(),
        hardMode: state.hardMode,
        lockFranchiseAbbrev,
        lockDecade: effectiveLockDecade,
        excludePairKey,
      }),
      delay(1450),
    ]);
    state.currentDraw = draw;
    state.hardModeLocked = true;
    state.twentiesModeLocked = true;
    state.candidateFilter = "ALL";
    return true;
  } catch (error) {
    state.error = error.message;
    if (previousDraw && loadingKind !== "offer") {
      state.currentDraw = previousDraw;
    }
    return false;
  } finally {
    state.shuffleFrame = null;
    state.loadingKind = null;
    render();
  }
}

async function drawTeamAndDecade() {
  await requestDraw();
}

async function handlePrimaryReroll() {
  if (state.hardMode) {
    await rerollDraw();
    return;
  }
  await rerollTeam();
}

async function rerollDraw() {
  if (!state.currentDraw || state.rerollDrawUsed) {
    return;
  }
  const success = await requestDraw({
    excludePairKey: state.currentDraw.pairKey,
    loadingKind: "reroll-draw",
  });
  if (success) {
    state.rerollDrawUsed = true;
    render();
  }
}

async function rerollTeam() {
  if (!state.currentDraw || state.rerollTeamUsed) {
    return;
  }
  const success = await requestDraw({
    lockDecade: state.currentDraw.decade,
    excludePairKey: state.currentDraw.pairKey,
    loadingKind: "reroll-team",
  });
  if (success) {
    state.rerollTeamUsed = true;
    render();
  }
}

async function rerollDecade() {
  if (!state.currentDraw || state.rerollDecadeUsed) {
    return;
  }
  const success = await requestDraw({
    lockFranchiseAbbrev: state.currentDraw.modernFranchise.abbrev,
    excludePairKey: state.currentDraw.pairKey,
    loadingKind: "reroll-decade",
  });
  if (success) {
    state.rerollDecadeUsed = true;
    render();
  }
}

async function chooseCandidate(candidate) {
  const slotIndex = findOpenSlotIndex(candidate.eligibleSlot);
  if (slotIndex === -1) {
    state.error = `${candidate.fullName} no longer fits an open lineup slot.`;
    render();
    return;
  }

  const slotEntry = state.lineup[slotIndex];
  slotEntry.pick = {
    slot: slotEntry.slot,
    candidateKey: candidate.candidateKey,
    fullName: candidate.fullName,
    teamAbbrev: candidate.historicalTeamAbbrev,
    teamName: candidate.historicalTeamName,
    decade: state.currentDraw.decade,
    headshot: candidate.headshot,
    positionCode: candidate.positionCode,
  };

  state.acceptedBoards.push({
    pairKey: state.currentDraw.pairKey,
    candidateKeys: state.currentDraw.candidates.map((entry) => entry.candidateKey),
  });

  state.currentDraw = null;
  state.error = null;
  state.currentIndex += 1;

  if (state.currentIndex === SLOT_SEQUENCE.length) {
    state.loadingKind = "grade";
    render();
    await gradeLineup();
    return;
  }

  await requestDraw();
}

async function gradeLineup() {
  state.loadingKind = "grade";
  state.error = null;
  render();

  try {
    state.result = await apiPost("/api/game/grade", {
      lineup: state.lineup.map((entry) => ({
        slot: entry.slot,
        candidateKey: entry.pick.candidateKey,
      })),
    });
    recordRunHistory(state.result);
  } catch (error) {
    state.error = error.message;
  } finally {
    state.loadingKind = null;
    render();
  }
}

async function toggleBestPossible() {
  if (!state.result || state.bestPossibleLoading) {
    return;
  }

  if (state.bestPossible) {
    state.bestPossibleVisible = !state.bestPossibleVisible;
    renderResults();
    return;
  }

  state.bestPossibleLoading = true;
  state.bestPossibleError = null;
  renderResults();

  try {
    state.bestPossible = await apiPost("/api/game/best-lineup", {
      lineup: state.lineup.map((entry) => ({
        slot: entry.slot,
        candidateKey: entry.pick.candidateKey,
      })),
      boards: state.acceptedBoards,
    });
    state.bestPossibleVisible = true;
  } catch (error) {
    state.bestPossibleError = error.message;
  } finally {
    state.bestPossibleLoading = false;
    renderResults();
  }
}

function renderStatus() {
  if (state.error) {
    statusBanner.hidden = false;
    statusBanner.className = "status-banner error";
    statusBanner.textContent = state.error;
    return;
  }
  statusBanner.hidden = true;
  statusBanner.textContent = "";
}

function applyTheme() {
  document.body.dataset.theme = state.theme;
}

function renderThemeToggle() {
  if (!themeToggleButton) {
    return;
  }
  const isLight = state.theme === "light";
  themeToggleButton.textContent = isLight ? "Light" : "Dark";
  themeToggleButton.setAttribute("aria-pressed", isLight ? "true" : "false");
  themeToggleButton.classList.toggle("active", isLight);
}

function renderHardModeToggle() {
  if (!hardModeToggleButton) {
    return;
  }
  hardModeToggleButton.textContent = state.hardMode ? "Hard Mode On" : "Hard Mode Off";
  hardModeToggleButton.setAttribute("aria-pressed", state.hardMode ? "true" : "false");
  hardModeToggleButton.disabled = !canToggleRunModes();
  hardModeToggleButton.classList.toggle("active", state.hardMode);
  hardModeToggleButton.classList.toggle("locked", !canToggleRunModes());
}

function renderTwentiesModeToggle() {
  if (!twentiesModeToggleButton) {
    return;
  }
  twentiesModeToggleButton.textContent = state.twentiesMode ? "2020s Mode On" : "2020s Mode Off";
  twentiesModeToggleButton.setAttribute("aria-pressed", state.twentiesMode ? "true" : "false");
  twentiesModeToggleButton.disabled = !canToggleRunModes();
  twentiesModeToggleButton.classList.toggle("active", state.twentiesMode);
  twentiesModeToggleButton.classList.toggle("locked", !canToggleRunModes());
}

function renderActionButtons() {
  const noOpenSlots = !openSlots().length;
  const isGrading = state.result || state.loadingKind === "grade" || noOpenSlots;
  const showStartState = !state.result && !state.loadingKind && !state.currentDraw && state.currentIndex === 0;

  if (isGrading) {
    if (drawButton) {
      drawButton.hidden = true;
    }
    rerollTeamButton.hidden = true;
    rerollDecadeButton.hidden = true;
    return;
  }

  if (drawButton) {
    drawButton.hidden = Boolean(state.currentDraw);
    drawButton.disabled = Boolean(state.loadingKind || state.currentDraw);
    if (state.currentIndex === 0) {
      drawButton.textContent = "Start Game";
    } else if (state.twentiesMode) {
      drawButton.textContent = "Draw Next 2020s Team";
    } else {
      drawButton.textContent = "Draw Next Team + Decade";
    }
    drawButton.classList.toggle("start-game-button", showStartState);
  }

  if (promptActions) {
    promptActions.classList.toggle("start-state", showStartState);
    promptActions.classList.toggle("reroll-state", Boolean(state.currentDraw));
  }

  if (state.hardMode) {
    rerollTeamButton.hidden = !state.currentDraw;
    rerollTeamButton.disabled = Boolean(state.loadingKind || state.rerollDrawUsed);
    rerollTeamButton.textContent = state.rerollDrawUsed ? "Reroll Used" : "Reroll Draw";
    rerollDecadeButton.hidden = true;
    return;
  }

  rerollTeamButton.hidden = !state.currentDraw;
  rerollTeamButton.disabled = Boolean(state.loadingKind || state.rerollTeamUsed);
  rerollTeamButton.textContent = state.rerollTeamUsed ? "Team Reroll Used" : "Reroll Team";

  rerollDecadeButton.hidden = !state.currentDraw || state.twentiesMode;
  rerollDecadeButton.disabled = Boolean(state.loadingKind || state.rerollDecadeUsed);
  rerollDecadeButton.textContent = state.rerollDecadeUsed ? "Decade Reroll Used" : "Reroll Decade";
}

function renderLineup() {
  lineupBoard.innerHTML = state.lineup
    .map((entry) => {
      if (!entry.pick) {
        return `
          <article class="lineup-slot open ${positionToneClass(entry.slot)}" aria-label="Open ${SLOT_LABELS[entry.slot]} slot">
            <div class="slot-topline">
              <span class="slot-badge ${positionToneClass(entry.slot)}">${entry.slot}</span>
            </div>
            <p class="slot-empty">Open</p>
          </article>
        `;
      }

      return `
        <article class="lineup-slot locked ${positionToneClass(entry.slot)}" aria-label="${SLOT_LABELS[entry.slot]}: ${entry.pick.fullName}">
          <div class="slot-topline">
            <span class="slot-badge ${positionToneClass(entry.slot)}">${entry.slot}</span>
          </div>
          <div class="picked-player">
            <img src="${entry.pick.headshot}" alt="${entry.pick.fullName}">
            <div>
              <h3>${entry.pick.fullName}</h3>
              <p>${entry.pick.teamAbbrev} · ${entry.pick.decade}</p>
            </div>
          </div>
        </article>
      `;
    })
    .join("");
}

function formatOfferStat(label, value) {
  if (value === null || value === undefined || value === "") {
    return `${label} --`;
  }
  if (label === "SV%") {
    return `${label} ${Number(value).toFixed(3)}`;
  }
  if (label === "FO%") {
    return `${label} ${(Number(value) * 100).toFixed(1)}`;
  }
  if (label === "GAA") {
    return `${label} ${Number(value).toFixed(2)}`;
  }
  if (label === "TOI") {
    const totalSeconds = Math.max(0, Math.round(Number(value) || 0));
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = String(totalSeconds % 60).padStart(2, "0");
    return `${label} ${minutes}:${seconds}`;
  }
  return `${label} ${value}`;
}

function statLabelForKey(key) {
  const labelMap = {
    points: "P",
    assists: "A",
    goals: "G",
    avgTimeOnIcePerGame: "TOI",
    faceoffWinPctg: "FO%",
    wins: "W",
    shutouts: "SO",
    goalsAgainstAverage: "GAA",
    savePercentage: "SV%",
  };
  return labelMap[key] || key;
}

function candidateStatMarkup(candidate) {
  const stats = candidate.offerStats || {};
  return Object.entries(stats)
    .map(([key, value]) => formatOfferStat(statLabelForKey(key), value))
    .map((stat) => `<span>${stat}</span>`)
    .join("");
}

function candidateIdentityBadgeMarkup(candidate) {
  const tierText = candidate.ratingTier ? ` · T${candidate.ratingTier}` : "";
  return `<span class="candidate-identity-badge ${positionToneClass(candidate.eligibleSlot)}">${candidate.positionCode}${tierText}</span>`;
}

function filteredCandidatesForCurrentDraw() {
  if (!state.currentDraw) {
    return [];
  }
  if (state.candidateFilter === "ALL") {
    return state.currentDraw.candidates;
  }
  return state.currentDraw.candidates.filter(
    (candidate) => candidate.eligibleSlot === state.candidateFilter,
  );
}

function renderCandidateFilters() {
  if (!candidateFilters) {
    return;
  }

  if (!state.currentDraw || state.result || state.loadingKind === "grade") {
    candidateFilters.innerHTML = "";
    candidateFilters.hidden = true;
    return;
  }

  const availableSlots = new Set(
    state.currentDraw.candidates.map((candidate) => candidate.eligibleSlot),
  );
  const options = ["ALL", "C", "W", "D", "G"];

  candidateFilters.hidden = false;
  candidateFilters.innerHTML = options
    .map((slot) => {
      const isAll = slot === "ALL";
      const enabled = isAll || availableSlots.has(slot);
      const active = state.candidateFilter === slot;
      const label = isAll ? "All" : slot;
      return `
        <button
          class="filter-chip${active ? " active" : ""}"
          type="button"
          data-filter-slot="${slot}"
          ${enabled ? "" : "disabled"}
        >${label}</button>
      `;
    })
    .join("");

  candidateFilters.querySelectorAll(".filter-chip").forEach((button) => {
    button.addEventListener("click", () => {
      const nextFilter = button.dataset.filterSlot;
      if (!nextFilter || nextFilter === state.candidateFilter) {
        return;
      }
      state.candidateFilter = nextFilter;
      renderPrompt();
    });
  });
}

function modeChipMarkup(extraClass = "") {
  const chips = [];
  if (state.hardMode) {
    chips.push(`<span class="mode-chip${extraClass ? ` ${extraClass}` : ""}">Hard Mode</span>`);
  }
  if (state.twentiesMode) {
    chips.push(`<span class="mode-chip${extraClass ? ` ${extraClass}` : ""}">2020s Mode</span>`);
  }
  return chips.join("");
}

function hardModeShareNoteMarkup() {
  const notes = [];
  if (state.hardMode) {
    notes.push("Blind draft run");
  }
  if (state.twentiesMode) {
    notes.push("2020s-only run");
  }
  if (!notes.length) {
    return "";
  }
  if (state.hardMode && state.twentiesMode) {
    return `<p class="share-mode-note">Blind draft run · locked to 2020s draws.</p>`;
  }
  if (state.hardMode) {
    return `<p class="share-mode-note">Blind draft run · player stats, tiers, and awards were hidden during picks.</p>`;
  }
  return `<p class="share-mode-note">Locked to 2020s draws for the full run.</p>`;
}

function shuffleCardMarkup(frame) {
  const loadingLabel = state.loadingKind === "reroll-team"
    ? "Rerolling team"
    : state.loadingKind === "reroll-decade"
      ? "Rerolling decade"
      : state.loadingKind === "reroll-draw"
        ? "Redrawing team and decade"
        : state.twentiesMode
          ? "Drawing 2020s lineup options"
          : "Drawing lineup options";
  const teamTickerMarkup = frame.teamTicker
    .map(
      (teamAbbrev) => `
        <span class="shuffle-ticker-chip">${teamAbbrev}</span>
      `,
    )
    .join("");
  const decadeTickerMarkup = frame.fixedDecade
    ? `<span class="shuffle-static-chip">${frame.fixedDecade}</span>`
    : frame.decadeTicker
      .map(
        (decade) => `
          <span class="shuffle-ticker-chip decade">${decade}</span>
        `,
      )
      .join("");
  const teamRowBody = frame.fixedTeam
    ? `<div class="shuffle-static-row"><span class="shuffle-static-chip">${frame.fixedTeam.abbrev}</span></div>`
    : `
      <div class="shuffle-ticker-window">
        <div class="shuffle-ticker-track">
          ${teamTickerMarkup}
          ${teamTickerMarkup}
        </div>
      </div>
    `;
  const decadeRowBody = frame.fixedDecade
    ? `<div class="shuffle-static-row">${decadeTickerMarkup}</div>`
    : `
      <div class="shuffle-ticker-window decades">
        <div class="shuffle-ticker-track decades">
          ${decadeTickerMarkup}
          ${decadeTickerMarkup}
        </div>
      </div>
    `;
  return `
    <div class="team-card shuffling compact-card">
      <div class="shuffle-header">
        <p class="team-label">${loadingLabel}</p>
        <div class="shuffle-badges">
          ${modeChipMarkup("in-draw")}
        </div>
      </div>
      <div class="shuffle-board" aria-hidden="true">
        <div class="shuffle-row">
          <span class="shuffle-row-label">Teams</span>
          ${teamRowBody}
        </div>
        <div class="shuffle-row">
          <span class="shuffle-row-label">Era</span>
          ${decadeRowBody}
        </div>
      </div>
      <div class="shuffle-copy-block">
        <h3>${frame.fixedTeam ? "Locking a new decade" : frame.fixedDecade ? "Scanning teams" : "Scanning franchises and eras"}</h3>
        <p class="team-subtitle">${frame.fixedDecade ? `${frame.fixedDecade} is locked for this draw.` : "Final team and decade will lock on reveal."}</p>
        <p class="shuffle-open-slots">Open slots: ${openSlotSummary()}</p>
      </div>
    </div>
  `;
}

function currentDrawMarkup(draw) {
  const secondaryNote = draw.historicalTeam.secondaryNote ? `<p class="historical-note">${draw.historicalTeam.secondaryNote}</p>` : "";
  return `
    <div class="team-card compact-card live-team-card">
      <div class="draw-card-header">
        <p class="team-label">Random draw</p>
        ${modeChipMarkup("in-draw")}
      </div>
      <div class="team-reveal">
        <img class="team-logo" src="${draw.historicalTeam.logo}" alt="${draw.historicalTeam.name} logo">
        <div>
          <h3>${draw.historicalTeam.name}</h3>
          <p class="team-subtitle">${draw.historicalTeam.abbrev} · ${draw.decade} · ${draw.seasonRange.start} to ${draw.seasonRange.end}</p>
          ${secondaryNote}
        </div>
      </div>
    </div>
  `;
}

function renderPrompt() {
  if (state.result) {
    promptTitle.textContent = "Run complete";
    turnIndicator.textContent = "Run complete";
    teamRoll.innerHTML = "";
    renderCandidateFilters();
    candidateGrid.innerHTML = "";
    return;
  }

  if (state.loadingKind === "grade" || state.currentIndex >= SLOT_SEQUENCE.length) {
    promptTitle.textContent = "Grading your lineup";
    turnIndicator.textContent = `${SLOT_SEQUENCE.length} picks complete`;
    teamRoll.innerHTML = `
      <div class="team-card result-callout compact-card">
        <p class="team-label">Lineup locked</p>
        <h3>Calculating…</h3>
        <p class="team-subtitle">Comparing your ${SLOT_SEQUENCE.length} picks against the same-position players from each decade.</p>
      </div>
    `;
    renderCandidateFilters();
    candidateGrid.innerHTML = "";
    return;
  }

  const turn = Math.min(state.currentIndex + 1, SLOT_SEQUENCE.length);
  turnIndicator.textContent = `Pick ${turn} of ${SLOT_SEQUENCE.length}`;

  if (isShuffleLoadingKind(state.loadingKind)) {
    promptTitle.textContent = state.loadingKind === "reroll-team"
      ? "Switching the team"
      : state.loadingKind === "reroll-decade"
        ? "Switching the decade"
        : state.loadingKind === "reroll-draw"
          ? "Redrawing team and decade"
        : "Shuffling team and decade";
    teamRoll.innerHTML = state.shuffleFrame ? shuffleCardMarkup(state.shuffleFrame) : "";
    renderCandidateFilters();
    candidateGrid.innerHTML = "";
    return;
  }

  if (!state.currentDraw) {
    if (state.twentiesMode) {
      promptTitle.textContent = state.currentIndex === 0 ? "Draw your opening 2020s team" : "Draw your next 2020s team";
    } else {
      promptTitle.textContent = state.currentIndex === 0 ? "Draw your opening franchise and decade" : "Draw your next franchise and decade";
    }
    teamRoll.innerHTML = "";
    renderCandidateFilters();
    candidateGrid.innerHTML = "";
    return;
  }

  promptTitle.textContent = "Pick any eligible player";
  teamRoll.innerHTML = currentDrawMarkup(state.currentDraw);
  renderCandidateFilters();

  const visibleCandidates = filteredCandidatesForCurrentDraw();
  if (!visibleCandidates.length) {
    candidateGrid.innerHTML = `
      <div class="candidate-empty-state">
        No ${SLOT_LABELS[state.candidateFilter] || state.candidateFilter} options available in this draw.
      </div>
    `;
    return;
  }

  candidateGrid.innerHTML = visibleCandidates
    .map((candidate) => `
      <button class="candidate-card ${positionToneClass(candidate.eligibleSlot)}" type="button" data-candidate-key="${candidate.candidateKey}">
        <img src="${candidate.headshot}" alt="${candidate.fullName}">
        <div class="candidate-body">
          <div class="candidate-topline">
            ${candidateIdentityBadgeMarkup(candidate)}
          </div>
          <h3>${candidate.fullName}</h3>
          ${candidate.offerStats ? `<div class="candidate-stats">${candidateStatMarkup(candidate)}</div>` : ""}
          ${awardChipsMarkup(candidate.awards, "candidate-awards")}
        </div>
      </button>
    `)
    .join("");

  candidateGrid.querySelectorAll(".candidate-card").forEach((button) => {
    button.addEventListener("click", async () => {
      const key = button.dataset.candidateKey;
      const candidate = state.currentDraw.candidates.find((entry) => entry.candidateKey === key);
      if (candidate) {
        await chooseCandidate(candidate);
      }
    });
  });
}

function formatResultStat(key, value) {
  const label = statLabelForKey(key);
  if (key === "savePercentage") {
    return `${label}: ${Number(value).toFixed(3)}`;
  }
  if (key === "faceoffWinPctg") {
    return `${label}: ${(Number(value) * 100).toFixed(1)}`;
  }
  if (key === "goalsAgainstAverage") {
    return `${label}: ${Number(value).toFixed(2)}`;
  }
  if (key === "avgTimeOnIcePerGame") {
    const totalSeconds = Math.max(0, Math.round(Number(value) || 0));
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = String(totalSeconds % 60).padStart(2, "0");
    return `${label}: ${minutes}:${seconds}`;
  }
  return `${label}: ${value}`;
}

function statSummaryMarkup(stats) {
  return Object.entries(stats || {})
    .map(([key, value]) => `<span>${formatResultStat(key, value)}</span>`)
    .join("");
}

function teamLogoUrl(teamAbbrev) {
  if (LOCAL_LOGO_OVERRIDES[teamAbbrev]) {
    return LOCAL_LOGO_OVERRIDES[teamAbbrev];
  }
  return `https://assets.nhle.com/logos/nhl/svg/${teamAbbrev}_light.svg`;
}

function positionToneClass(slot) {
  return `position-${String(slot || "").toLowerCase()}`;
}

function tierToneClass(tier) {
  return `tier-${String(tier || "").toLowerCase()}`;
}

function awardLabel(award) {
  if (!award) {
    return "";
  }
  if (award.level === "winner") {
    return award.count > 1 ? `${award.label} x${award.count}` : award.label;
  }
  return award.count > 1 ? `${award.label} F x${award.count}` : `${award.label} F`;
}

function awardChipsMarkup(awards, wrapperClass) {
  if (!awards || !awards.length) {
    return "";
  }

  return `
    <div class="${wrapperClass}">
      ${awards.map((award) => `
        <span class="award-chip ${award.level}" title="${award.level === "winner" ? "Award winner" : "Award finalist"}">
          ${awardLabel(award)}
        </span>
      `).join("")}
    </div>
  `;
}

function cumulativeLineupTotals(breakdown) {
  return (breakdown || []).reduce(
    (totals, entry) => {
      const scorecardTotals = entry.scorecardTotals || {};
      totals.points += Number(scorecardTotals.points || 0);
      totals.goals += Number(scorecardTotals.goals || 0);
      totals.assists += Number(scorecardTotals.assists || 0);
      return totals;
    },
    { points: 0, goals: 0, assists: 0 },
  );
}

function cumulativeLineupAwards(breakdown) {
  const totals = new Map();
  (breakdown || []).forEach((entry) => {
    (entry.awards || []).forEach((award) => {
      if (!award || award.level !== "winner") {
        return;
      }
      const key = award.key || award.label;
      const existing = totals.get(key);
      const count = Number(award.count || 0) || 0;
      if (existing) {
        existing.count += count;
        return;
      }
      totals.set(key, {
        key,
        label: award.label,
        count,
      });
    });
  });

  return [...totals.values()].sort((left, right) => {
    const leftIndex = CUMULATIVE_AWARD_ORDER.indexOf(left.key);
    const rightIndex = CUMULATIVE_AWARD_ORDER.indexOf(right.key);
    const normalizedLeft = leftIndex === -1 ? Number.MAX_SAFE_INTEGER : leftIndex;
    const normalizedRight = rightIndex === -1 ? Number.MAX_SAFE_INTEGER : rightIndex;
    if (normalizedLeft !== normalizedRight) {
      return normalizedLeft - normalizedRight;
    }
    return left.label.localeCompare(right.label);
  });
}

function scorecardTotalsMarkup() {
  if (!state.result) {
    return "";
  }

  const totals = cumulativeLineupTotals(state.result.lineupBreakdown);
  const awards = cumulativeLineupAwards(state.result.lineupBreakdown);
  return `
    <div class="scorecard-summary">
      <div class="scorecard-totals" aria-label="Cumulative lineup totals">
        <span class="scorecard-total-chip">P ${totals.points}</span>
        <span class="scorecard-total-chip">G ${totals.goals}</span>
        <span class="scorecard-total-chip">A ${totals.assists}</span>
      </div>
      ${awards.length ? `
        <div class="scorecard-awards" aria-label="Cumulative trophy totals">
          ${awards
            .map(
              (award) => `
                <span class="scorecard-award-chip">${award.label} ${award.count}</span>
              `,
            )
            .join("")}
        </div>
      ` : ""}
    </div>
  `;
}

function shareCardMarkup() {
  if (!state.result) {
    return "";
  }

  const breakdown = state.result.lineupBreakdown;
  const decades = [...new Set(breakdown.map((entry) => entry.decade))].join(" • ");

  return `
    <section class="share-card${state.hardMode ? " hard-mode-share-card" : ""}" id="share-card">
      <div class="share-card-header">
        <div>
          <div class="share-kicker-row">
            <p class="panel-kicker">Share Card</p>
            ${modeChipMarkup("in-results")}
          </div>
          <div class="share-brand-row">
            <img class="share-brand-logo" src="/static/logo.png" alt="linecraft logo">
          </div>
          <p class="share-card-subtitle">${decades}</p>
          ${hardModeShareNoteMarkup()}
        </div>
        <div class="share-grade-block">
          <span class="share-grade-pill">${state.result.letterGrade}</span>
          <span class="share-score-value">${state.result.totalScore}</span>
          <span class="share-score-label">Lineup score</span>
        </div>
      </div>
      ${scorecardTotalsMarkup()}
      <div class="share-card-grid">
        ${breakdown.map((entry) => `
          <article class="share-slot-row ${positionToneClass(entry.slot)}">
            <span class="share-slot-pill ${positionToneClass(entry.slot)}">${entry.slot}</span>
            <div class="share-slot-media">
              <img class="share-headshot" src="${entry.headshot}" alt="${entry.fullName}">
              <img class="share-team-logo" src="${teamLogoUrl(entry.teamAbbrev)}" alt="${entry.teamAbbrev} logo">
            </div>
            <div class="share-slot-copy">
              <strong>${entry.fullName}</strong>
              <span class="share-slot-meta">${entry.teamAbbrev} · ${entry.decade} · ${entry.positionCode}</span>
              <div class="share-slot-stats">${statSummaryMarkup(entry.stats)}</div>
              ${awardChipsMarkup(entry.awards, "share-slot-awards")}
            </div>
            <span class="share-slot-score">${entry.score}</span>
          </article>
        `).join("")}
      </div>
      <div class="share-card-footer">
        <span class="share-card-url">linecraft.lol</span>
      </div>
    </section>
  `;
}

function formatHistoryTimestamp(value) {
  try {
    return new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }).format(new Date(value));
  } catch (_error) {
    return value;
  }
}

function runHistoryMarkup() {
  const history = state.runHistory || [];
  if (!history.length) {
    return "";
  }
  return `
    <section class="run-history-card compact-card">
      <div class="run-history-header">
        <div>
          <p class="panel-kicker">Recent Runs</p>
          <h3>Stored on this device</h3>
        </div>
        <button id="clear-history-button" class="ghost-button history-clear-button" type="button">Clear</button>
      </div>
      <div class="run-history-list">
        ${history.map((entry) => `
          <article class="run-history-row">
            <div class="run-history-main">
              <div class="run-history-topline">
                <span class="run-history-grade">${entry.letterGrade}</span>
                <strong>${entry.totalScore}</strong>
                ${entry.hardMode ? '<span class="run-history-mode">Hard Mode</span>' : ""}
                ${entry.twentiesMode ? '<span class="run-history-mode">2020s Mode</span>' : ""}
              </div>
              <span class="run-history-decades">${(entry.decades || []).join(" • ")}</span>
            </div>
            <span class="run-history-time">${formatHistoryTimestamp(entry.savedAt)}</span>
          </article>
        `).join("")}
      </div>
    </section>
  `;
}

function localBestRowsMarkup() {
  const stats = state.runStats || emptyRunStats();
  return TRACKED_MODE_KEYS.map((modeKey) => {
    const best = stats.bestByMode?.[modeKey];
    const count = Number(stats.runsByMode?.[modeKey] || 0);
    const playerNames = Array.isArray(best?.playerLastNames) && best.playerLastNames.length
      ? best.playerLastNames.join(" • ")
      : null;
    return `
      <article class="local-best-row">
        <div class="local-best-copy">
          <div class="local-best-topline">
            <strong>${MODE_LABELS[modeKey]}</strong>
            <span class="local-best-count">${count} run${count === 1 ? "" : "s"}</span>
          </div>
          <span class="local-best-meta">${best ? (playerNames || "Saved best lineup") : "No saved best yet"}</span>
        </div>
        ${best ? `
          <div class="local-best-score-block">
            <span class="run-history-grade">${best.letterGrade}</span>
            <strong>${best.totalScore}</strong>
          </div>
        ` : '<span class="local-best-empty">—</span>'}
      </article>
    `;
  }).join("");
}

function bestMetricValueMarkup(metricKey, entry) {
  const value = metricValue(entry, metricKey);
  if (value === null) {
    return '<span class="local-best-empty">—</span>';
  }
  if (metricKey === "points") {
    return `<strong>P ${value}</strong>`;
  }
  if (metricKey === "goals") {
    return `<strong>G ${value}</strong>`;
  }
  if (metricKey === "assists") {
    return `<strong>A ${value}</strong>`;
  }
  return `<strong>${value} ${value === 1 ? "award" : "awards"}</strong>`;
}

function bestMetricRowsMarkup() {
  const stats = state.runStats || emptyRunStats();
  return BEST_LINEUP_METRIC_KEYS.map((metricKey) => {
    const best = stats.bestByMetric?.[metricKey];
    const playerNames = Array.isArray(best?.playerLastNames) && best.playerLastNames.length
      ? best.playerLastNames.join(" • ")
      : null;
    return `
      <article class="local-best-row metric-row">
        <div class="local-best-copy">
          <div class="local-best-topline">
            <strong>${BEST_LINEUP_METRIC_LABELS[metricKey]}</strong>
          </div>
          <span class="local-best-meta">${best ? (playerNames || "Will populate on a future completed run") : "No saved lineup yet"}</span>
        </div>
        <div class="local-best-score-block metric-block">
          ${bestMetricValueMarkup(metricKey, best)}
        </div>
      </article>
    `;
  }).join("");
}

function localBestMarkup() {
  const stats = state.runStats || emptyRunStats();
  if (!stats.totalRuns) {
    return "";
  }
  const overall = stats.bestOverall;
  return `
    <section class="local-best-card compact-card">
      <div class="run-history-header local-best-header">
        <div>
          <p class="panel-kicker">Your Best Runs</p>
          <h3>Across every mode</h3>
        </div>
        <button id="reset-run-stats-button" class="ghost-button history-clear-button" type="button">Reset</button>
      </div>
      <div class="local-best-overview">
        <div class="local-best-overview-copy">
          <strong>Overall best</strong>
          <span>${stats.totalRuns} total run${stats.totalRuns === 1 ? "" : "s"}</span>
        </div>
        ${overall ? `
          <div class="local-best-score-block overall">
            <span class="run-history-grade">${overall.letterGrade}</span>
            <strong>${overall.totalScore}</strong>
          </div>
        ` : ""}
      </div>
      <div class="local-best-list">
        ${localBestRowsMarkup()}
      </div>
      <div class="local-best-secondary">
        <p class="panel-kicker">Lineup Records</p>
        <div class="local-best-list">
          ${bestMetricRowsMarkup()}
        </div>
      </div>
    </section>
  `;
}

function bestPossibleControlsMarkup() {
  if (!state.result) {
    return "";
  }

  const buttonLabel = state.bestPossibleLoading
    ? "Calculating best lineup..."
    : state.bestPossibleVisible
      ? "Hide Best Possible Lineup"
      : "Show Best Possible Lineup";

  return `
    <div class="best-possible-controls">
      <button
        id="best-possible-button"
        class="ghost-button best-possible-button"
        type="button"
        ${state.bestPossibleLoading ? "disabled" : ""}
      >${buttonLabel}</button>
      ${state.bestPossibleError ? `<p class="best-possible-error">${state.bestPossibleError}</p>` : ""}
    </div>
  `;
}

function bestPossibleMarkup() {
  if (!state.bestPossibleVisible || !state.bestPossible) {
    return "";
  }

  const delta = Number(state.bestPossible.scoreDelta || 0);
  const deltaLabel = delta > 0 ? `+${delta.toFixed(1)} vs your run` : "You found the top lineup";

  return `
    <section class="best-possible-card compact-card">
      <div class="best-possible-header">
        <div>
          <p class="panel-kicker">Best Possible</p>
          <h3>Best lineup from your six draws</h3>
          <p class="best-possible-subtitle">${deltaLabel}</p>
        </div>
        <div class="best-possible-score-block">
          <span class="best-possible-grade">${state.bestPossible.letterGrade}</span>
          <span class="best-possible-score">${state.bestPossible.totalScore}</span>
        </div>
      </div>
      <div class="best-possible-list">
        ${state.bestPossible.lineupBreakdown.map((entry) => `
          <article class="best-possible-row ${positionToneClass(entry.slot)}">
            <span class="share-slot-pill ${positionToneClass(entry.slot)}">${entry.slot}</span>
            <img class="best-possible-headshot" src="${entry.headshot}" alt="${entry.fullName}">
            <div class="best-possible-copy">
              <strong>${entry.fullName}</strong>
              <span class="best-possible-meta">${entry.teamAbbrev} · ${entry.decade} · Draw ${entry.sourceDrawIndex}</span>
              <div class="best-possible-stats">${statSummaryMarkup(entry.stats)}</div>
              ${awardChipsMarkup(entry.awards, "best-possible-awards")}
            </div>
            <span class="best-possible-player-score">${entry.score}</span>
          </article>
        `).join("")}
      </div>
    </section>
  `;
}

function renderResults() {
  const persistentMarkup = localBestMarkup();

  if (!state.result) {
    resultPanel.innerHTML = persistentMarkup;
  } else {
    resultPanel.innerHTML = `
      ${shareCardMarkup()}
      ${bestPossibleControlsMarkup()}
      ${bestPossibleMarkup()}
      ${persistentMarkup}
    `;
  }

  const bestPossibleButton = document.getElementById("best-possible-button");
  if (bestPossibleButton) {
    bestPossibleButton.addEventListener("click", async () => {
      await toggleBestPossible();
    });
  }
  const resetRunStatsButton = document.getElementById("reset-run-stats-button");
  if (resetRunStatsButton) {
    resetRunStatsButton.addEventListener("click", () => {
      resetRunStats();
    });
  }
}

function render() {
  applyTheme();
  renderThemeToggle();
  renderHardModeToggle();
  renderTwentiesModeToggle();
  renderStatus();
  renderActionButtons();
  renderLineup();
  renderPrompt();
  renderResults();
}

state.theme = loadTheme();
state.runHistory = loadRunHistory();
state.runStats = loadRunStats(state.runHistory);
startNewRun();
