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
};

const lineupBoard = document.getElementById("lineup-board");
const promptTitle = document.getElementById("prompt-title");
const turnIndicator = document.getElementById("turn-indicator");
const teamRoll = document.getElementById("team-roll");
const candidateGrid = document.getElementById("candidate-grid");
const resultPanel = document.getElementById("result-panel");
const statusBanner = document.getElementById("status-banner");
const newRunButton = document.getElementById("new-run-button");
const drawButton =
  document.getElementById("draw-matchup-button") ||
  document.getElementById("draw-draw-button");
const rerollTeamButton = document.getElementById("reroll-team-button");
const rerollDecadeButton = document.getElementById("reroll-decade-button");


function wrapCanvasText(context, text, x, y, maxWidth, lineHeight) {
  const words = text.split(/\s+/);
  let line = "";
  let currentY = y;
  for (const word of words) {
    const nextLine = line ? `${line} ${word}` : word;
    if (context.measureText(nextLine).width > maxWidth && line) {
      context.fillText(line, x, currentY);
      line = word;
      currentY += lineHeight;
    } else {
      line = nextLine;
    }
  }
  if (line) {
    context.fillText(line, x, currentY);
  }
  return currentY;
}

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
          <article class="lineup-slot open">
            <div class="slot-topline">
              <span class="slot-badge">${entry.slot}</span>
              <span class="slot-label">${SLOT_LABELS[entry.slot]}</span>
            </div>
            <p class="slot-empty">Open</p>
          </article>
        `;
      }

      return `
        <article class="lineup-slot locked">
          <div class="slot-topline">
            <span class="slot-badge">${entry.slot}</span>
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
  return `${label} ${value}`;
}

function statLabelForKey(key) {
  const labelMap = {
    points: "P",
    assists: "A",
    goals: "G",
    shots: "SOG",
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
    promptTitle.textContent = "Final grade";
    turnIndicator.textContent = "Run complete";
    teamRoll.innerHTML = `
      <div class="team-card result-callout compact-card">
        <p class="team-label">Lineup submitted</p>
        <h3>${state.result.letterGrade}</h3>
        <p class="team-subtitle">Lineup score ${state.result.totalScore}</p>
      </div>
    `;
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
    candidateGrid.innerHTML = "";
    return;
  }

  if (!state.currentDraw) {
    promptTitle.textContent = state.currentIndex === 0 ? "Draw your opening franchise and decade" : "Draw your next franchise and decade";
    teamRoll.innerHTML = "";
    candidateGrid.innerHTML = "";
    return;
  }

  promptTitle.textContent = "Pick any eligible player";
  teamRoll.innerHTML = currentDrawMarkup(state.currentDraw);

  candidateGrid.innerHTML = state.currentDraw.candidates
    .map((candidate) => `
      <button class="candidate-card" type="button" data-candidate-key="${candidate.candidateKey}">
        <img src="${candidate.headshot}" alt="${candidate.fullName}">
        <div class="candidate-body">
          <div class="candidate-topline">
            <span class="candidate-team">${candidate.historicalTeamAbbrev}</span>
            <span class="candidate-position">${candidate.positionCode}</span>
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
  return `${label}: ${value}`;
}

function statSummaryMarkup(stats) {
  return Object.entries(stats || {})
    .map(([key, value]) => `<span>${formatResultStat(key, value)}</span>`)
    .join("");
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
      <div class="share-card-grid">
        ${breakdown.map((entry) => `
          <article class="share-slot-row">
            <span class="share-slot-pill">${entry.slot}</span>
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

async function exportResultImage() {
  if (!state.result) {
    return;
  }

  try {
    if (document.fonts && document.fonts.ready) {
      await document.fonts.ready;
    }

    const breakdown = state.result.lineupBreakdown;
    const width = 1200;
    const rowHeight = 94;
    const height = 260 + breakdown.length * rowHeight;
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    if (!context) {
      throw new Error("Canvas rendering unavailable.");
    }

    const background = context.createLinearGradient(0, 0, width, height);
    background.addColorStop(0, "#11273a");
    background.addColorStop(1, "#0c6e74");
    context.fillStyle = background;
    context.fillRect(0, 0, width, height);

    context.fillStyle = "rgba(255, 255, 255, 0.08)";
    context.fillRect(46, 46, width - 92, height - 92);
    context.fillStyle = "rgba(255, 255, 255, 0.04)";
    context.fillRect(80, 180, width - 160, height - 240);

    context.fillStyle = "#d4ebf4";
    context.font = '600 24px "Space Grotesk", sans-serif';
    context.fillText("Historical NHL Builder", 88, 96);

    context.fillStyle = "#ffffff";
    context.font = '700 74px "Barlow Condensed", sans-serif';
    context.fillText(state.result.letterGrade, 88, 170);

    context.font = '600 30px "Space Grotesk", sans-serif';
    context.fillText("Historical NHL Builder Result", 220, 120);

    context.fillStyle = "rgba(255, 255, 255, 0.8)";
    context.font = '500 24px "Space Grotesk", sans-serif';
    context.fillText(`Lineup score ${state.result.totalScore}`, 220, 162);

    let y = 220;
    breakdown.forEach((entry) => {
      context.fillStyle = "rgba(255, 255, 255, 0.92)";
      context.fillRect(88, y, width - 176, 72);

      context.fillStyle = "#0c6e74";
      context.font = '700 24px "Space Grotesk", sans-serif';
      context.fillText(entry.slot, 112, y + 44);

      context.fillStyle = "#11273a";
      context.font = '700 30px "Barlow Condensed", sans-serif';
      context.fillText(entry.fullName, 176, y + 34);

      context.fillStyle = "#35536b";
      context.font = '500 18px "Space Grotesk", sans-serif';
      wrapCanvasText(
        context,
        `${entry.teamAbbrev} · ${entry.decade} · ${entry.positionCode} · ${Object.entries(entry.stats).map(([key, value]) => formatResultStat(key, value)).join(" · ")}`,
        176,
        y + 58,
        680,
        20,
      );

      context.fillStyle = "#0c6e74";
      context.font = '700 26px "Space Grotesk", sans-serif';
      context.textAlign = "right";
      context.fillText(String(entry.score), width - 120, y + 45);
      context.textAlign = "left";
      y += rowHeight;
    });

    const scoreSlug = String(state.result.totalScore).replace(/[^0-9.]/g, "").replace(".", "-");
    const fileName = `nhl-builder-${state.result.letterGrade.toLowerCase()}-score-${scoreSlug}.png`;
    if (canvas.toBlob) {
      canvas.toBlob((blob) => {
        if (!blob) {
          state.error = "Unable to export image.";
          render();
          return;
        }
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = fileName;
        link.click();
        URL.revokeObjectURL(link.href);
      }, "image/png");
      return;
    }

    const link = document.createElement("a");
    link.href = canvas.toDataURL("image/png");
    link.download = fileName;
    link.click();
  } catch (error) {
    state.error = error.message || "Unable to export image.";
    render();
  }
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
    <div class="result-toolbar">
      <button id="export-result-button" class="action-button export-button" type="button">Export Result Image</button>
      <p class="result-toolbar-note">The summary card below is also formatted to be easy to screenshot.</p>
    </div>
    ${shareCardMarkup()}
  `;

  const exportButton = document.getElementById("export-result-button");
  if (exportButton) {
    exportButton.addEventListener("click", () => {
      exportResultImage();
    });
  }
}

function render() {
  renderStatus();
  renderActionButtons();
  renderLineup();
  renderPrompt();
  renderResults();
}

startNewRun();
