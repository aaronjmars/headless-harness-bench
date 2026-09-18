#!/usr/bin/env python3
# Render each benchmark table as a standalone PNG (dark, branded). No browser.
import os, textwrap
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")
os.makedirs(OUT, exist_ok=True)

DPI = 150
BG      = "#0d1117"   # page
PANEL   = "#0f141b"   # row base
PANEL2  = "#131a23"   # row alt
HEADBG  = "#1f2a37"   # header
GRID    = "#273140"
TEXT    = "#c9d1d9"
MUTE    = "#8b949e"
ACCENT  = "#58a6ff"   # title / labels
GREEN   = "#3fb950"
RED     = "#f85149"
AMBER   = "#d29922"
FOOT    = "#6e7681"
MONO    = "DejaVu Sans Mono"

def cw(fs): return fs * DPI / 72.0 * 0.602          # mono char width px
def lh(fs): return fs * DPI / 72.0 * 1.55           # line height px

def wrap(s, n):
    out = []
    for part in str(s).split("\n"):
        out += textwrap.wrap(part, n, break_long_words=False, break_on_hyphens=False) or [""]
    return out

def render(fname, title, subtitle, headers, rows, wraps, style=None, first_bold=True, footer_note=None):
    FS, FH, FT, FSub, FF = 14, 14, 26, 13.5, 12.5
    padx, pady = 14, 9
    ncol = len(headers)
    # wrap every cell
    W = [[wrap(headers[c], wraps[c]) for c in range(ncol)]]
    for row in rows:
        W.append([wrap(row[c], wraps[c]) for c in range(ncol)])
    # column widths
    colw = []
    for c in range(ncol):
        mx = max(max((len(l) for l in W[r][c]), default=0) for r in range(len(W)))
        colw.append(mx * cw(FS) + 2 * padx)
    # row heights
    rowh = []
    for r in range(len(W)):
        mx = max(len(W[r][c]) for c in range(ncol))
        rowh.append(mx * lh(FS) + 2 * pady)
    table_w = sum(colw)
    title_h = lh(FT) + 12
    sub_h = (lh(FSub) + 6) if subtitle else 0
    top_pad, side_pad, bot_pad = 26, 26, 14
    W_px = table_w + 2 * side_pad
    note_lines = wrap(footer_note, max(20, int((W_px - 2 * side_pad) / cw(FF - 1)))) if footer_note else []
    foot_h = lh(FF) + 26 + len(note_lines) * lh(FF - 1)
    H_px = top_pad + title_h + sub_h + 10 + sum(rowh) + bot_pad + foot_h

    fig = plt.figure(figsize=(W_px / DPI, H_px / DPI), dpi=DPI)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W_px); ax.set_ylim(0, H_px)
    ax.invert_yaxis(); ax.axis("off")
    fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
    ax.add_patch(Rectangle((0, 0), W_px, H_px, color=BG, zorder=0))

    y = top_pad
    ax.text(side_pad, y, title, color=ACCENT, fontsize=FT, fontweight="bold",
            family=MONO, va="top", ha="left")
    y += title_h
    if subtitle:
        ax.text(side_pad, y, subtitle, color=MUTE, fontsize=FSub, family=MONO, va="top")
        y += sub_h
    y += 10
    x0 = side_pad

    for r in range(len(W)):
        x = x0
        is_head = (r == 0)
        base = HEADBG if is_head else (PANEL if (r % 2) else PANEL2)
        ax.add_patch(Rectangle((x0, y), table_w, rowh[r], color=base, ec=GRID, lw=0.8, zorder=1))
        for c in range(ncol):
            val = headers[c] if is_head else rows[r - 1][c]
            lines = W[r][c]
            color, bold = TEXT, False
            align = "left" if c == 0 else "center"
            if is_head:
                color, bold = "#e6edf3", True
            elif style:
                st = style(r - 1, c, val) or {}
                color = st.get("color", color); bold = st.get("bold", bold)
                if st.get("bg"):
                    ax.add_patch(Rectangle((x, y), colw[c], rowh[r], color=st["bg"], zorder=1.5))
                if "align" in st: align = st["align"]
            if c == 0 and not is_head and first_bold:
                bold = True
                if color == TEXT: color = "#e6edf3"
            th = len(lines) * lh(FS)
            ty = y + (rowh[r] - th) / 2 + lh(FS) * 0.5
            if align == "center":
                tx, ha = x + colw[c] / 2, "center"
            else:
                tx, ha = x + padx, "left"
            for i, ln in enumerate(lines):
                ax.text(tx, ty + i * lh(FS), ln, color=color, fontsize=(FH if is_head else FS),
                        family=MONO, fontweight=("bold" if bold else "normal"),
                        va="center", ha=ha, zorder=3)
            x += colw[c]
        y += rowh[r]

    fy = H_px - foot_h + 6
    ax.text(side_pad, fy, "github.com/aaronjmars/headless-harness-bench", color=ACCENT,
            fontsize=FF, family=MONO, va="top", fontweight="bold")
    ax.text(W_px - side_pad, fy, "@aaronjmars",
            color=FOOT, fontsize=FF, family=MONO, va="top", ha="right")
    for i, nl in enumerate(note_lines):
        ax.text(side_pad, fy + lh(FF) + i * lh(FF - 1), nl, color=FOOT, fontsize=FF - 1,
                family=MONO, va="top")
    fig.savefig(os.path.join(OUT, fname), dpi=DPI, facecolor=BG)
    plt.close(fig)
    print("wrote", fname, f"{int(W_px)}x{int(H_px)}")

# ---------- data ----------
H6 = ["", "omp", "pi", "fx", "opencode", "dsh", "crush", "flue", "eve"]

# 1. identity
render("1-identity.png",
  "Identity + distribution", "8 coding-agent harnesses, headless-driver role  (flue + eve = frameworks)",
  H6,
  [["Language / runtime","TS + Rust / Bun","TS / Node 22+","Zig (native 6 MiB)","TS / Bun","TS / Node (+Py wheel)","Go (native)","TS / Node (Vite)","TS / Node (Nitro)"],
   ["License","MIT","MIT","Apache-2.0","MIT","MIT","FSL-1.1-MIT","Apache-2.0","Apache-2.0"],
   ["OSI-open?","yes","yes","yes","yes","yes","no (MIT after 2y)","yes","yes"],
   ["Version tested","18.2.4","0.85.1","0.0.10","1.18.31","0.1.6-alpha.2","0.95.0","2.0.8","0.60.1"],
   ["Maturity","stable","stable","experimental","stable","alpha, no audit","stable","stable","preview / beta"],
   ["Stars","~31.6k","~106k (suspect)","new","~208k","preview","~28k","~8.3k","~5.3k"],
   ["Built-in tools","31","7","~11","~14","~30","~30 (+LSP)","6 (sandbox)","~14"],
   ["Shape","CLI","CLI","CLI","CLI","CLI","CLI","framework","framework"],
   ["Edit format","hashline","search-replace","string-replace","search-replace","search-replace","search-replace+LSP","search-replace","whole-file"]],
  wraps=[18,16,15,15,15,16,15,15,15],
  style=lambda r,c,v: (
     {"color":GREEN} if v in ("stable","yes") else
     {"color":RED} if v in ("experimental","alpha, no audit") or v.startswith("no (") else
     {"color":AMBER} if v in ("preview / beta","framework") else
     {"color":ACCENT,"bold":True} if v=="hashline" else None))

# 2. tier-1 scorecard
S = ["OMP","dsh","opencode","Pi","fx","Crush","flue","eve"]
sc_rows = [
 ["A Headless (5)","2.8","2.5","2.5","2.8","2.2","2.0","2.0","1.7"],
 ["B Observability (4)","2.8","2.3","2.8","2.8","2.2","1.8","2.0","2.2"],
 ["C Auth & provider (4)","3.0","2.3","2.8","2.8","2.3","2.2","2.0","1.8"],
 ["D Isolation (4)","1.0","2.6","1.4","1.4","1.6","1.4","2.6","2.4"],
 ["E Process hygiene (3)","2.0","2.0","2.0","1.5","2.5","1.75","1.5","2.0"],
 ["F Tooling (2)","3.0","2.4","1.6","1.0","1.6","2.2","1.6","1.2"],
 ["G Extensibility (2)","2.4","3.0","2.2","2.4","1.6","1.2","2.4","2.2"],
 ["H Cost & license (3)","2.6","2.4","2.4","2.4","3.0","2.8","2.0","1.8"],
 ["WEIGHTED TOTAL /81","66.1","65.6","61.6","60.9","58.1","52.1","54.9","52.1"]]
def sc_style(r,c,v):
    if c==0: return None
    row=sc_rows[r]
    if r==len(sc_rows)-1:  # totals
        mx=max(float(x) for x in row[1:])
        return {"bold":True,"color":GREEN if float(v)==mx else TEXT}
    vals=[float(x) for x in row[1:]]
    return {"color":GREEN,"bold":True} if float(v)==max(vals) else None
render("2-tier1-scorecard.png",
  "Tier-1 weighted scorecard", "static source audit, category mean 0-3 x weight, total /81",
  [""]+S, sc_rows, wraps=[22,7,8,9,6,6,7,7,7], style=sc_style,
  footer_note="green = best in row.  absolute totals ~+/-3 noise; trust the tiers.  flue + eve appended, not re-sorted.")

# 3. contract matrix
cm = [
 ["Headless one-shot","-p --mode json","-p --mode json","ask --json (1 obj)","run --format json","--profile headless --json","run (PLAIN TEXT)","run --json (1 obj)","invoke (1 obj+chatter)"],
 ["JSONL event stream","yes","yes","- (single obj)","yes","yes","- (needs serve SSE)","- (final envelope)","- (final obj)"],
 ["Token usage in output","yes","yes","yes","yes","yes","via session json","- (observe/OTel)","via traces (2-step)"],
 ["USD cost in output","yes (telemetry)","yes","-","yes","-","via session json","-","- (gateway-only)"],
 ["Tool-call events","yes","yes","yes","yes","yes","via session json","- (observe/OTel)","via traces"],
 ["Per-run tool allowlist","--tools (leaky)","-t/-xt/-nt exact","per-tool (escapable)","OPENCODE_PERMISSION","ToolRestriction","config-only","code (useTool)","approval policy (code)"],
 ["Append-to-system-prompt","--append-system-prompt","--append-system-prompt","--system (replaces)","AGENTS.md","AGENTS.md / section","CRUSH.md file","return string","instructions.md"],
 ["Per-run provider swap","yes","yes","yes (env)","yes","yes","yes","code (useModel)","eve set (persistent)"],
 ["Subscription OAuth via env","yes (setup token)","yes","- (codex/grok)","yes (Claude sub)","- (grant, no env)","- (API-key only)","- (API-key only)","- (gateway/API-key)"],
 ["API key via env","yes","yes","yes (named)","yes","yes","yes","yes","yes"],
 ["Child-env scrub by default","-","-","-","-","YES","-","YES (allowlist)","YES (sandbox)"],
 ["MCP transports","stdio/http/sse","- (extension)","stdio/http/sse","local/http/sse","stdio/http","stdio/http/sse","http/sse","http/sse"],
 ["MCP $HOME leak","yes (isolate HOME)","n/a","no","no","no","no","no","no"],
 ["Native computer-use","yes (eval)","-","- (WASM)","- (MCP)","opt-in plugin","- (MCP)","- (CF remote)","- (web_fetch)"],
 ["Wall-clock timeout","--max-time (soft)","-","- (no flag)","-","-","- (per-req)","- (cooperative)","- (no flag)"],
 ["Programmatic API","RPC+ACP+SDK","RPC+SDK","ACP+SDK","HTTP+SSE+SDK+ACP","SDK+ACP","serve HTTP+SSE","HTTP+SDK","HTTP+SSE+ACP+SDK"]]
def cm_style(r,c,v):
    if c==0: return None
    if v.startswith("YES"): return {"color":GREEN,"bold":True}
    if v=="-" or v.startswith("- "): return {"color":RED}
    if v.startswith("yes"): return {"color":GREEN}
    return None
render("3-contract-matrix.png",
  "Contract-axis capability matrix", "every axis of the headless-driver contract   ( - = absent )",
  ["Axis","omp","pi","fx","opencode","dsh","crush","flue","eve"], cm,
  wraps=[24,18,17,18,18,17,18,17,18], style=cm_style)

# 4. tier-2 live
H4 = ["Test (0-3)","omp","pi","opencode","dsh","crush","fx(grok)","flue","eve"]
t2 = [
 ["T1 boot-to-JSON","3","2*","3","3","2^","3","3","2+"],
 ["T2 struct-parse","3 (4/4)","3 (4/4)","3 (4/4)","2 (3/4)","2 (4/4)","2 (3/4)","1 (1/4)","2 (1/4)"],
 ["T3 tool-allowlist","3","3","3","3","3","2~","3","1#"],
 ["T4 sys-prompt inject","2","3","2","3","3","3","2","2"],
 ["T5 env isolation","0","0","0","3","0","0","3","3"],
 ["T6 cancel / no orphan","0","3","0","3","3","3","3","2&"],
 ["T7 error machine-readable","3","3","2","3","1","3","2","2"],
 ["T1-T7 TOTAL /21","14","17","13","20","14","16","17","14"],
 ["TASK SUCCESS","yes","yes","yes","yes","yes","yes","yes","yes"]]
def t2_style(r,c,v):
    if c==0: return None
    if r==7:  # totals
        mx=max(int(x) for x in t2[7][1:])
        return {"bold":True,"color":GREEN if int(v)==mx else TEXT}
    if r==8: return {"color":GREEN}
    if v=="0": return {"color":RED,"bold":True}
    if r==4 and v.startswith("3"): return {"color":GREEN,"bold":True}
    return None
render("4-tier2-live.png",
  "Tier-2 live run", "golden task, qwen/qwen3.7-flash (fx on grok-4.6; eve via custom-provider shim; T8 fx not comparable)",
  H4, t2, wraps=[26,9,9,9,9,9,9,9,9], style=t2_style,
  footer_note="*pi hangs until --thinking off.  ^crush run=text, JSON via session show.  ~fx deny shell-escapable.  +eve stdout mixes progress+result.  #eve defaultTools did not drop sandbox bash.  &eve container lingers (pooled).")

# 5. cost + speed
cs = [
 ["pi","$0.0000347","6.1s","329 (+4427 cache)","2","leanest"],
 ["dsh","$0.00033 (computed)","27s","9,447","357","lean"],
 ["omp","$0.000821 (native)","20s","12,283 (+59k cache)","801","mid"],
 ["crush","$0.00087 (session json)","61s","26,325","10","heavy"],
 ["opencode","$0.001347 (native)","28s","24,365","372","heavy"],
 ["flue","n/a (not emitted by CLI)","12.9s","n/a","n/a","light (in-process)"],
 ["eve","n/a (off-gateway)","20.7s (106s pull)","~25,000 (traces)","~966 (traces)","heavy (Nitro+docker)"],
 ["fx (grok, n/c)","n/a (grok sub)","21s","86,401","457","very heavy (86k catalog)"]]
def cs_style(r,c,v):
    if cs[r][0].startswith("fx"): return {"color":MUTE}
    if r==0 and c in (1,2): return {"color":GREEN,"bold":True}
    return None
render("5-cost-speed.png",
  "Cost + wall-clock", "same one-line edit task, same cheap model",
  ["Harness","USD","wall","input tok","output tok","context front-load"], cs,
  wraps=[15,24,12,20,11,22], style=cs_style,
  footer_note="pi ~25x cheaper and ~3x faster than the incumbent.  flue emits no usage on stdout; eve tokens are 2-step (traces), no USD off-gateway.")

# 6. blockers
bl = [
 ["omp","Orphans bash child on bare SIGINT (kill the process GROUP); leaks parent env to tools; --tools does not fully lock the surface (isolate $HOME); --max-time is soft; needs --auto-approve headless. All handled by the caller."],
 ["pi","Hangs forever on a reasoning model unless --thinking off; no built-in MCP / browser / permission gate (extension-only); no wall-clock timeout; env leaks to bash."],
 ["fx","Shipped v0.0.10 binary cannot use OpenRouter / any OpenAI-compatible endpoint (gateway/codex/grok only); ask --json is one object not a stream; no --timeout, no --model; experimental."],
 ["opencode","Headless auto-REJECTS perms without --auto (silent stall); orphans bash child on kill; env leaks; no wall-clock timeout; priciest + slow on the task."],
 ["dsh","Published latest (0.1.5-rc.2) rejects --json (pin 0.1.6-alpha.2); no USD cost in stream; subscription OAuth not usable via env token; uploads session-log to DeepSeek by default; alpha, no security audit."],
 ["crush","run stdout is plain text only (structured needs the serve daemon); no Anthropic/Claude subscription OAuth (API-key only); tool allowlist config-only; errors not machine-readable on run."],
 ["flue","Framework, not a CLI (author + scaffold a TS agent project first); flue run --json is a final envelope with no tokens/cost/tool-calls on stdout (usage only via in-code observe()/OTel); no per-run model/tool/system-prompt flags; no Claude-sub OAuth. Wins: env-scrub by default in BOTH sandbox modes, clean process-tree kill."],
 ["eve","Framework, not a CLI; Vercel-AI-Gateway-locked (OpenRouter needs a custom-provider shim + modelContextWindowTokens); default microsandbox backend hung >140s, just-bash has no node (use docker); usage is a 2-step traces --json, no USD off-gateway; stdout co-mingles progress with the result; Nitro host per invoke + lingering docker sandbox."]]
ready={"omp":GREEN,"opencode":GREEN,"pi":GREEN,"fx":AMBER,"dsh":AMBER,"crush":AMBER,"flue":AMBER,"eve":AMBER}
def bl_style(r,c,v):
    if c==0: return {"color":ready[bl[r][0]],"bold":True,"align":"left"}
    return {"align":"left"}
render("6-blockers.png",
  "Deploy blockers + gotchas", "green = deploy-ready   amber = gated",
  ["Harness","Blockers / gotchas found (live)"], bl,
  wraps=[10,86], style=bl_style, first_bold=False)

print("done ->", OUT)
