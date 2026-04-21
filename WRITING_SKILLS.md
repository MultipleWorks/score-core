# Writing Score Skills

A practical guide to creating skill files that work reliably in production.

This guide is for anyone writing skills for a Score-compatible AI assistant —
no technical background required.

→ [What is a skill?](#what-is-a-skill)
→ [When to create a skill](#when-to-create-a-skill)
→ [How to structure a skill body](#how-to-structure-a-skill-body)
→ [How to know if your skill is working](#how-to-know-if-your-skill-is-working)

---

## What is a skill?

A skill is a piece of your organisation's knowledge, written down in a form
your AI assistant can reliably use. Not a prompt. Not a document. A skill is
specific, structured, and permanent — it fires automatically when it's needed,
every time, without you having to explain it again.

The difference between a skill and a prompt: a prompt is something you write
for one conversation. A skill is something you write once and the assistant
uses forever.

---

## When to create a skill

**Create a skill when:**

- You find yourself explaining the same thing to the AI repeatedly
- You want a consistent output regardless of how the question is phrased
- The answer involves facts that should never be guessed at (rates, standards,
  brand rules, policy)
- You want the AI to behave differently for your organisation than it would
  for anyone else

**Do not create a skill for:**

- One-off tasks — use a regular conversation
- General knowledge the AI already has — you are adding noise, not value
- Context that changes with every conversation — put it in the message instead
- Everything — a library of 200 skills with broad triggers is harder to
  maintain than 20 focused ones

---

## How to structure a skill body

Two types of skill need different structures.

### Reference skills

Reference skills contain facts the assistant must know and never invent. Brand
guidelines, rate cards, credentials, policy. Write these exhaustively. Every
locked value — every hex code, every fee, every rule — must be in the body. If
it is not there, the assistant will guess, and guessing on facts is exactly what
skills exist to prevent.

```
## Reference skill structure
- Context: what is this skill for?
- The facts: every specific, locked value
- Rules: what must always / never happen
- (Optional) What to avoid
```

### Action skills

Action skills instruct the assistant how to behave in a specific situation.
Proposal review, email drafting, meeting prep, pricing conversations. Write
these as instructions, not facts.

```
## Action skill structure
- Context: what situation is the assistant in?
- What to do: step by step or structured output
- What good looks like: the standard to aim for
- (Optional) What to avoid
```

### The golden rules

**Write in second person imperative.** "Review the proposal for X" not "This
skill reviews proposals for X." The body is injected directly into the
assistant's context — write as if you are briefing the assistant directly.

**Be exhaustive on anything that should never be guessed.** If the rate is
HKD 11,000/day, write that number. If the brand colour is #0F4C75, write that
hex code. Leave no gap for invention.

**Keep it under 500 words.** Skills can fire simultaneously — when they do, all
their bodies combine. Long bodies crowd out each other and the actual question.
If your skill is growing past 500 words, split it into two focused skills.

**Test it.** Use the test panel to send a real message and see whether the skill
fires and whether the response reflects what you wrote. If the assistant says
something that is not in the skill body, the body has a gap.

---

## How to know if your skill is working

**The gap log** shows you every time the assistant refused to answer an
organisational question because no skill covered it. Every gap log entry is a
signal — either a skill is missing, a trigger phrase is wrong, or a question was
asked that nobody had anticipated. Review it regularly.

**The library health check** surfaces skills that have never fired, skills with
overlapping triggers, and skills that violate the format rules. Run it when the
library grows or after importing a batch of skills.

---

*For the full technical specification, see [score_spec.md](score_spec.md).*
