# explain-plain

Explain or summarize any source — a tracker issue, a file, a diff, a chat thread —
in plain, everyday English. Laymen-first, bulleted, no jargon.

## Overview

The failure mode this guards against is an explanation that is technically
accurate but only readable by someone who already understands the thing. This
skill produces the opposite: a takeaway a first-time reader gets on one pass,
backed by a source that was actually read, not recalled or guessed.

## When To Use

Any request to explain, summarize, or "what does this mean" for:

- A tracker issue or PR description
- A file, function, or diff
- A chat thread, meeting note, or long message
- A spec, design doc, or error message

Not for: requests that ask for code changes, technical review, or a decision —
those want engineering output, not a plain-English summary.

Two modes. **Written** (the default) is the whole explanation in one reply.
**Tutor** (§ *Tutor mode*) teaches it over several turns; use it when the reader
asks to be walked through, taught, or quizzed.

## Workflow

1. **Read the real source first.** Open the file, fetch the issue, read the
   thread. Never summarize from memory or from a filename/title alone.
2. **Keep every fact, cut only the words.** Every limit below governs *phrasing*,
   never *content*. If a stated fact does not fit the takeaway or a list stays
   under its cap, the fix is another line or another bullet — never dropping the
   fact. An explanation that reads simply but left out something the source
   states has failed, even though it looks like a clean pass.
3. **Lead with the takeaway.** One to three lines — under 60 words — before any
   bullets: what this is and why it matters. The 60 words are for that opening
   framing only; the facts themselves belong in the bullets that follow, not
   inside the cap.
4. **Bullet anything with more than one part.** A sentence trying to hold two
   or more facts becomes a list instead. Keep a list to 7 items; past that,
   group related facts under a sub-heading rather than cutting any of them.
5. **Strip jargon, metaphors, nested clauses, and field names.** If a word
   needs the source's own vocabulary to parse (a status enum, an internal
   field name, an acronym), replace it with what it means in context. Keep
   sentences averaging under 20 words, and let none run past 30.
6. **Flag gaps honestly.** If the source doesn't state something, write "not
   stated" — never fill the gap with a plausible-sounding guess.
7. **Self-check before replying.** Read the answer back once as a first-time
   reader would, then check it against the source a second time for anything
   left out. If any line needs a re-read, an unexplained term, or a fact is
   missing, fix it before sending.

## Tutor mode

Teach like a patient person who has read the source closely.
Workflow steps 1, 2, 5, 6 and 7 apply to every turn: read first, plain words and
the sentence caps, never guess, self-check. Drop no facts: one that doesn't fit an
idea's turn gets a further turn, or goes in the all-at-once version. Workflow steps
3 and 4 (takeaway, bullets) are for written mode, and tutor step 3's flagged
analogy per idea is the exception to step 5's no-metaphor rule.

1. **Plan the path.** From the source, pick the 2-4 ideas the reader needs, in the
   order they build. Open with how many parts there are, and that they can have it
   all at once: "Three parts. Say 'all at once' for the full version."
2. **One idea per turn.** A few short sentences, under about 150 words. A term you
   cannot avoid gets an everyday definition the first time it appears.
3. **One honest analogy.** Tie an everyday example to the real mechanism, then say
   in one line where it stops matching. No invented stories. If nothing fits
   honestly, skip it.
4. **Pause.** End the turn with one short question: a check on that idea, or
   whether to go on. Then stop and wait. Never use it to ask for a decision or a
   preference; ask that separately, after the explanation, and say it is one.
5. **Check the core.** After the last idea, ask 2-3 basic questions, one at a time.
6. **Hint, don't correct.** On a wrong answer, point at the part they missed and ask
   again. After two wrong retries, give the answer in a sentence or two, say why,
   and move on.
7. **Only what is known.** Where the source is silent, say so. When the topic leans
   on outside knowledge (a standard, a protocol), check it against a reference and
   say it comes from outside the source.

About every fifth turn, repeat the all-at-once offer in a few words before the
closing question, but not on a turn that gives a hint. If the reader asks for
everything at once, switch to written mode.

## Where the numbers come from

The limits in Workflow steps 3-5 and tutor steps 1, 2 and 6 are this workflow's
own rules, not preferences — each one is set from a stated basis below, not
copied verbatim from a single published number (the 30-word sentence cap, for
instance, is this workflow's own margin above the ~25-word figure gov.uk and the
Plain English Campaign use). Workflow step 2 exists because these limits, left
unqualified, measured worse than a bare "explain this" in the source project's
eval of this skill — the model was cutting facts to make the numbers, not just
the prose.

| Limit | Basis |
|---|---|
| Sentences average under 20 words, none over 30 | The Plain English Campaign and gov.uk both put the average at 15-20 and cap a single sentence near 25. |
| No list over 7 items | Miller (1956) put working memory at 7±2. Cowan (2001) revised it down to about 4 real chunks. |
| Takeaway under 60 words | The size of the 1-3 lines step 3 already asks for. |
| Tutor: 2-4 ideas, a turn under about 150 words | The ideas rest on Cowan's (2001) ~4 chunks. The word count is this workflow's own rule: in the source project's eval, first replies averaged 139 words with the target and 207 without. Two retries before the answer is also this workflow's own rule. |

Sentence length and word length are also what drive the standard readability
scores — Flesch Reading Ease (Flesch 1948) and the Flesch-Kincaid grade (Kincaid
et al. 1975). Those are worth knowing as the reason the limits above are the
lever, but they are not rules here: nobody computes them while writing, and a
rule nobody can apply is decoration.

**Hitting the limits is a floor, not a verdict.** They measure the shape of the
prose, not whether it is organized or whether a term is familiar to *this*
reader. They are gameable too: split every sentence in half and the numbers
improve while the writing does not.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "The title already says what this is, no need to open it." | Titles compress away the part that usually matters. Open the source. |
| "This term is standard, everyone knows it." | The reader of a plain-English summary is, by definition, someone who might not. Replace it. |
| "The source doesn't say, but it's probably X." | That's a guess wearing a fact's clothes. Say "not stated." |
| "One long sentence covers it, bullets are overkill for two facts." | Two facts in one sentence is exactly the case bullets exist for. |

## Red Flags

- A summary written before the source was opened.
- In written mode, a takeaway longer than 3 lines, or missing entirely.
- Any jargon term, metaphor (other than tutor mode's flagged analogy per idea), or internal
  field name left unexplained.
- A stated fact that isn't actually in the source.
- A sentence carrying more than one distinct point.
- A fact the source states that the explanation doesn't — a length limit was
  followed by cutting content instead of cutting words.

## Verification

Before sending the explanation (in tutor mode, each turn), confirm:

- [ ] The source was actually read before the first reply (file opened, issue fetched, thread read).
- [ ] Written mode: a 1-3 line plain-word takeaway leads the answer.
- [ ] Written mode: anything with more than one part is a bullet, not a run-on sentence.
- [ ] No jargon, metaphor (bar tutor mode's flagged analogy per idea), nested clause, or raw field name survives unexplained.
- [ ] Every unstated detail is marked "not stated," not guessed.
- [ ] No sentence runs past 30 words, and no list past 7 items.
- [ ] Compared the explanation against the source a second time for anything left out, not only facts cut to hit a limit.
- [ ] Read back once as a first-time reader — no line needed a second pass.

## Known limitation

This is a trigger-based skill: it shapes behavior when invoked, but nothing in
this harness rewrites or validates Claude's final text automatically. It cannot
guarantee every response follows these rules — only that following them was
asked for. The numeric limits are the part a reader could check after the
fact. The failures that cost the most cannot be checked that way at all: a fact
that was invented, a source that was never opened, or a gap that should have
read "not stated".
