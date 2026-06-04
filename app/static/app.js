const SLOT_SEQUENCE = ["C", "W", "W", "D", "D", "G"];
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

const state = {
  lineup: [],
  currentIndex: 0,
  currentDraw: null,
  result: null,
  loadingKind: null,
  error: null,
  shuffleFrame: null,
  rerollTeamUsed: false,
  rerollDecadeUsed: false,
  candidateFilter: "ALL",
};

const lineupBoard = document.getElementById("lineup-board");
const promptTitle = document.getElementById("prompt-title");
const turnIndicator = document.getElementById("turn-indicator");
const teamRoll = document.getElementById("team-roll");
const candidateFilters = document.getElementById("candidate-filters");
const candidateGrid = document.getElementById("candidate-grid");
const resultPanel = document.getElementById("result-panel");
const statusBanner = document.getElementById("status-banner");
const newRunButton = document.getElementById("new-run-button");
const drawButton =
  document.getElementById("draw-matchup-button") ||
  document.getElementById("draw-draw-button");
const rerollTeamButton = document.getElementById("reroll-team-button");
const rerollDecadeButton = document.getElementById("reroll-decade-button");


newRunButton.addEventListener("click", () => {
  startNewRun();
});

if (drawButton) {
  drawButton.addEventListener("click", () => {
    drawTeamAndDecade();
  });
}

rerollTeamButton.addEventListener("click", () => {
  rerollTeam();
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

function randomShuffleFrame() {
  const team = SHUFFLE_TEAMS[Math.floor(Math.random() * SHUFFLE_TEAMS.length)];
  return {
    ...team,
    decade: SUPPORTED_DECADES[Math.floor(Math.random() * SUPPORTED_DECADES.length)],
  };
}

function startShuffleAnimation() {
  state.shuffleFrame = randomShuffleFrame();
  render();

  const intervalId = window.setInterval(() => {
    state.shuffleFrame = randomShuffleFrame();
    render();
  }, 120);

  return () => {
    window.clearInterval(intervalId);
    state.shuffleFrame = null;
  };
}

async function startNewRun() {
  initializeLineup();
  state.currentIndex = 0;
  state.currentDraw = null;
  state.result = null;
  state.loadingKind = null;
  state.error = null;
  state.shuffleFrame = null;
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
  render();

  const stopShuffle = startShuffleAnimation();

  try {
    const [draw] = await Promise.all([
      apiPost("/api/game/draw", {
        openSlots: openSlots(),
        excludeCandidateKeys: selectedCandidateKeys(),
        lockFranchiseAbbrev,
        lockDecade,
        excludePairKey,
      }),
      delay(1100),
    ]);
    state.currentDraw = draw;
    state.candidateFilter = "ALL";
    return true;
  } catch (error) {
    state.error = error.message;
    if (previousDraw && loadingKind !== "offer") {
      state.currentDraw = previousDraw;
    }
    return false;
  } finally {
    stopShuffle();
    state.loadingKind = null;
    render();
  }
}

async function drawTeamAndDecade() {
  await requestDraw();
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
  } catch (error) {
    state.error = error.message;
  } finally {
    state.loadingKind = null;
    render();
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

function renderActionButtons() {
  const noOpenSlots = !openSlots().length;
  const isGrading = state.result || state.loadingKind === "grade" || noOpenSlots;

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
    drawButton.textContent = state.currentIndex === 0 ? "Draw Opening Team + Decade" : "Draw Next Team + Decade";
  }

  rerollTeamButton.hidden = !state.currentDraw;
  rerollTeamButton.disabled = Boolean(state.loadingKind || state.rerollTeamUsed);
  rerollTeamButton.textContent = state.rerollTeamUsed ? "Team Reroll Used" : "Reroll Team";

  rerollDecadeButton.hidden = !state.currentDraw;
  rerollDecadeButton.disabled = Boolean(state.loadingKind || state.rerollDecadeUsed);
  rerollDecadeButton.textContent = state.rerollDecadeUsed ? "Decade Reroll Used" : "Reroll Decade";
}

function renderLineup() {
  lineupBoard.innerHTML = state.lineup
    .map((entry) => {
      if (!entry.pick) {
        return `
          <article class="lineup-slot open ${positionToneClass(entry.slot)}">
            <div class="slot-topline">
              <span class="slot-badge ${positionToneClass(entry.slot)}">${entry.slot}</span>
              <span class="slot-label">${SLOT_LABELS[entry.slot]}</span>
            </div>
            <p class="slot-empty">Open</p>
          </article>
        `;
      }

      return `
        <article class="lineup-slot locked ${positionToneClass(entry.slot)}">
          <div class="slot-topline">
            <span class="slot-badge ${positionToneClass(entry.slot)}">${entry.slot}</span>
            <span class="slot-label">${SLOT_LABELS[entry.slot]}</span>
          </div>
          <div class="picked-player">
            <img src="${entry.pick.headshot}" alt="${entry.pick.fullName}">
            <div>
              <h3>${entry.pick.fullName}</h3>
              <p>${entry.pick.teamAbbrev} · ${entry.pick.decade} · ${entry.pick.positionCode}</p>
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
    shots: "SOG",
    avgTimeOnIcePerGame: "TOI",
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

function shuffleCardMarkup(frame) {
  return `
    <div class="team-card shuffling compact-card">
      <p class="team-label">${state.loadingKind === "reroll-team" ? "Rerolling team" : state.loadingKind === "reroll-decade" ? "Rerolling decade" : "Shuffling draw"}</p>
      <div class="shuffle-reel">
        <img class="shuffle-logo" src="${frame.logo}" alt="${frame.name} logo">
        <div>
          <h3>${frame.name}</h3>
          <p class="team-subtitle">${frame.abbrev} · ${frame.decade} · Open slots: ${openSlotSummary()}</p>
        </div>
      </div>
    </div>
  `;
}

function currentDrawMarkup(draw) {
  const secondaryNote = draw.historicalTeam.secondaryNote ? `<p class="historical-note">${draw.historicalTeam.secondaryNote}</p>` : "";
  return `
    <div class="team-card compact-card live-team-card">
      <p class="team-label">Random draw</p>
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

  if (["offer", "reroll-team", "reroll-decade"].includes(state.loadingKind)) {
    promptTitle.textContent = state.loadingKind === "reroll-team"
      ? "Switching the team"
      : state.loadingKind === "reroll-decade"
        ? "Switching the decade"
        : "Shuffling team and decade";
    teamRoll.innerHTML = state.shuffleFrame ? shuffleCardMarkup(state.shuffleFrame) : "";
    renderCandidateFilters();
    candidateGrid.innerHTML = "";
    return;
  }

  if (!state.currentDraw) {
    promptTitle.textContent = state.currentIndex === 0 ? "Draw your opening franchise and decade" : "Draw your next franchise and decade";
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
            <span class="candidate-team">${candidate.historicalTeamAbbrev}</span>
            <span class="candidate-position ${positionToneClass(candidate.eligibleSlot)}">${candidate.positionCode}</span>
          </div>
          <h3>${candidate.fullName}</h3>
          <p class="candidate-meta">${candidate.historicalTeamName}</p>
          <div class="candidate-stats">${candidateStatMarkup(candidate)}</div>
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
  return `https://assets.nhle.com/logos/nhl/svg/${teamAbbrev}_light.svg`;
}

function positionToneClass(slot) {
  return `position-${String(slot || "").toLowerCase()}`;
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

function scorecardTotalsMarkup() {
  if (!state.result) {
    return "";
  }

  const totals = cumulativeLineupTotals(state.result.lineupBreakdown);
  return `
    <div class="scorecard-totals" aria-label="Cumulative lineup totals">
      <span class="scorecard-total-chip">P ${totals.points}</span>
      <span class="scorecard-total-chip">G ${totals.goals}</span>
      <span class="scorecard-total-chip">A ${totals.assists}</span>
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
    <section class="share-card" id="share-card">
      <div class="share-card-header">
        <div>
          <p class="panel-kicker">Share Card</p>
          <h4>Historical NHL Builder Result</h4>
          <p class="share-card-subtitle">${decades}</p>
        </div>
        <div class="share-grade-block">
          <span class="share-grade">${state.result.letterGrade}</span>
          <span class="share-record">Score ${state.result.totalScore}</span>
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
            </div>
            <span class="share-slot-score">${entry.score}</span>
          </article>
        `).join("")}
      </div>
    </section>
  `;
}

function renderResults() {
  if (!state.result) {
    resultPanel.innerHTML = "";
    return;
  }

  resultPanel.innerHTML = `
    <div class="result-header">
      <div>
        <p class="panel-kicker">Scorecard</p>
        <h3>${state.result.letterGrade}</h3>
      </div>
      <div class="result-summary-stack">
        <p class="result-score">${state.result.totalScore}</p>
        <p class="result-record">Lineup score</p>
      </div>
    </div>
    ${shareCardMarkup()}
  `;
}

function render() {
  renderStatus();
  renderActionButtons();
  renderLineup();
  renderPrompt();
  renderResults();
}

startNewRun();
