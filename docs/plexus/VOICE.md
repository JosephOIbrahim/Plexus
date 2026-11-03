# Plexus · Voice and words

**One word per thing, and each word from the right vocabulary.** This page is the lexicon every Plexus surface uses: the README, the docs, the harness output, release notes, error messages, the panel and the stage's own flags.

It builds on the closed artist word table in `docs/plexus/ADVANCEMENT_RESEARCH_2026-11.md` (`ux.state-model`) rather than starting a second one, and it follows the root element in `UI_DESIGN.md` §5, decision 8: every line that carries information ends in a word that names its verdict.

## Three vocabularies, three territories

| Vocabulary | Used for | Examples |
|---|---|---|
| **USD** | Layers, opinions, composition | stage, layer, sublayer, opinion, prim, property, strongest first, composed |
| **Nervous system** | When and why an agent acts | neuron, dormant, wake, predicate, budget, axon, membrane, exchange, organ |
| **Plain English** | Everything off the stage | the harness, gates in the harness, attempts, releases, panel chrome |

**A new biological word gets in only when the runtime behaves the way the biology does.** "Refractory", for example, stays out: a refractory period is a fixed dead time after each spike, while a Plexus budget allows N wakes in a sliding window. The two agree only when N is 1, so the words are "over budget".

## State words

| Word | Means | Never |
|---|---|---|
| **dormant** | A neuron waiting for its predicate. The resting state. | asleep, idle, sleeping |
| **wakes** | A neuron's predicate came true and the budget allowed it | fires, triggers |
| **neuron muted** | Three wakes in a row were refused; it stays muted until released | muted, alone. To a USD operator a muted *layer* is one left out of composition, so "muted" always names its object: *neuron muted* or *layer muted* |
| **parked** | A proposal waiting for Joe. The neuron stays dormant; nothing times out | pending approval, blocked |
| **lands** | A write reached the neuron's own layer and was saved | succeeded, committed |

The artist words for results come from the research table: Working, Verified, Already made, Broken, Unknown, plus the rail states Parked and Stopping, which are not marks. Renaming Verified to Made is Joe's open wording call.

## Three verbs for what didn't happen

| Verb | Means | Example |
|---|---|---|
| **refused** | Nothing ran | "Wakes over the budget are refused." |
| **denied** | The neuron's authority can't do it; it becomes a parked proposal | "Denied: the tool is not on the neuron's allowlist." |
| **dropped** | It ran, and the result was thrown away | "Write dropped at the membrane: the path is outside the allowlist." In the harness: "Attempt 4 dropped at `layers`." |

## "Gate"

The Spec's own terms stay, always with their qualifier: **budget gate, risk gate, publication gate**, the frozen test **T5 · Gate**, and the module `plexus/membrane/gate.py`. The harness's checks are **harness gates** (`layers`, `core`, `cargo`, `unit`). A bare "gate" names nothing. Panel chrome uses neither: a proposal waiting for Joe is a **parked-proposal card**, not a gate card.

## Voice

- **No first person in product text.** The system reports; it doesn't say "I".
- **No "thinking…", no spinners in words, no emoji.**
- **Lead with the verdict, then the reason, then the release.** "Neuron muted 14:02: 3 wakes in a row refused (budget 1 per 10 s). Unmute with `plexus:state = dormant` in the session layer."
- **Units on every number.** `30.8 min`, `250 ms`, `0.31 > 0.2`.
- **Wit only when it is true in both registers.** "T8 · Blindness" (the runtime is blind to the engine's vocabulary) and "Nothing has merged. Promotion is yours." are fine. A joke that is only a joke is not.
- **Verbs name the act.** A button says what will happen ("Write the hint", "Discard"), never "OK" or "Approve".

## Reserved words

These never appear in Plexus code, tokens or UI text:

- **Engine vocabulary outside the organ.** Anything matching T8's `ENGINE_TERMS` (`tests/acceptance/phase2/test_t8_blindness.py`): node class names, `prompt_id`, `class_type`, the sampler's `cfg`, and the rest of that list. Import the pattern; never copy it.
- **`synapse` as a key or token.** The guard in `.claude/hooks/_common.py` treats a quoted `synapse…` key as a dependency. Prose that names SYNAPSE as a reference is fine.
- **Another studio's or product's identity register.** From the Cohere reference: cell, atmosphere, pebble, "new nature". Plexus's colour tokens are role names (`bg-0`, `fg-1`, `accent-action`), never natural-material names.
- **Any design studio's name** in a file, token or asset.

## Names recorded, not renamed

These names are frozen in the Spec, the tests or `CONTRACT.md`. They stay as they are and are batched for Spec Patch 02 rather than changed piecemeal: `cool()`; `CozyOrgan` beside the organ id `comfyui`; `created` and `createdAt`; `budgetWindow`; the frozen test file names; and the Spec's gate terms above.
