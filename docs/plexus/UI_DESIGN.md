# Plexus · Interface design

**The idea:** the interface is a reading of the stage. Every mark, word and verb shows state the runtime has confirmed, in one grammar (five marks, fixed-order receipts), and anything not yet known is drawn as Unknown, never as a pass.

Status: **draft for Joe.** Nothing here is built. Decided Nov 1 from a read-only study of the SYNAPSE panel, three Jev passes and Joe's seven calls, then checked by two independent reviewers.

**What this document does:** it sets the design elements of the Plexus interface. The SYNAPSE Python panel (`C:\Users\User\SYNAPSE\python\synapse`) was studied as a design reference only. **Nothing from it is copied or imported**: no code, widget or class names, stylesheet text, assets or layout. Each borrowed idea is restated in Plexus's own terms, with the reason it fits.

**How decisions were made:** every design element has candidate options. TypeSafe's **Jev** model chose among them and routed each element to a Plexus surface, from the study's evidence and Plexus's rules. Jev also checked each element for copy risk: whether the option closest to the reference panel would amount to copying it. Code then applied fixed policy on top: a pick with high copy risk moves on (0.6, or 0.5 for anything visual, Joe's setting), and where options combine rather than compete, a second Jev pass judged each option on its own (see the appendix). Jev's raw probabilities are kept in `docs/plexus/ui_design_jev.json`, so any decision can be re-weighed without re-running it.

---

## 1 · Principles

These six come out of the study and the Jev pass together. Each one is a rule a test can check, because the study's clearest lesson is that a rule kept only in a comment drifts.

1. **Every claim on screen reads real state.** "Stopping", "Parked", "Not on stage", "Reverted" and "Unknown" each read an opinion that is actually on the stage or the session layer. A card settles only when the runtime confirms. The reference panel's worst failures were surfaces that sat apart from what enforced them: approval cards drawn but never reached, a "revert" that was really a global undo.
2. **Unknown is its own mark, and never a default pass.** Verified, Broken, Unknown, idle and working each get a distinct mark. Green is unreachable from a no-data state. This is the visual half of the `Outcome` lesson in the scaffold plan (§3.2 #5).
3. **Waiting for Joe is parked, never blocking.** A proposal that needs Joe becomes a parked card; the neuron stays dormant; either verb (named for the act, or Discard) is an opinion written to the session layer, and the neuron's predicate wakes on it. Nothing times out on its own.
4. **Words and weight carry hierarchy; colour is budgeted.** Two accents at most (actions; live agent presence), a muted verdict trio inside content, and organ outputs (images, video) as the only colour on their surface. A test counts hues.
5. **Mono for anything compared character by character, sans for prose, three sizes.** Prim paths, sublayer names, intent hashes, organ ids and predicate text are mono. Quiet comes from caps and tracking, never a fourth grey.
6. **A halt is a request until confirmed.** Stop moves to a visible Stopping state that names what is still running; each organ job resolves to cancelled-confirmed or Unknown before the state settles, and a restart never resumes work by itself.

The words on every surface come from [`VOICE.md`](VOICE.md): one word per thing, from the right vocabulary.

---

## 2 · Surfaces

Jev routed each element to the surface it belongs on. Five elements are system-wide rules (colour, type, spacing, accents, keyboard), so code sets them to every surface instead of asking Jev.

| Surface | What lives there | Elements routed here |
|---|---|---|
| **Graph canvas** | Nodes, ports, edges; the graph a user builds and runs | A thin progress rule plus a heartbeat dot on each running node (the dot also carries the three stop states) |
| **Inspector** | The selected node, layer or neuron: parameters, provenance, which opinion wins | The five-mark status display (Verified, Broken, Unknown, idle, working) with reasons inline, result receipts, the opinion stack, stage-state visualisation |
| **Activity rail** | Neuron wakes, parked proposals, running organ jobs, budgets, the provenance log | Stop / Stopping, approvals, denials, turn limits, undo, admission, long-job counts, liveness, the provenance log, session persistence (close = detach) |
| **Status bar** | One line of global state: connection, composer, CPU/GPU, unknowns | Connection loss and reconnect, the one-sentence status and a refused send (both confirmed by Joe) |
| **CLI** and **MCP** | Runs and reports without a UI; other agents driving Plexus | Nothing in this pass routed here first; both read the same state model |

**Low routing confidence** (below 0.5): Joe placed the one-sentence status (Jev 0.30) and the refused send (0.46) in the status bar, and the Unknown mark in the inspector (Jev had it on the canvas at 0.42).

---

## 3 · Design elements, decided

Each element gives: the decision; why it fits Plexus; the reference idea it came from, as a description with the SYNAPSE file it was observed in (nothing copied); what Plexus does not take; and Jev's numbers.

**How to read Jev's numbers.** `p` is the probability Jev gave the chosen option. Confidence is how concentrated its probabilities were. Copy risk is Jev's probability that the option closest to the reference would amount to copying it. A pick with copy risk ≥ 0.6 moves on; **for anything visual the threshold is 0.5** (Joe, Nov 1). The full policy (which reading counts, passes 2 and 3, composable options) is in the appendix. **Visual** means the twelve elements from the study's visual lens, plus the status sentence and the approval-card layout, which decide how something is drawn. Decisions marked **Joe** override Jev.

### At a glance

| Element | Surface | Decision |
|---|---|---|
| Keyboard and focus | all | Node-editor conventions + a global Stop key; hints read from the binding |
| Neutral ramp | all | Seed `#2D2D2D` (Joe); three text greys; quiet comes from form |
| Type | all | Three sizes; mono for identifiers, sans for prose |
| Colour roles | all | Two accents + muted verdict trio; hue-count test |
| Spacing | all | Named roles, 4-px grid, gap steps down per nesting level (Joe) |
| Progress and liveness | canvas | Top-edge progress rule + heartbeat dot (Joe) |
| Status marks | inspector | Five marks, reason inline (Joe: placement) |
| Result receipt | inspector | One-line receipt on the node, full rows in the inspector |
| Opinion stack | inspector | Per-attribute stack read from USD, winner marked |
| Stage state | inspector | Layer-stack step list per prim |
| Stop | rail | Single-stage; named Stopping state; per-job list (Joe) |
| Liveness and retry | rail | Idle / busy / stalled from heartbeats; intent-hash retry breaker |
| Turn revert | rail | Revert mutes the turn's delta layer |
| Parked-proposals tray | rail | Parked-proposals inbox + stage diff and cost |
| Turn limit | rail | Three-part closing sentence |
| Denial | rail | Becomes a parked proposal or a do-it-yourself verb |
| Admission | rail | Per-organ / per-budget refusal in a sentence |
| Session | rail | Session layer per project; close = detach |
| Long-job progress | rail | Counted line (n of m), no graphic |
| Transcript | rail | Provenance log, one row per opinion |
| Parked-proposal card | rail | Predicate + intent hash, stage diff, budget, act-named verbs, no countdown |
| Refused send | status bar | Refuse, keep the draft, one sentence (Joe: placement) |
| Status sentence | status bar | One sentence per project, fixed precedence (Joe: placement) |
| Connection | status bar | Lasting per-organ state with last error and next retry |

### System-wide (applies to every surface)

**Keyboard and focus behaviour** (`keyboard-and-focus`)

- **Decision:** Composer conventions as observed, plus a global Stop key (e.g. Escape twice or Ctrl+.) with its hint read from the binding
- **Why it fits Plexus:** Node-editor habits should carry over: Tab (or '/') for the palette, Escape to back out, and a dedicated, always-bound key for Stop that works whatever has focus. Every shortcut hint is read from the real binding. Focus returns to where Joe was typing after any card or dialog closes.
- **Reference idea (SYNAPSE, ideas only):** Enter sends, Shift+Enter adds a new line, and '/' on an empty prompt opens the command palette. Ctrl+K also opens it, and the on-screen hint is read from the shortcut that is actually bound, so the hint can't be wrong. The palette closes on Escape and moves with the arrow keys and Enter. After attachments change, focus goes back to the input. The placeholder shortens to fit narrow docks. Stop has no keyboard shortcut; it is reachable only by clicking the button or the status mark. — `C:\Users\User\SYNAPSE\python\synapse\panel\synapse_panel.py:452-469, 869-876, 2934-2938; command_palette.py:809-835`. Did it work: Unknown. There were no keyboard findings, and the missing Stop key is visible in the code (no Escape or Stop binding in synapse_panel.py).
- **Not taken:** Stop reachable only by mouse.
- **Jev:** Jev opt0 p 0.91, confidence 0.86, copy risk of the closest option 0.28

**Colour: surfaces and the text grey ramp** (`solved-neutral-ramp`)

- **Decision:** One seed grey with elevation offsets and contrast-solved text roles; quiet below three rungs comes from form. **Seed: `#2D2D2D`, neutral** — Joe asked for a neutral grey around `#2A2A2A` (Nov 1); `#2A2A2A` itself is the exact seed the reference panel uses, so the seed sits three levels above it.
- **Derived ramp** (computed from the seed with the WCAG 2 contrast formula; text roles solved against the lightest text-bearing surface, `bg-2`; offsets are Plexus's own, in decimal levels per channel; role names are Plexus's own; no value in the ramp appears anywhere in the reference panel's code, checked Nov 1):

  | Role | Value | Rule | Contrast on bg-2 / bg-1 / bg-0 |
  |---|---|---|---|
  | bg-0 (below) | `#232323` | seed − 10 | — |
  | bg-1 (base) | `#2D2D2D` | seed | — |
  | bg-2 (lifted) | `#373737` | seed + 10 | — |
  | bg-rule (edges) | `#454545` | seed + 24 | 1.24 / 1.44 / 1.64 |
  | fg-1 (strong) | `#ECECEC` | ≥ 10:1 | 10.08 / 11.66 / 13.30 |
  | fg-2 (body) | `#C7C7C7` | ≥ 7:1 (AAA body) | 7.04 / 8.15 / 9.30 |
  | fg-3 (quiet) | `#A1A1A1` | ≥ 4.5:1 (AA) | 4.61 / 5.33 / 6.08 |
  | fg-off (inactive) | `#808080` | ≈ 3:1, inactive controls only | 3.01 / 3.49 / 3.98 |

  Each foreground is the lowest grey that meets its target on `bg-2`, except `fg-3`, nudged one level from `#A0A0A0`, a value the reference names for the same role. `bg-rule` is 1.24:1 on `bg-2`, so a card that needs a real edge (the approval card) sits on `bg-1`, where its edge reads 1.44:1. The role names are working names; the final names are Joe's.
- **Why it fits Plexus:** Plexus has no host theme to sit inside, so it can pick one seed grey on purpose and derive everything else from it: elevation steps for surfaces and contrast-solved greys for text. A light theme then comes free. Plan from the start for at most three readable text rungs. Below those, quiet comes from form (caps, tracking, the mono face), not a fourth grey.
- **Reference idea (SYNAPSE, ideas only):** All surface greys are fixed offsets from one seed grey: ground below, panel at the seed, raised and border steps above. The text greys are not a fixed table. Each role (body, secondary, caption, bright, disabled) is solved to hit a target contrast against the worst surface it can sit on. The light-on-dark or dark-on-light direction is whichever gives more contrast, so a light theme flips the ramp on its own. Disabled is deliberately left below the contrast floor, because it only ever paints inactive controls. — `python/synapse/panel/designsystem/tokens.py:159-202, 212-233, 239-249`. Did it work: Mixed. The contrast floor holds at every seed grey, and the comments say a seeded-contrast sweep gates it. The cost is that the quiet end collapsed: caption and secondary text ended up about two levels apart out of 255, which reads as one grey. The note on that says value can no longer carry the quiet rung, so form has to (tokens.py:153-158; Claude outputs/panel-design-state-2026-09-16.md:134-140).
- **Not taken:** Reading a host application's colour scheme, the specific hex values, the token names.
- **Jev:** Jev opt0 p 1.00, confidence 1.00, copy risk of the closest option 0.23; pass 3 copy 0.23 (under the visual 0.5). **Seed:** Joe.

**Typography: size scale, weights, families** (`three-rung-type`)

- **Decision:** Three sizes, sans for words and mono for identifiers, quiet by caps and tracking
- **Why it fits Plexus:** Plexus surfaces carry a lot of identifiers: prim paths, sublayer names, intent hashes, organ ids, predicate text. Use a strict split: mono for every identifier and number the eye has to compare, sans for prose and labels, and only three sizes. Hierarchy inside a node or row comes from weight and caps. In a dense node editor, size changes should be saved for the canvas zoom.
- **Reference idea (SYNAPSE, ideas only):** Text uses three sizes only (body, section title, display), about 12/15/19 px. The fourth size, one pixel below body, was retired because the eye cannot see a one-pixel step. Captions and status lines stay at body size and go quiet through caps, letter-spacing and a mono face. Status-dot and chevron sizes are named separately so nobody counts them as type sizes. Sans is for anything read as words; mono is for anything scanned character by character (paths, tool names, counts, code). Each weight token names a weight the font file actually has. A user text-size control only scales up from the host's default size, never below it. — `python/synapse/panel/designsystem/tokens.py:414-449, 525-552, 591-623, 651-702`. Did it work: Measured. The lowercase x took six pixel rows at both 11 and 12 px, and the display size had been used zero times (Claude outputs/panel-design-state-2026-09-16.md:123-128). Requested weights the mono family could not draw were rendering as regular (tokens.py:534-545). Pinned by tests/test_panel_typography.py.
- **Not taken:** The bundled font files, the tracking values as a table, the font-loading code.
- **Jev:** Jev opt0 p 1.00, confidence 1.00, copy risk of the closest option 0.27; pass 3 copy 0.30 (under the visual 0.5)

**Colour roles: accents, actions, verdict hues** (`two-accent-ceiling`)

- **Decision:** Two accents (action, live presence) plus a muted verdict trio, enforced by a hue-count test
- **Why it fits Plexus:** Give Plexus a written colour budget that a test enforces from day one. One accent for actions. One for live agent presence: a neuron awake, or an organ job running. A muted verdict trio for Verified, Broken and Unknown inside content. On a canvas where organ outputs (images, video) appear, the output is the colour, and the chrome stays grey around it.
- **Reference idea (SYNAPSE, ideas only):** The rule is at most two accent hues in any view. The cool accent is for actions and technical links, and every action uses it, however many there are. The warm accent is for the agent's own presence and for the halt control. Emphasis among actions comes from value on the grey ladder and from weight, not from new hues. There are two status families: full-strength hues for gates and badges, and a muted trio (settled green, amber, soft red) for verdicts inside content. A rendered image is treated as the only chromatic event on its surface, so verdict dots beside it stay quiet. Metadata over an image uses a grey warmed slightly off neutral. — `python/synapse/panel/designsystem/qss.py:321-340; python/synapse/panel/designsystem/tokens.py:279-284, 349-370; python/synapse/panel/face_review.py:115-200`. Did it work: Partly failed. One button kept a third hue about fifteen lines after the comment that forbids it, and the hue-count test and two review documents disagreed on whether the guard was red (Claude outputs/panel-design-state-2026-09-16.md:58-68). The rule existed only in a comment, so it drifted.
- **Not taken:** The specific hues and their names, the stylesheet rules.
- **Jev:** Jev opt0 p 1.00, confidence 1.00, copy risk of the closest option 0.25; pass 3 copy 0.26 (under the visual 0.5)

**Spacing rhythm, density, region layout** (`named-spacing-roles`)

- **Decision:** **Named spacing roles on a 4-px grid, with gaps that step down with nesting depth, as restated for Plexus (Joe, Nov 1).** Plexus names its own roles (none of the reference's). Each nesting level steps its gap down by at least one grid step, and a layout test checks it, because the reference's failure was nesting that read flat (four roles landed on the same gap). No density multiplier and no layout profiles until two real users need different layouts. Joe's decision overrides the visual 0.5 rule for this element only.
- **Why it fits Plexus:** Use named spacing roles on one grid, and make the gaps step down with nesting depth so hierarchy can be seen. Do not build a density axis or layout profiles until there are two real users who need different layouts.
- **Reference idea (SYNAPSE, ideas only):** Spacing sits on one grid (4, 8, 12, 16, 24, 32, 48). Layouts are tagged with a named role (shell, stack, band, row, tag, card, group, turn), and one applier sets the gaps and margins. Density is a single panel-wide multiplier (airy 1.5, standard 1, tight 0.75) that scales gaps, never padding. The top-level regions (rail, context ribbon, faces) come from an ordered manifest; an unknown region is logged and skipped. — `python/synapse/panel/designsystem/rhythm.py:15-61, 116-150; python/synapse/panel/designsystem/tokens.py:708-745; python/synapse/panel/compositor.py:24-35`. Did it work: Partly failed. Shell, group, card and tag all landed on 16 px, so nesting read flat (Claude outputs/panel-design-state-2026-09-16.md:224). Only one layout ever ships, and the profile and density choices left the UI (synapse_panel.py:952-956), which leaves the density axis carried but unused.
- **Not taken:** The role names, the manifest schema.
- **Jev:** Jev opt0 p 0.99, confidence 0.98, copy risk of the closest option 0.56. Pass 3: opt0 adopt 0.85 / copy 0.34; opt1 (plain constants) adopt 0.35 / copy 0.22; opt2 (density switch) adopt 0.14 / copy 0.56; a Plexus-native variant (8-px base, 4 px only inside nodes, regions separated by elevation, a layout test) adopt 0.41 / copy 0.31. **Joe** took opt0 as restated, over the 0.56 pass 1 reading.


### Graph canvas

**Progress and liveness mark** (`status-ring-two-channels`)

- **Decision:** **A thin progress rule along the node's top edge, plus a separate heartbeat dot (Joe, Nov 1).** The rule's length counts completed steps of the organ job and never reaches full until the job is done; the dot pulses while the job is alive, so stalled and moving look different. The three stop states (stop requested, confirmed cancelled, cancel unknown) are drawn on the dot.
- **Why it fits Plexus:** On a neuron or organ node, progress counts completed steps of the organ job and a separate channel shows that the job is alive, so a stalled job and a moving one look different. The halt control should not claim more than it can verify. The plan already weakens 'a halt is immediate' (§3.2), so the mark needs three distinct states: stop requested, confirmed cancelled, and cancel unknown.
- **Reference idea (SYNAPSE, ideas only):** The product mark doubles as the status light. Idle is an open outline. While working, the arc length grows by one step for each completed step, and it stops short of a full circle, so in-flight work can never look finished. Only done closes the ring. Rotation is a separate channel that shows the process is alive, so a stalled job and a moving one look different, and rotation never lengthens the arc. While work is running the same mark is also the stop control, and it offers no stop when nothing is running. — `python/synapse/panel/designsystem/components.py:407-460, 540-583`. Did it work: Unknown. No test or review note was found that measures it.
- **Not taken:** The mark's geometry, the product mark itself.
- **Jev:** Joe chose this over Jev's top pick, the ring (pass 2 adopt 0.81; copy risk 0.59 in pass 1 and 0.56 in pass 2; the higher, 0.59, fails the visual 0.5, though it passed the old 0.6). This option: pass 2 adopt 0.77, copy risk 0.23 · routed here at 0.86


### Inspector

**Status display: health cells and fidelity readouts** (`unknown-is-its-own-colour`)

- **Decision:** **Five distinct marks (verified, broken, unknown, idle, working) with the reason inline on degraded, shown in the inspector (Joe, Nov 1).**
- **Why it fits Plexus:** This adds the visual side to the Unknown/Broken/Verified lesson already in the plan (§3.2 #5). Each of the three outcomes, plus idle and working, gets its own mark, and Unknown is never close to Verified in colour. In the inspector, a degraded item shows its one-line reason inline, with no extra click.
- **Consequence of the placement:** the canvas now carries no verdict marks. On a node, state shows only through the progress rule and heartbeat dot, and the node's one-line receipt. A minimal verdict mark on nodes would be a separate element, if Joe wants one later.
- **Reference idea (SYNAPSE, ideas only):** A small always-visible strip of cells, each with a status dot and a short value. A cell has six states, each drawn differently: ok, amber, red, unknown, idle, working. Unknown means the value could not be measured and is a calm grey, never green. Idle means it was measured and is quiet, so it is not drawn as a pass. A degraded cell shows its one-line reason inline, with no click needed. A fidelity readout shows no data yet in grey words rather than a perfect score, and the code makes green unreachable from a no-data state. — `python/synapse/panel/health_strip.py:13-24, 84-122, 147-154; python/synapse/panel/gate_widget.py:57-130; python/synapse/panel/integrity_readout.py:12-18`. Did it work: Worked after a defect. The fidelity row used to read a perfect 1.0 in green before any operation had run (gate_widget.py:57-78). Source-pin tests now guard it: tests/test_panel_fidelity_honesty_sourcepin.py and tests/test_gate_fidelity_honesty_sourcepin.py.
- **Not taken:** The specific cells, the producer wiring.
- **Jev:** Jev opt0 p 0.95, confidence 0.92, copy risk of the closest option 0.49; pass 3 copy 0.27. Kept: 0.49 is just under the visual 0.5, tied with the receipt rows for the closest any kept visual decision comes. Jev routed it to the canvas at 0.42; **Joe** placed it in the inspector.

**Agent result: structured rows instead of prose** (`fixed-order-receipt-rows`)

- **Decision:** A compact one-line receipt on the node plus the full rows in the inspector
- **Why it fits Plexus:** Make the provenance receipt (Blueprint §5.2 item 5) the row grammar of every Plexus result: writer, intent hash, what was touched, verdict, what could not be verified, budget spent. Show the budget in the organ's own declared unit, and only once the organ has reported it. Build the renderer together with its first real producer, not before.
- **Reference idea (SYNAPSE, ideas only):** A result is a fixed, ordered list of key/value rows: verdict (the one sentence of free model prose allowed), decision (chose X over Y because Z), via (path, mechanism), checks (state, text, ref), paths, by (model, tier, tokens only if measured), actions (with forecast tokens). The rendering cannot vary by which model wrote it, so changing models does not change how the panel reads. Cost is carried in the data but not drawn until a real usage reader exists, and the panel shows tokens, never currency. — `python/synapse/panel/verdict.py:1-40, 465-531`. Did it work: The contract is pinned by tests/test_v2_verdict_contract.py, but its own docstring says nothing in the panel calls the row renderer yet (verdict.py:476-477). The design shipped without a live consumer.
- **Not taken:** The field names as a schema, the voice-contract machinery.
- **Jev:** Jev opt1 p 0.74, confidence 0.61, copy risk of the closest option 0.53 (not the chosen one); pass 3 copy for the chosen option 0.49, under the visual 0.5, so it stays · routed here at 0.93

**Authorship and decision credit layout** (`credit-key-column`)

- **Decision:** A per-attribute opinion stack read straight from USD's property stack: the attribute, then each layer's opinion strongest first, the winner marked, each row naming its writer and intent hash.
- **Why it fits Plexus:** The one-writer-per-sublayer rule gives Plexus a natural key column: writer id or sublayer on the left, the opinion it contributed on the right. In a layer-stack or opinion inspector, this grid shows who won each attribute and why, using the composition result, not model text. Cap the reading width even when the inspector is wide.
- **Reference idea (SYNAPSE, ideas only):** A two-column grid: a narrow mono key column (about 64 px) and a value column. Decision rows come first and the signed author row comes last. The 'why' on a decision is a sentence the model actually wrote, never a summary. A tool the registry cannot classify is still credited, with a note saying so. The block is held to a reading width of about 440 px, even in wide docks. — `python/synapse/panel/face_review.py:258-275, 398-414; python/synapse/panel/decision_log.py:3-31`. Did it work: Failed at first: the grid could draw a decision row but had zero product callers for months (decision_log.py:3-6). A surface was built before its data existed.
- **Not taken:** The SIGNED / DECISION vocabulary and the routing-log source.
- **Jev:** pass 2 (per-option): adopt 0.81, copy risk 0.39 — a Plexus-native variant, chosen because the closest option tripped the copy-risk rule in pass 1 · routed here at 1.00

**Scene and stage state visualisation; node-editor conventions** (`trace-step-rules`)

- **Decision:** A layer-stack step list per prim, with a left verdict rule and delta colours
- **Why it fits Plexus:** Plexus owns its canvas, so the panel has nothing to teach about wires or ports. What carries over is the step-list grammar for stage state: walk the layer stack or the composition of one prim, one row per opinion. The left rule marks the winning opinion, overridden ones and stale ones, and the deltas use the growth/loss colours. A breadcrumb of the prim path plus actions that adapt to the prim type covers the rest. External-reference status (present, missing, modified) works as a badge on reference and payload arcs.
- **Reference idea (SYNAPSE, ideas only):** Network state appears as a vertical list of steps. Each step has a 3 px left rule coloured by verdict: hot for the bottleneck, inactive grey for trivial cooks, neutral otherwise. The header is step number, node label and type. Below it are a geometry delta, coloured green for growth and red for loss, and the cook time, then key parameters, attribute changes, errors and warnings. A context bar shows the network breadcrumb and quick actions that change with the network type. A dependency scan reports present, missing or modified for each external file. The panel has no canvas, wires or ports of its own; it sits beside a host node editor it does not own. — `python/synapse/panel/network_trace.py:455-530; python/synapse/panel/context_bar.py:84-128; python/synapse/panel/dependency_map.py:1-14`. Did it work: Unknown. The only recorded change is that six hard-coded hues in the trace were folded into the shared status family (network_trace.py:455-459).
- **Not taken:** The trace walker, the Houdini network types, the HTML rendering.
- **Jev:** Jev opt0 p 0.96, confidence 0.94, copy risk of the closest option 0.43; pass 3 copy 0.29 (under the visual 0.5) · routed here at 0.99


### Activity rail

**Stop button and the stopping state** (`stop-is-a-request`)

- **Decision:** **Single-stage Stop (Joe, Nov 1):** a named Stopping state that lists the in-flight jobs and settles only on real confirmation, **plus** a per-job list (organ, job, cancelled / still running / unknown) that collapses to one line once settled. The two-stage Stop-then-Halt control is dropped.
- **Why it fits Plexus:** This is the surface for the §3.2 note that a halt is a request. Stop moves the turn into a visible Stopping state that names which organ jobs are still running. Each job then resolves to cancelled-confirmed or Unknown, and only then does the state settle. The record of what was stopped is written to the stage or session layer as plain data, so the next wake reads it and won't resume the work by itself.
- **Reference idea (SYNAPSE, ideas only):** Pressing Stop does not claim idle. The panel stays busy, disables Stop so it can't be pressed twice, changes the status sentence to 'Stopping…', and puts the name of the tool it is waiting on in the sentence's tooltip. It goes back to rest only when the worker actually exits. Tool calls queued in that round after Stop are returned to the model as errors ('cancelled before execution') and are not run. When the turn ends stopped or broken, a settled note goes into the history: the task was stopped, ending it undoes nothing, an operation without a confirmed result may still be finishing, check unknowns before retrying, do not continue the plan unless asked. — `C:\Users\User\SYNAPSE\python\synapse\panel\synapse_panel.py:4400-4418; claude_worker.py:215-221, 252-273, 546-556; synapse_panel.py:1251-1264`. Did it work: Worked. The earlier version flipped to 'Standing by' right away while Houdini was still cooking the tool; the fix is pinned by tests\test_panel_stop_honest.py:1-8. One limit is still open: cancelling the in-flight tool itself was deferred (synapse_panel.py:4402-4408).
- **Not taken:** Cancel that waits on a cooperative flag checked only between tool rounds; in Plexus, cancel has to reach the organ job.
- **Jev:** pass 2 (options compose): adopt 0.95 / copy 0.24 and adopt 0.90 / copy 0.31 kept; the two-stage control (adopt 0.73 / copy 0.23) dropped by Joe · routed here at 0.69

**Liveness when the host is busy, and the retry breaker** (`host-busy-evidence-not-clock`)

- **Decision:** Three states (idle draws nothing / busy / stalled-in-warn) from organ heartbeats, plus an intent-hash retry breaker
- **Why it fits Plexus:** Organ liveness comes from organ evidence: heartbeats, job state, queue position. Plexus never infers it from elapsed time on the surface. A slow organ is a warning-role state with the organ and job named. A retry of the same intent against an organ that still holds the earlier job is refused with a sentence saying which job holds it and since when. Because the Rust core owns the stage thread, the surface can always repaint, which removes the limit SYNAPSE had to admit to.
- **Reference idea (SYNAPSE, ideas only):** While a call is in flight, a three-state cue shows: Idle draws nothing; Busy reads 'tool working'; Stalled reads 'tool is stalled' in the warning colour, not the error colour, because a stall is 'worth a look', not 'crashed'. The state comes from real evidence (the busy flag plus the host's own count of main-thread timeouts), never from a local stopwatch. The module also states its limit: when the host's UI thread is frozen, nothing can repaint. Separately, after two abandoned attempts at the same command while something still holds the host, re-issuing is blocked with a sentence that names what is holding it and for how long: 'Houdini is busy — a X operation has held the UI for Ns. Try again when it finishes.' — `C:\Users\User\SYNAPSE\python\synapse\panel\working_indicator.py:1-50; retry_breaker.py:1-14, 24-49`. Did it work: The breaker came from a real lockup: one 179 s hold became three minutes because the panel re-sent the same command five times (retry_breaker.py:3-6). Both are unit-tested (tests\test_retry_breaker.py, tests\test_working_indicator.py). Live GUI behaviour of the stalled state: unknown. The module itself says the signal can clear before it can be painted (working_indicator.py:40-50).
- **Jev:** Jev opt0 p 0.87, confidence 0.80, copy risk of the closest option 0.29 · routed here at 0.74

**Turn receipt and REVERT** (`turn-scoped-undo`)

- **Decision:** Per-turn receipt: 'N changes in layer X', Revert mutes the layer, refusal names the stronger opinion that depends on it
- **Why it fits Plexus:** Each wake or turn writes its edits into its own delta layer, so 'revert this turn' means muting or removing that layer. That is real rollback, and it is cheap to show. The receipt can name the layer, count the changed prims or attributes, and refuse only when a later opinion depends on it, saying which one.
- **Reference idea (SYNAPSE, ideas only):** After a turn that changed the scene, a quiet receipt row shows 'N CHANGES' and a REVERT verb. REVERT undoes only the undo entries that appeared during that turn, carry the tool's own label, and still sit on top of the stack. If anything else is on top (a manual edit, a selection click, a later turn, Joe's own Ctrl+Z), it refuses with a sentence that names the blocking entry and ends 'Nothing was changed. Ctrl+Z still works.' The receipt hides itself once the history no longer holds the turn. A second, model-routed revert path also exists: it asks the model to run one global undo step and passes in the operation's name. — `C:\Users\User\SYNAPSE\python\synapse\panel\turn_revert.py:8-23, 91-129; synapse_panel.py:1692-1708, 1745-1778, 2596-2626`. Did it work: Mixed. The stack-checked path was built because the old REVERT sent a new model turn that declined on camera (turn_revert.py:3-6). Retiring the receipt after a hand undo is in CHANGELOG.md:225-238, but 'none of the five has been seen in the Houdini GUI yet'. The model-routed path is the failure 'REVERT is a global one-step undo wearing an operation's name' (artist_findings.json id TRUST-3). There were also zero artist-facing undo words (TRUST-2).
- **Not taken:** Host undo groups as rollback (already in NEXTGEN_SCAFFOLD_PLAN §3.2 'Do not take'), and any revert that routes through a model.
- **Jev:** Jev opt0 p 0.97, confidence 0.96, copy risk of the closest option 0.36 · routed here at 0.81

**Parked-proposal card layout, verbs, countdown and settled states** (`consent-card-surface`)

- **Decision:** A parked-proposals tray (an inbox) with counts in the header; the graph node of the parked neuron carries the same badge and opens the card **+** Card plus a stage diff preview (what will change) and the cost in budget units next to the act-named verb
- **Why it fits Plexus:** The parked proposal (§3.2 idea 1) needs a face. A card shows the neuron, the intent, the prims or organ it touches, the budget it will spend, and the level as a phrase. Either verb (named for the act, or Discard; see the gate card below) writes an opinion into the session layer. The card settles only when that opinion is confirmed on the stage. If the write fails, the card says Not on stage and stays live. The settled record lives in provenance, not the card.
- **Reference idea (SYNAPSE, ideas only):** Approval cards appear inline in the conversation's slot. The header gives the level as a plain phrase ('Heads up' / 'Quick review' / 'Approve?' / 'Confirm'), then the operation in mono, then the agent. The body is the description, and the critical level says 'Arbitrary code execution' in words. The footer has a countdown on the left and the verbs on the right. Hierarchy comes from weight, not hue: Approve is bold because a timeout rejects, Reject is regular. The card's level accent was deliberately removed, and the only warm note left is a BLOCKED tag. Critical approval asks for a modal confirm. Review-level cards offer REVERT instead. A decision that didn't reach the gate shows NOT RECORDED and keeps the card live with its verbs. A decision that landed replaces the verbs with an APPROVED or REJECTED tag, disables the card, then hides it, and the chat line becomes the record. The work view comes forward on its own only when a card needs action. — `C:\Users\User\SYNAPSE\python\synapse\panel\gate_widget.py:26-55, 236-322, 352-374, 395-418, 656-715; synapse_panel.py:1628-1631, 1710-1727, 3049-3074; designsystem\tokens.py:864-869`. Did it work: The card design is careful, but it never ran. Every in-process path approves on its own, so no operation has ever waited on a card (artist_findings.json id TRUST-1, blocker; C:\Users\User\SYNAPSE\CLAUDE.md:64-66). A denied tool dead-ends in the chat because the card is wired to a different path (U2, blocker). The parked-state fix is already in NEXTGEN_SCAFFOLD_PLAN §3.2 idea 1; this pattern covers only the card.
- **Not taken:** Countdown auto-reject on a blocking wait, and a card that is drawn but not wired to the path that actually enforces the gate.
- **Jev:** pass 2 (options compose): adopt 0.70 / copy 0.35, adopt 0.74 / copy 0.37 · routed here at 0.96

**How a turn limit is surfaced** (`named-closing-reason`)

- **Decision:** Three-part closing sentence (limit / last effect / how to continue), written as provenance and drawn in the turn
- **Why it fits Plexus:** When a neuron's wake runs out of budget, it ends by writing a named closing reason onto the stage: which limit, what ran last, what did not run, and the state it left. The surface shows that sentence as the turn's last line, in the same three-part shape: limit hit, nothing after X, how to continue.
- **Reference idea (SYNAPSE, ideas only):** When a turn reaches a limit, the last round runs with no tools, and the panel says in words which limit was hit (tool rounds, time budget in seconds, or input-token budget), that nothing changed after the last tool result, and how to carry on ('Send the request again to continue from the scene as it is now'). If a response limit cut a tool call off before it ran, the panel says so and names the dropped calls. A token-limit stop that would have ended with nothing on screen now says so instead of reading as completed. — `C:\Users\User\SYNAPSE\python\synapse\panel\claude_worker.py:380-418, 445-453, 516-536, 617-650`. Did it work: The budgets were added after one turn ran 15 minutes and 5.77M input tokens (claude_worker.py:372-378). The three-limit rule itself is already in NEXTGEN_SCAFFOLD_PLAN §3.2 idea 6; what is new here is the wording. Live verification of the closing line: unknown.
- **Jev:** Jev opt0 p 0.86, confidence 0.79, copy risk of the closest option 0.33 · routed here at 0.77

**What the agent may do alone, and how a denial is worded** (`denial-replans-not-deadends`)

- **Decision:** A denial turns into a parked proposal on the same surface, so deny and approve are one path **+** Denial as an inline sentence with the reason and a 'do it yourself' verb that opens the right Plexus surface **+** Show authority up front: each neuron node lists its allowed acts, and greys out actions the current authority can't reach
- **Why it fits Plexus:** A neuron's tool set and authority are declared in its definition. A denial is never a dead end for Joe: it either becomes a parked proposal on the same surface (the card above), or it says plainly that this needs Joe and gives him the verb to do it. The surface never shows an affordance the neuron's authority can't honour.
- **Reference idea (SYNAPSE, ideas only):** What the unattended worker may call is filtered by an allowlist built from each tool's read-only flag and its derived gate level. Unknown or unclassified tools are denied (fail-closed), and a mode setting that is invalid or conflicts with the profile falls back to the strictest mode. A denial goes back to the model as an error with a one-line reason ('outside what the panel worker may do — run it yourself in the native UI'), so it can plan again; the denied tool is not run. — `C:\Users\User\SYNAPSE\python\synapse\panel\worker_policy.py:89-110, 145-237, 240-254`. Did it work: Mixed. The allowlist landed (CHANGELOG.md:1623), but a denied tool dead-ends in the chat because the approval card sits on a different path (artist_findings.json id U2, blocker). Composite builds were denied while the steps inside them were allowed (U4), and a button's own prompt named a tool the panel may not run (U3).
- **Not taken:** Env-variable mode switches that widen authority, including an 'unrestricted' mode.
- **Jev:** pass 2 (options compose): adopt 0.86 / copy 0.26, adopt 0.83 / copy 0.35, adopt 0.89 / copy 0.16 · routed here at 0.56

**Concurrency: admission refused in a sentence** (`one-task-admission`)

- **Decision:** Per-organ and per-budget admission, refused in a sentence naming the limit
- **Why it fits Plexus:** Plexus wants many neurons running at once, so it shouldn't copy a single global slot. What carries over is admission control in words: when a wake is refused (budget spent, organ at capacity, a conflicting wake on the same prims), the surface says which limit refused it and keeps the request. The refuse-to-start conductor lock in Plexus is the project-level version.
- **Reference idea (SYNAPSE, ideas only):** Before a task starts, the panel reserves the one task slot for this workstation. If another panel already holds it, the send is refused with a sentence ('A task is still running on this workstation. Wait for it to finish…') and the draft is left alone. The reservation is bound to the worker and released only when the worker finishes. The reservation is taken after the approval step on purpose, because approval can run a nested event loop. — `C:\Users\User\SYNAPSE\python\synapse\panel\synapse_panel.py:3819-3830, 3862-3869, 4156; 100-102`. Did it work: Unknown. No dedicated test or finding was seen. CHANGELOG.md:876 mentions keeping worker admission across panel reloads.
- **Not taken:** One task per workstation as the rule.
- **Jev:** Jev opt0 p 0.85, confidence 0.77, copy risk of the closest option 0.24 · routed here at 0.89

**History persistence, scene switching, and closing the panel** (`conversation-follows-stage`)

- **Decision:** Session layer per project, rebind waits for in-flight wakes, close = detach
- **Why it fits Plexus:** In Plexus the session lives on the stage: each project's conversation and provenance is a layer next to its USD layer, so it follows the project by construction. Switching projects in the surface waits for in-flight wakes or shows them still running in the old project. Closing the surface is a detach: neurons keep sleeping and waking under their budgets, and reopening shows what happened while it was closed.
- **Reference idea (SYNAPSE, ideas only):** The conversation is pinned to the scene file it was loaded from. When a file is opened or a new scene started, the panel saves the old conversation and loads the new scene's, but waits if a turn is in flight so the answer lands in the right scene. Save As moves the conversation to the new location. Work from the previous host session is parked, not lost, with a one-line notice and a restore command. Closing the panel saves the conversation and detaches; it doesn't shut down the host-side machinery, so protection stays on for work still finishing. — `C:\Users\User\SYNAPSE\python\synapse\panel\synapse_panel.py:3871-3906, 3923-3992, 4711-4778`. Did it work: Partly. A full re-render of restored turns is still to do (synapse_panel.py:3883-3884). Otherwise unknown; no finding or GUI test was seen.
- **Jev:** Jev opt0 p 0.87, confidence 0.80, copy risk of the closest option 0.16 · routed here at 0.51

**Long-job progress visual** (`honest-progress-field`)

- **Decision:** **A single counted line (n of m) with no graphic** (moved by the visual 0.5 rule). When the organ reports no count, the line says so in words and the node's heartbeat dot carries liveness; no percentage is ever derived from a clock.
- **Why it fits Plexus:** For organ jobs such as ComfyUI batches or render buckets, show counted progress when the organ reports a count, and a clearly different indeterminate state when it does not. Never derive a percentage from a clock. The line fits the space it has, with no hard minimum height (the reference's real failure was fixed heights that overflowed its panel).
- **Reference idea (SYNAPSE, ideas only):** A grid of cells fills as counted work lands. When no count is available, it switches to an indeterminate sweep with a short trail, so it looks alive without inventing a number. The cell edges vary by a small deterministic amount per cell, so the grid reads as territory being claimed rather than a stock progress bar, and it does not shimmer between frames. Reduced-motion shows a static grid instead. — `python/synapse/panel/face_work.py:56-168`. Did it work: The visual is unmeasured. The geometry failed: fixed minimum heights on this and two sibling surfaces push the panel 30-54 px past its declared minimum height, and no owner was assigned (Claude outputs/panel-design-state-2026-09-16.md:160-168).
- **Not taken:** The bucket-grid implementation, the jitter hash.
- **Jev:** pass 1 picked opt0, the cell field (p 0.94), at copy risk 0.58, which fails the visual 0.5. Pass 3: opt2, the counted line, adopt 0.67 / copy 0.08, the best remaining (opt1, the organ's own preview, adopt 0.51 / copy 0.16). The no-count wording is Claude's, to keep the idea's honesty rule · routed here at 0.96

**Agent transcript presentation** (`ruled-turn-transcript`)

- **Decision:** **A provenance-log view, one row per opinion, instead of a chat transcript** (moved by the visual 0.5 rule). Prim paths in any row stay locate chips that select the prim on the stage.
- **Why it fits Plexus:** Plexus has many writers (neurons, organs, Joe), not two speakers, so the record is a log of opinions by writer and sublayer rather than a two-speaker chat. Every prim path in any text should be a chip that selects the prim on the stage. Pick a renderer with real leading.
- **Reference idea (SYNAPSE, ideas only):** Each turn is a reading column with a 2 px leading rule. Human turns colour the rule; agent turns leave it clear for open prose. A speaker label with a mono timestamp opens each group. There is a large gap before a new speaker and a small one between lines from the same speaker, both on the spacing grid. Node and prim paths in text become clickable chips (a small mark plus the mono path) that locate the item. Group breaks use negative space, not timestamp dividers. — `python/synapse/panel/message_formatter.py:40-58, 218-243, 460-538; python/synapse/panel/designsystem/rhythm.py:26-50`. Did it work: Mixed. CSS line-height does nothing in the Qt text widget, so rhythm had to come from block margins instead (message_formatter.py:40-52). An earlier 4 px difference between speaker gaps could not be felt (Claude outputs/panel-design-state-2026-09-16.md:210); the gaps were later doubled (rhythm.py:36-41).
- **Not taken:** The two-speaker identity colours, the HTML-table technique.
- **Jev:** pass 1 picked opt0, ruled turns (p 0.95), at copy risk 0.55, which fails the visual 0.5. Pass 3: opt1, the provenance log, adopt 0.67 / copy 0.21, the best remaining (opt2, split chat and activity log, adopt 0.46 / copy 0.51, does not qualify) · routed here at 0.52

**Parked-proposal card** (`consent-card-weight`)

- **Decision:** A parked-proposal card in Plexus's own form: the predicate that fired and the intent hash on top, a stage diff of exactly what will change, the budget it will spend, and two verbs named for the act (for example Publish to exchange / Discard). Hierarchy by weight; no countdown, because a parked proposal never times out.
- **Why it fits Plexus:** Use this for the acts that always need Joe (Blueprint §5.2 item 7), drawn as the parked proposal from plan §3.2 #1: the neuron stays dormant and the card waits. Hierarchy comes from weight and words, not colour. Give the card a real edge. Choose each verb's name once across the whole product, and only promise a scope the undo can actually deliver.
- **Reference idea (SYNAPSE, ideas only):** The gate level is never a border hue or tag. The header is a sentence-case phrase per level (heads up, quick review, approve?, confirm), set as a label, with the operation in mono and the agent in quiet mono. The body is plain text; the critical level adds one plain line naming the risk, with no colour and no pulse. The footer has a mono countdown on the left (timed levels only) and verbs on the right. The verbs carry no hue; the consequential verb is bold because a timeout defaults to reject. A decided card shows a neutral or blocked tag in the countdown slot and hides its verbs. — `python/synapse/panel/gate_widget.py:27-55, 196-230, 291-321`. Did it work: Partly failed. With tone borders removed, the card's border is the same grey as its fill, so it has no painted edge and the corner radius is its only boundary (Claude outputs/panel-design-state-2026-09-16.md:72-90). Three different controls labelled with the same revert verb meant three different scopes (same doc :172-180).
- **Not taken:** The level phrases verbatim, the timeout numbers, the card class.
- **Jev:** pass 2 (per-option): adopt 0.80, copy risk 0.27 — a Plexus-native variant, chosen because the closest option tripped the copy-risk rule in pass 1 · routed here at 0.99


### Status bar

**Composer send while the host connection is down** (`send-refused-not-queued`)

- **Decision:** Refuse and keep the draft: one sentence, the text stays in the box, nothing replays
- **Why it fits Plexus:** A request to wake a neuron or run an organ is never queued out of sight. If the runtime (the Rust core, or the organ behind the contract) can't take it right now, the surface refuses, keeps Joe's text, and says so in one sentence. In Plexus a deferred request would be a visible opinion in the session layer, never a hidden buffer that replays into a stage that has since changed.
- **Reference idea (SYNAPSE, ideas only):** When the link to the host is down, the panel refuses the send, leaves the draft in the input box, and puts one plain line on the surface saying the message was not sent and will not be replayed, with the next action (connect, then send again). Quick-action pills get the same rule in their own wording: press the pill again. Nothing is held and nothing fires later. A 'held, press Send to release' version was considered but not built. — `C:\Users\User\SYNAPSE\python\synapse\panel\send_guard.py:19-27, 52-78, 100-124`. Did it work: Worked as a fix. Before it, a message typed while the link was down was silently queued, spun forever, then fired into whatever scene was open when the link came back; this was rated a blocker (C:\Users\User\SYNAPSE\harness\notes\closeout-2026-09-15\artist_findings.json id FR-1). The fix is pinned by tests\test_send_guard.py.
- **Not taken:** The fire-and-forget replay queue the bridge still keeps for other callers (ws_bridge.py:364-376, 414-455). Plexus should not have a second, hidden delivery path.
- **Jev:** Jev opt0 p 0.94, confidence 0.91, copy risk of the closest option 0.21 · routed here at 0.46; **status bar confirmed by Joe**

**Status sentence and state-gated controls** (`one-status-sentence`)

- **Decision:** One sentence per project with a fixed precedence; neuron state as node badges in the graph
- **Why it fits Plexus:** Plexus needs one runtime-state sentence per project or neuron, picked by an explicit precedence rule. A good order: stopping > waking/running > parked-for-Joe > settled-result > runtime connection. Each state gets a fixed colour role used for that state only, never decoration, and the controls follow from the state. Because Plexus has many neurons dormant at once, the sentence can sit at project level, with neuron-level marks in the graph (the node-editor convention: a badge on the node, the sentence in the status bar).
- **Reference idea (SYNAPSE, ideas only):** The header shows one mark and one short sentence, chosen by one precedence rule: a turn in flight (working or stopping) beats a finished turn ('Result ready'), which beats the connection's state at rest ('Not connected', 'Worth a look', 'Ready'). 'Idle' is never shown on its own, because at rest the connection is what the panel reports, so a fresh panel says 'Not connected', not 'Ready'. Six states map to six fixed colour roles: grow = connected, fire = working, signal = idle, warn = warning, error = error, slate = offline. While a turn runs, the mark doubles as the halt control. Stop is visible only while working. Connect and REVERT are switched off while working. — `C:\Users\User\SYNAPSE\python\synapse\panel\synapse_panel.py:4452-4478, 4515-4528, 4420-4424, 2587-2593; designsystem\tokens.py:854-861`. Did it work: Partly. The precedence rule exists to fix the panel's first line saying 'Ready.' before it had connected to anything or been given a model (artist_findings.json id FR-2, major). A related problem, that at rest you can't tell 'configured' from 'never configured', was logged as FR-4. Reading the code, the model token now carries a separate live/off state for this (synapse_panel.py:4480-4513). No GUI confirmation was found.
- **Not taken:** The state names and colour tokens themselves.
- **Jev:** Jev opt0 p 0.87, confidence 0.80, copy risk of the closest option 0.44; pass 3 copy 0.22 (under the visual 0.5) · routed here at 0.30; **status bar confirmed by Joe**

**Connection loss and reconnect** (`host-gone-reconnect`)

- **Decision:** A lasting per-organ connection state with last error and next retry, never silenced
- **Why it fits Plexus:** For Plexus the runtime and each organ endpoint (ComfyUI first) is a host that can be gone. The surface should show a lasting, honest state for each ('ComfyUI organ unreachable since 14:02, retrying every 5 s, last error: …'), not a burst of messages that then stops. Connect stays idempotent and says what it did in words.
- **Reference idea (SYNAPSE, ideas only):** The link reconnects in the background with a fixed backoff of 2 s, 3 s, then 5 s. Errors are surfaced only for the first three failed attempts; after that it keeps retrying in silence. The Connect action can be pressed any time, does nothing if already running, and reports what happened as a line in the chat ('running on :port' / 'did not report running' / 'couldn't start: reason'). Its tooltip carries the current state. — `C:\Users\User\SYNAPSE\python\synapse\panel\ws_bridge.py:232-258; synapse_panel.py:1366-1415`. Did it work: Failed in part. A connection failure printed three raw exception lines, then went permanently silent while still failing (artist_findings.json id FR-5, major). The cause is visible at ws_bridge.py:244-250, where errors are emitted only while attempts <= 3.
- **Not taken:** Capping error reports at three and then going quiet while the failure continues.
- **Jev:** Jev opt0 p 0.98, confidence 0.97, copy risk of the closest option 0.26 · routed here at 0.88


---

## 4 · What the reference taught, and what Plexus leaves behind

**What the SYNAPSE panel gets right** (the study's words, condensed): the wording of state. A refused send keeps the draft and says so. Stop stays in "Stopping…" and names what it waits on until the work really ends. Turn limits close with a sentence naming the limit and how to continue. An unmeasured value has its own calm colour, never green. Results are fixed-order rows, not prose.

**What it gets wrong:** the surface often sat apart from what enforced it. Approval cards were drawn but never reached; denials dead-ended in the chat; a second revert path was a global undo wearing an operation's name; reconnect errors went silent after three tries. Rules stated in comments were broken a few lines later, surfaces were built before their data existed, and a 2026-09-16 status note found 22 of 28 open design items waiting on a ruling.

**What Plexus leaves behind, always:** all code, class and widget names, stylesheet text, token names and values, hex colours, fonts and font-loading code, asset files, the product mark's geometry, level phrases verbatim, timeout numbers, and the panel's layout. Also every behaviour the study marked as a failure: a countdown that auto-rejects on a blocking wait, cancel checked only between rounds, env-variable switches that widen authority, Stop reachable only by mouse, and any card not wired to the path that enforces it.

**The one idea Plexus most needs from it:** a single state and receipt grammar. Unknown, Broken, Verified, idle and working each get their own mark; every result is a fixed-order provenance row set; and absence shows as its own state wherever it is read, never as a pass.

---

## 5 · Decisions

### Decided by Joe (Nov 1)

1. **Stop stays single-stage**, with the named Stopping state and the per-job list. The two-stage Stop-then-Halt control is dropped.
2. **Progress on a node is a thin rule along its top edge plus a heartbeat dot**, not a ring.
3. **The one-sentence status and the refused-send notice live in the status bar.**
4. **Copy risk for anything visual is 0.5** (0.6 elsewhere). Re-applying it moved two decisions: long-job progress became a single counted line, and the agent transcript became a provenance log.
5. **The theme seed is a neutral grey around `#2A2A2A`: `#2D2D2D`.** `#2A2A2A` itself is the reference panel's exact seed, so it moved three levels, inside Joe's "around". The derived ramp is in the colour element (§3, system-wide).
6. **Spacing takes Jev's preferred option as restated:** named Plexus roles on a 4-px grid, gaps stepping down at least one grid step per nesting level, checked by a layout test. This overrides the visual 0.5 rule for this element only.
7. **The Unknown mark, with the other four status marks, lives in the inspector.** The canvas carries no verdict marks as a result.

### Decided by Joe (Nov 3)

From the Nov 3 design review, which used Pentagram's Cohere identity as a reference for method only (one root element every surface derives from; generators as the identity), never for its look.

8. **The root element is the ordered line.** Every line that carries information on a Plexus surface is one of two things, and ends in a mark that names its verdict: a layer in a strength-ordered stack (the resolved value first, then the stack that produced it, strongest first, as USD resolves), or a measured span of time or count. Structural edges, such as the `bg-rule` on cards and panes, are exempt and stay as decided. Working concept line: *timing from biology, order from composition*.
9. **The mark never shows state.** The felt disc with its slit is a still emblem. It is never lit, animated or used as a status light, and no value is encoded in its slit. The slit stays a hairline at one fixed angle, stops short of the centre and is never widened into a wedge; the letters of the wordmark are never cut. State lives in the five inspector marks, node badges and rail states (decision 7). The felt black and the paper grey of the render stay in photographs and never become UI colour tokens.
10. **The type families are Atkinson Hyperlegible Next (sans) and Atkinson Hyperlegible Mono, at a 13 px base.** Both were drawn so that similar characters cannot be mistaken for each other, and a misread hash, layer name or prim path is Plexus's worst reading failure. Mono is the identifier voice (principle 5); Next carries prose, display and the quiet caps labels. Principle 5's three sizes step from the base at about 1.3, on the 4-px grid: 13/20, 17/24 and 22/28 (size/line height, px). Both are on Google Fonts; read each family's licence file before bundling them into the panel. Excluded: Space Grotesk and Space Mono (the reference panel's), and IBM Plex ("Plex" sits inside "Plexus").
11. **Holds stay rail states and badges, with the reason inline. There is no sixth mark.** A deliberate hold (a muted neuron, a parked proposal, `Outcome.blocked`) shows where Parked and Stopping already show: the rail tray, the node badge, the tray count and the status precedence. Its reason is always written out and always names the release, for example *neuron muted: 3 wakes in a row refused; unmute with `plexus:state = dormant` in the session layer*. A hold is never mapped to Broken, and the five inspector marks (decision 7) stay five.
12. **The two accents: `accent-action` `#8AA4FF` and `accent-presence` `#4FDCCB`.** Picked by Claude on Joe's ask, independently of the mark: neither comes from the slit's light, and the reference panel's warm presence hue is not taken.
    - **`accent-action` `#8AA4FF`**, a soft periwinkle blue (hue 227). Every control that does something and every link, however many there are; emphasis among actions comes from weight and the grey ladder, never a second action hue. Contrast 6.61 / 5.79 / 5.01 on `bg-0` / `bg-1` / `bg-2` (AA for text everywhere); dark text on an action fill reads 7.25:1 (`#1B1B1B`).
    - **`accent-presence` `#4FDCCB`**, an aqua (hue 173). Only something live: a neuron awake, an organ job running. It draws the heartbeat dot and the progress rule (decision 2) and never text, never a verdict and never the mark (decision 9). Contrast 9.30 / 8.15 / 7.05 on the three backgrounds.
    - **Why this pair.** The two differ in hue and in lightness, so they hold apart without colour: CIE76 ΔE between them is 72.8 for normal vision and 44.8 / 50.1 / 27.5 under simulated deuteranopia, protanopia and tritanopia (Machado 2009, full severity). Blue for action follows the convention people already read; aqua for presence reads as a live signal without borrowing a verdict's meaning.
    - **Rules the hue-count test enforces.** At most these two accent hues in any view. The verdict trio (Verified, Broken, Unknown) stays muted, inside content only, and when its values are chosen each must sit at least ΔE 20 from both accents under all four vision simulations, so Verified never reads as "awake". Organ output stays the only other colour on its surface.

### Still open

Every element in §3 is decided. Nothing from the Nov 3 review is open. The verdict trio's values are still to choose, under decision 12's distance rule.

### Optional additions Jev scored well

Pass 3 was a copy check on each existing pick, not a re-decision, so these runner-ups were not adopted. Each clears adopt ≥ 0.5 and copy risk < 0.5 and composes with the decided option. They are Joe's to add or leave:

1. **Shape-coded status marks** (filled, hollow, dashed), so the five marks survive colour-blindness and greyscale: adopt 0.86, copy 0.17. Composes with the five inspector marks.
2. **A composition-arc overlay on the canvas** (reference and payload arcs badged): adopt 0.76, copy 0.17. Composes with the layer-stack step list in the inspector.
3. **A count strip beside the project status sentence** (dormant / waking / parked / failed, clickable to filter the graph): adopt 0.74, copy 0.31.
4. **A sortable per-sublayer receipt table**: adopt 0.76, copy 0.47. Composes with the one-line node receipt and inspector rows.

---

## Appendix · How Jev was used

- **Model:** `jev-1.14.0` (`jev-latest`), TypeSafe System One.
- **Pass 1:** 24 elements × 3 questions over the same state: `decide` (choice among the element's options), `route` (choice among six surfaces), `too_close` (noul: does the closest option copy the reference?). 31,028 input tokens.
- **Pass 2:** the 6 elements where one choice was the wrong question: four whose options compose (low confidence because probability spread across good options) and two whose pick the copy-risk rule had moved onto an option Jev scored near zero. Each option got two nouls, `adopt` and `copy`; two Plexus-native variants were added for the copy-risk cases.
- **Pass 3 (after Joe's Nov 1 decisions):** every option of the ten visual elements pass 2 had not covered, as `adopt` / `copy` nouls (12,252 input tokens), plus one Plexus-native spacing variant.
- **Policy in code, on top of Jev's raw answers:** copy risk ≥ 0.6 moves the pick, or ≥ 0.5 for visual elements, using the higher of the pass 1 reading (closest option only) and the per-option reading (pass 2 or pass 3); system-wide rules route to every surface; composable options are included at adopt ≥ 0.5 and copy under the threshold; alternative presentations take the single best; Joe's decisions override Jev.
- **Raw answers:** `docs/plexus/ui_design_jev.json` keeps every probability, so weights and thresholds can change without re-running Jev.
- **State given to Jev:** what Plexus is, who Joe is as a user, Plexus's no-copy and parked-waiting rules, and each element's observed idea, whether it worked, the idea restated for Plexus, and what must not carry over. Jev never saw SYNAPSE code.
