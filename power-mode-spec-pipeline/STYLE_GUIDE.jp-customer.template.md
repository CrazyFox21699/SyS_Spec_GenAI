# System test specification style guide — Japanese customer (template)

Customize this once per program; paste the **Approved examples** block into prompts for Ollama / Copilot.

## Output language

- Primary narrative language: **`[JA | EN | JA+EN]`** (strike unused).
- Technical Given may stay **English signal names** if customer agrees; clarify in glossary.

## Per testcase sections (minimum)

| Section | Requirement |
|---------|--------------|
| **Description** | One scenario only. State **what is unique** vs similar cases (`neighbors_similar_ids` in IR). Customer-grade tone — no vague “verify behavior”. |
| **Given** | Every value/condition the expectation depends on, **enumerated**. Tie every item to glossary terms. Timing/debounce/explicit waits must appear here or in stimulus. |
| **Expectation** | Observable outcomes only — modes, signals, timestamps/bounds, forbidden transitions. No implementation internals unless customer doc allows. |

## Tone (JA customer)

- Consistent endings and register (`である調` vs `ですます` — pick one program-wide).
- Use **canonical product terms** from glossary; forbid literal mixing of synonyms.
- Avoid copy-pasted Description across rows — **vary the distinguishing trigger**.

## Forbidden / discouraged

- Vague verbs: 「動作確認する」「適切になる」without measurable criteria.
- Missing units or comparator on numeric conditions.
- Expectations that contradict IR predicates (validators must flag).

---

## Approved examples (replace with gold samples from signed reviews)

### Example gold triplet — A

**Description**  
*[paste customer-accepted JA or bilingual text]*

**Given**  
*[paste enumerative Given]*  

**Expectation**  
*[paste measurable Expectation]*  

### Example gold triplet — B

*(repeat 3–5 times total for few-shot prompting)*  

---

## Glossary snippet (minimal)

| EN id | JA customer term | Definition / note |
|-------|-------------------|-------------------|
| NORMAL | *[term]* | |
| SLEEP | *[term]* | |
| IGN_STABLE_OFF | *[term]* | |
