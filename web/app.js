/* Sudoku: static frontend with generator + uniqueness check.
   - Click cell to select
   - Type 1-9 to set
   - Backspace/Delete clears
   - N toggles notes mode
   - Notes stored per cell
*/

const $ = (sel) => document.querySelector(sel);

const boardEl = $("#board");
const statusEl = $("#statusText");
const keypadEl = $("#keypad");

const difficultyEl = $("#difficulty");
const newGameBtn = $("#newGame");
const toggleNotesBtn = $("#toggleNotes");
const hintBtn = $("#hint");
const checkBtn = $("#check");
const solveBtn = $("#solve");

const DIGITS = [1, 2, 3, 4, 5, 6, 7, 8, 9];

const timerEl = $("#timer");
const pauseBtn = $("#pause");


function deepCopyGrid(g) { return g.map(row => row.slice()); }
function emptyGrid() { return Array.from({ length: 9 }, () => Array(9).fill(0)); }
function keyRC(r, c) { return `${r},${c}`; }

function boxStart(i) { return Math.floor(i / 3) * 3; }

function candidates(grid, r, c) {
    if (grid[r][c] !== 0) return [];
    const used = new Set();

    for (let cc = 0; cc < 9; cc++) if (grid[r][cc] !== 0) used.add(grid[r][cc]);
    for (let rr = 0; rr < 9; rr++) if (grid[rr][c] !== 0) used.add(grid[rr][c]);

    const br = boxStart(r), bc = boxStart(c);
    for (let rr = br; rr < br + 3; rr++) {
        for (let cc = bc; cc < bc + 3; cc++) {
            if (grid[rr][cc] !== 0) used.add(grid[rr][cc]);
        }
    }
    return DIGITS.filter(d => !used.has(d));
}

function findBestCellMRV(grid) {
    let best = null;
    let bestCount = 10;
    for (let r = 0; r < 9; r++) {
        for (let c = 0; c < 9; c++) {
            if (grid[r][c] === 0) {
                const cand = candidates(grid, r, c);
                const n = cand.length;
                if (n === 0) return { r, c, cand };
                if (n < bestCount) {
                    bestCount = n;
                    best = { r, c, cand };
                    if (n === 1) return best;
                }
            }
        }
    }
    return best; // null means solved
}

function shuffle(arr) {
    const a = arr.slice();
    for (let i = a.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
}

function solveOne(grid) {
    // returns solved grid or null
    const cell = findBestCellMRV(grid);
    if (cell === null) return grid; // solved

    const { r, c, cand } = cell;
    const order = shuffle(cand);
    for (const v of order) {
        grid[r][c] = v;
        const res = solveOne(grid);
        if (res) return res;
        grid[r][c] = 0;
    }
    return null;
}

function countSolutions(grid, limit = 2) {
    // backtracking count with early exit at limit
    let count = 0;
    function rec(g) {
        if (count >= limit) return;
        const cell = findBestCellMRV(g);
        if (cell === null) {
            count += 1;
            return;
        }
        const { r, c, cand } = cell;
        for (const v of cand) {
            g[r][c] = v;
            rec(g);
            g[r][c] = 0;
            if (count >= limit) return;
        }
    }
    rec(grid);
    return count;
}

function generateSolved() {
    const g = emptyGrid();
    return solveOne(g);
}

function difficultyConfig(diff) {
    // target clues and max attempts
    if (diff === "easy") return { clues: 40, attempts: 2000 };
    if (diff === "hard") return { clues: 26, attempts: 4000 };
    return { clues: 32, attempts: 3000 }; // medium
}

function generatePuzzle(diff) {
    const solved = generateSolved();
    if (!solved) throw new Error("Failed to generate solution.");
    const puzzle = deepCopyGrid(solved);

    const { clues, attempts } = difficultyConfig(diff);

    // random removal order
    const cells = [];
    for (let r = 0; r < 9; r++) for (let c = 0; c < 9; c++) cells.push([r, c]);
    const order = shuffle(cells);

    let remaining = 81;
    let tries = 0;

    for (const [r, c] of order) {
        if (remaining <= clues) break;
        const backup = puzzle[r][c];
        puzzle[r][c] = 0;

        // ensure uniqueness
        const test = deepCopyGrid(puzzle);
        const n = countSolutions(test, 2);
        if (n !== 1) {
            puzzle[r][c] = backup; // revert
        } else {
            remaining -= 1;
        }

        tries += 1;
        if (tries > attempts) break;
    }

    return { puzzle, solved };
}

function computeConflicts(grid) {
    // returns Set of "r,c" keys that are in conflict
    const conflicts = new Set();

    function markGroup(coords) {
        const map = new Map();
        for (const [r, c] of coords) {
            const v = grid[r][c];
            if (v === 0) continue;
            if (!map.has(v)) map.set(v, []);
            map.get(v).push([r, c]);
        }
        for (const [v, list] of map.entries()) {
            if (list.length > 1) {
                for (const [r, c] of list) conflicts.add(keyRC(r, c));
            }
        }
    }

    // rows
    for (let r = 0; r < 9; r++) {
        markGroup(Array.from({ length: 9 }, (_, c) => [r, c]));
    }
    // cols
    for (let c = 0; c < 9; c++) {
        markGroup(Array.from({ length: 9 }, (_, r) => [r, c]));
    }
    // boxes
    for (let br = 0; br < 9; br += 3) {
        for (let bc = 0; bc < 9; bc += 3) {
            const coords = [];
            for (let r = br; r < br + 3; r++) for (let c = bc; c < bc + 3; c++) coords.push([r, c]);
            markGroup(coords);
        }
    }
    return conflicts;
}

/* ---------- UI State ---------- */
let state = {
    puzzle: emptyGrid(),
    solved: emptyGrid(),
    current: emptyGrid(),
    givens: new Set(),       // "r,c"
    notes: new Map(),        // "r,c" -> Set(digits)
    selected: { r: 0, c: 0 },
    notesMode: false,
    showCheck: false
};

let timer = {
    seconds: 0,
    intervalId: null,
    running: false
};

function formatTime(totalSeconds) {
    const m = Math.floor(totalSeconds / 60);
    const s = totalSeconds % 60;
    const mm = String(m).padStart(2, "0");
    const ss = String(s).padStart(2, "0");
    return `${mm}:${ss}`;
}

function renderTimer() {
    timerEl.textContent = formatTime(timer.seconds);
}

function stopTimer() {
    if (timer.intervalId !== null) {
        clearInterval(timer.intervalId);
        timer.intervalId = null;
    }
    timer.running = false;
    pauseBtn.textContent = "Resume";
}

function startTimer() {
    if (timer.running) return;
    timer.running = true;
    pauseBtn.textContent = "Pause";

    timer.intervalId = setInterval(() => {
        timer.seconds += 1;
        renderTimer();
    }, 1000);
}

function resetTimer() {
    stopTimer();
    timer.seconds = 0;
    renderTimer();
    startTimer();
}

function togglePause() {
    if (timer.running) stopTimer();
    else startTimer();
}


function setStatus(msg, kind = "") {
    statusEl.textContent = msg;
    statusEl.style.color =
        kind === "ok" ? "rgba(75,225,139,.95)" :
            kind === "bad" ? "rgba(255,106,106,.95)" :
                "rgba(170,179,214,.95)";
}

function buildBoard() {
    boardEl.innerHTML = "";
    for (let r = 0; r < 9; r++) {
        for (let c = 0; c < 9; c++) {
            const cell = document.createElement("div");
            cell.className = "cell";
            cell.setAttribute("role", "gridcell");
            cell.dataset.r = String(r);
            cell.dataset.c = String(c);

            if (r === 2 || r === 5) cell.classList.add("r3");
            if (c === 2 || c === 5) cell.classList.add("c3");

            const value = document.createElement("div");
            value.className = "value";
            value.textContent = "";

            const notes = document.createElement("div");
            notes.className = "notes hide";
            for (let i = 1; i <= 9; i++) {
                const n = document.createElement("div");
                n.className = "note";
                n.dataset.n = String(i);
                n.textContent = "";
                notes.appendChild(n);
            }

            cell.appendChild(value);
            cell.appendChild(notes);

            cell.addEventListener("click", () => selectCell(r, c));
            boardEl.appendChild(cell);
        }
    }
}

function buildKeypad() {
    keypadEl.innerHTML = "";

    for (const d of DIGITS) {
        const k = document.createElement("div");
        k.className = "key";
        k.textContent = String(d);
        k.addEventListener("click", () => applyDigit(d));
        keypadEl.appendChild(k);
    }

    const erase = document.createElement("div");
    erase.className = "key special";
    erase.textContent = "Erase";
    erase.addEventListener("click", () => applyDigit(0));
    keypadEl.appendChild(erase);

    const notes = document.createElement("div");
    notes.className = "key special";
    notes.textContent = "Notes";
    notes.addEventListener("click", toggleNotesMode);
    keypadEl.appendChild(notes);

    const show = document.createElement("div");
    show.className = "key special";
    show.textContent = "Show";
    show.addEventListener("click", () => { render(); });
    keypadEl.appendChild(show);
}

function startNewGame() {
    const diff = difficultyEl.value;
    const { puzzle, solved } = generatePuzzle(diff);

    resetTimer();

    state.puzzle = puzzle;
    state.solved = solved;
    state.current = deepCopyGrid(puzzle);
    state.givens = new Set();
    state.notes = new Map();
    state.selected = { r: 0, c: 0 };
    state.notesMode = false;
    state.showCheck = false;
    toggleNotesBtn.textContent = "Notes: Off";

    for (let r = 0; r < 9; r++) {
        for (let c = 0; c < 9; c++) {
            if (puzzle[r][c] !== 0) state.givens.add(keyRC(r, c));
        }
    }
    setStatus(`New ${diff} puzzle created.`, "ok");
    render();
}

function selectCell(r, c) {
    state.selected = { r, c };
    render();
}

function toggleNotesMode() {
    state.notesMode = !state.notesMode;
    toggleNotesBtn.textContent = state.notesMode ? "Notes: On" : "Notes: Off";
    setStatus(state.notesMode ? "Notes mode: toggles candidates." : "Value mode: sets numbers.");
    render();
}

function relatedSetForSelected() {
    const { r, c } = state.selected;
    const set = new Set();

    for (let cc = 0; cc < 9; cc++) set.add(keyRC(r, cc));
    for (let rr = 0; rr < 9; rr++) set.add(keyRC(rr, c));

    const br = boxStart(r), bc = boxStart(c);
    for (let rr = br; rr < br + 3; rr++) {
        for (let cc = bc; cc < bc + 3; cc++) {
            set.add(keyRC(rr, cc));
        }
    }
    return set;
}

function applyDigit(d) {
    const { r, c } = state.selected;
    const k = keyRC(r, c);

    if (state.givens.has(k)) {
        setStatus("That cell is a given.", "bad");
        return;
    }

    if (state.notesMode) {
        if (d === 0) {
            state.notes.delete(k);
            setStatus(`Cleared notes at ${toLabel(r, c)}.`);
        } else {
            const cur = state.notes.get(k) || new Set();
            if (cur.has(d)) cur.delete(d); else cur.add(d);
            if (cur.size === 0) state.notes.delete(k); else state.notes.set(k, cur);
            setStatus(`Notes at ${toLabel(r, c)}: ${[...cur].sort().join("") || "∅"}`);
        }
        render();
        return;
    }

    // value mode
    if (d === 0) {
        state.current[r][c] = 0;
        setStatus(`Cleared ${toLabel(r, c)}.`);
    } else {
        // validate against current grid (temporarily clear same cell for replacements)
        const temp = state.current[r][c];
        state.current[r][c] = 0;
        const cand = candidates(state.current, r, c);
        if (!cand.includes(d)) {
            state.current[r][c] = temp; // restore
            setStatus(`Invalid move. Candidates for ${toLabel(r, c)}: ${cand.join(", ")}`, "bad");
            render();
            return;
        }
        state.current[r][c] = d;
        state.notes.delete(k); // clear notes when you place a value
        setStatus(`Set ${toLabel(r, c)} = ${d}.`);
    }

    render();
    if (isSolved()) {
        stopTimer();
        setStatus(`You solved it! 🎉  Time: ${formatTime(timer.seconds)}`, "ok");
    }

}

function toLabel(r, c) {
    return `${"ABCDEFGHI"[r]}${c + 1}`;
}

function isSolved() {
    for (let r = 0; r < 9; r++) {
        for (let c = 0; c < 9; c++) {
            if (state.current[r][c] === 0) return false;
            if (state.current[r][c] !== state.solved[r][c]) return false;
        }
    }
    return computeConflicts(state.current).size === 0;
}

function doHint() {
    // hint: choose best MRV cell and fill ONLY if single-candidate, else show suggestion
    const cell = findBestCellMRV(state.current);
    if (cell === null) {
        setStatus("No empty cells left.");
        return;
    }
    const { r, c, cand } = cell;
    if (cand.length === 0) {
        setStatus(`Dead-end around ${toLabel(r, c)} (no candidates).`, "bad");
        selectCell(r, c);
        return;
    }
    selectCell(r, c);
    if (cand.length === 1) {
        applyDigit(cand[0]);
    } else {
        setStatus(`Try ${toLabel(r, c)} candidates: ${cand.join(", ")}`);
    }
}

function doCheck() {
    state.showCheck = !state.showCheck;
    setStatus(state.showCheck ? "Check: highlighting conflicts." : "Check: off.");
    render();
}

function doSolve() {
    state.current = deepCopyGrid(state.solved);
    state.notes = new Map();
    stopTimer();
    setStatus("Solved (spoiler).", "bad");
    render();
}


function render() {
    const conflicts = state.showCheck ? computeConflicts(state.current) : new Set();
    const related = relatedSetForSelected();
    const selKey = keyRC(state.selected.r, state.selected.c);
    const selectedValue = state.current[state.selected.r][state.selected.c];


    for (const cell of boardEl.children) {
        const r = Number(cell.dataset.r);
        const c = Number(cell.dataset.c);
        const k = keyRC(r, c);

        cell.classList.toggle("given", state.givens.has(k));
        cell.classList.toggle("selected", k === selKey);
        cell.classList.toggle("related", related.has(k) && k !== selKey);
        cell.classList.toggle("conflict", conflicts.has(k));
        cell.classList.toggle("same", selectedValue !== 0 && state.current[r][c] === selectedValue);


        const valueEl = cell.querySelector(".value");
        const notesEl = cell.querySelector(".notes");

        const v = state.current[r][c];

        if (v !== 0) {
            valueEl.textContent = String(v);
            notesEl.classList.add("hide");
            // clear note glyphs
            for (const n of notesEl.children) n.textContent = "";
        } else {
            valueEl.textContent = "";
            const ns = state.notes.get(k);
            if (ns && ns.size > 0) {
                notesEl.classList.remove("hide");
                for (const n of notesEl.children) {
                    const d = Number(n.dataset.n);
                    n.textContent = ns.has(d) ? String(d) : "";
                }
            } else {
                notesEl.classList.add("hide");
                for (const n of notesEl.children) n.textContent = "";
            }
        }
    }
}

/* ---------- Keyboard ---------- */
window.addEventListener("keydown", (e) => {
    if (e.altKey || e.ctrlKey || e.metaKey) return;

    const { r, c } = state.selected;

    if (e.key >= "1" && e.key <= "9") {
        applyDigit(Number(e.key));
        e.preventDefault();
        return;
    }
    if (e.key === "Backspace" || e.key === "Delete") {
        applyDigit(0);
        e.preventDefault();
        return;
    }
    if (e.key === "n" || e.key === "N") {
        toggleNotesMode();
        e.preventDefault();
        return;
    }

    // arrow navigation
    if (e.key === "ArrowUp") { selectCell(Math.max(0, r - 1), c); e.preventDefault(); return; }
    if (e.key === "ArrowDown") { selectCell(Math.min(8, r + 1), c); e.preventDefault(); return; }
    if (e.key === "ArrowLeft") { selectCell(r, Math.max(0, c - 1)); e.preventDefault(); return; }
    if (e.key === "ArrowRight") { selectCell(r, Math.min(8, c + 1)); e.preventDefault(); return; }
});

/* ---------- Buttons ---------- */
newGameBtn.addEventListener("click", startNewGame);
toggleNotesBtn.addEventListener("click", toggleNotesMode);
hintBtn.addEventListener("click", doHint);
checkBtn.addEventListener("click", doCheck);
solveBtn.addEventListener("click", doSolve);
pauseBtn.addEventListener("click", togglePause);


/* ---------- Init ---------- */
buildBoard();
buildKeypad();
startNewGame();
renderTimer();

