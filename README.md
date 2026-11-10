# o2i-lexicons

Default residual lexicons for [orthography2ipa](https://github.com/TigreGotico/orthography2ipa).

A lexicon in this package holds only words that the orthography2ipa rules get wrong. Each entry is one of two kinds:

- An **exception** is a word whose reading the spelling cannot give, such as the height of a stressed mid vowel or the value of ⟨x⟩. A cited source states this for its class. An exception is always meant to be used.
- A **patch** is a word that a rule could reach and that the rules of the recorded orthography2ipa version get wrong. Each patch names its gap: the orthography2ipa pull request or the rule lead that will reach it. The patches shrink as rules land, and a caller reads them only on request.

Each entry names the gold it came from, the tier and licence of that gold, and a reason class.

The package is enabled in code, never by installing it. An installed package changes no output until the caller enables it.

## Data layout

Each language has an exception directory, `o2i_lexicons/data/<code>/`, and a patch directory, `o2i_lexicons/data/patches/<code>/`. Each directory holds one pair of files, and no word is in both:

| File | Content |
| :--- | :--- |
| `<source>.tsv` | One `word<TAB>ipa` pair per line. UTF-8, NFC, lowercase words, sorted, no duplicate word. A patch file can be empty. |
| `<source>.meta.json` | The `kind` of the file, the source dataset, its URL, tier and licence, the build command, the orthography2ipa version whose rules got each entry wrong, where the stress of the entries comes from, and the reason class of each word. An exception sidecar gives the citation of each word in `citations`, and a patch sidecar gives the gap of each word in `gaps`. |

`o2i_lexicons/schema.py` states the contract, and the tests apply it to every packaged file.

A reason class is one of `loanword`, `proper_noun`, `lexical_stress`, `irregular`, `acronym` or `homograph_default`. Each of these claims a linguistic fact, so the sidecar states the evidence for each class in use. A word that has no evidence other than the data is `unclassified`.

Only a gold that can gate a quality decision in orthography2ipa can supply entries. A silver set (LLM-generated or engine-pinned) never does, and neither does the output of a system that orthography2ipa benchmarks against.

`stress` is `source` when the entries carry the stress marks of their source. It is `rules` when the source has no stress marks: the file then holds none, and the orthography2ipa stress rules place the stress on output.

## How orthography2ipa uses a lexicon

The package declares one entry point per language code in the group `orthography2ipa.lexicons`. Each entry point loads `o2i_lexicons.tsv_path`, and orthography2ipa calls it with the code. The entry point only makes the lexicon discoverable. The transcription is a function of the spec and the input, never of the environment, so the caller passes the lexicon to the engine:

```python
from orthography2ipa import G2P, Pipeline, packaged_lexicon

engine = G2P("en-GB", pipeline=Pipeline(lexicon=packaged_lexicon("en-GB")))
```

The patches are in a second entry-point group, `orthography2ipa.lexicon_patches`, whose entry points load `o2i_lexicons.patch_tsv_path`. `packaged_lexicon(code, patches=True)` adds them to the exceptions, and an exception wins over a patch of the same word.

The lexicon belongs to that engine. Another engine in the process does not see it, and an engine with no pipeline runs on the rules. The `word_exceptions` of a spec win over the lexicon. The package's own API:

```python
import o2i_lexicons

o2i_lexicons.available_codes()            # the codes with an exception file
o2i_lexicons.available_codes("patch")     # the codes with a patch file
o2i_lexicons.tsv_path("en-GB")            # the exception file for a code
o2i_lexicons.load_meta("en-GB")           # its sidecar
o2i_lexicons.patch_tsv_path("en-GB")      # the patch file for a code
o2i_lexicons.load_patch_meta("en-GB")     # its sidecar
```

## Packaged lexicons

| Code | File | Source | Tier | Licence |
| :--- | :--- | :--- | :--- | :--- |
| `en-GB` | `wikipron.tsv` | [WikiPron](https://github.com/CUNY-CL/wikipron) `eng_latn_uk_broad.tsv`, scraped from Wiktionary | crowd-scraped | CC BY-SA 4.0 |
| `pt-PT` | `infopedia.tsv` | The Infopédia rows of [portuguese-unified-pronunciation-lexicon](https://huggingface.co/datasets/TigreGotico/portuguese-unified-pronunciation-lexicon), from the Porto Editora dictionary | lexicon-derived | CC BY-SA 4.0 |
| `pt-BR` | `nilc.tsv` | The training file of the NILC Aeiouadô transcriber (`etc/unitex_sample_transcribed.txt`), human-revised by one research team and not independently verified, with some readings from hand-typed pt.wiktionary lines | expert-human | CC BY-SA 4.0 |

Each code has the file in its exception directory and in its patch directory.

Stress on the en-GB entries comes from the orthography2ipa rules, not from the source. WikiPron scrapes Wiktionary with stress removed (`"stress": False` in its `data/scrape/lib/scrape.py`), so the published file holds no stress mark. The sidecar records this as `"stress": "rules"`, and the orthography2ipa stress rules mark each entry on output, as they mark an entry of `word_exceptions`.

An en-GB entry is a non-rhotic reading, because the en-GB spec models Received Pronunciation. WikiPron gives some words several readings, some of them rhotic (course [kuːɹs], drawer [dɹɑɚ]). The build takes the first reading that has no r-coloured vowel and no /r/ before a consonant or at the end of the word. Roach (2004, "British English: Received Pronunciation", *JIPA* 34(2)) lists no r-coloured vowel in the inventory (p. 243), and his transcription has /r/ before a vowel only (p. 244: north [nɔːθ], more [mɔː], around [əraʊnd]). The build never edits a reading. A word with no non-rhotic reading leaves the lexicon, and `build_lexicon.py --excluded` lists it.

The pt-PT entries are the Infopédia rows of the dataset: the rows with an `infopedia_url`, including the rows that Infopédia and Wiktionary share with the same reading. Infopédia transcribes the European Portuguese standard, and the orthography2ipa `pt-PT` spec models that standard. A lexicon on `pt-PT` does not reach its child lects, such as `pt-PT-x-lisbon`.

The entries carry the stress marks of Infopédia (`"stress": "source"`). Infopédia writes three sounds with other symbols than the spec does, and the build writes the spec's symbols:

| Infopédia | Spec | Sound |
| :--- | :--- | :--- |
| `ə` | `ɨ` | the reduced vowel, an allophone of `ɨ` in the spec |
| `r` | `ɾ` | the tap |
| `ʀ` | `ʁ` | the strong rhotic |

A reading that writes `r` where the spelling has the strong rhotic (an initial `r`, `rr`, or `r` after `n`, `l` or `s`) is left out, because there `r` is not the tap. Infopédia writes an optional vowel as `(ə)`. The dataset gives both forms, and the entry takes the full form, as the spec writes the vowel. The rows that the corrections overlay of the orthography2ipa board lists are left out: they contradict a written accent, lack the stress mark, or transcribe another headword.

Infopédia transcribes the Lisbon (Estremenho) speech, and the `pt-PT` spec models the more conservative norm. The `pt-PT-x-lisbon` notes list the Lisbon deltas, and the build treats each one that Infopédia carries:

| Lisbon delta | Infopédia | pt-PT spec | Build |
| :--- | :--- | :--- | :--- |
| ⟨ei⟩, and ⟨e⟩ before ⟨x⟩ | [ɐj] (leite, êxito) | [ej] (leite `ˈlejtɨ`) | writes [ej] where the rules read the vowel as ⟨e⟩, or read an English ⟨a⟩ for [eɪ] (basebol) as [a] or [ɐ]; leaves any other [ɐj] out (rugby), except in a word spelled with ⟨ai ay aj⟩ |
| stressed ⟨e⟩ before a palatal | [ɐ] (espelho, coelho) | [e] or [ɛ], by word | leaves the word out, because the vowel cannot be recovered |
| ⟨ou⟩ | [o] | [o] | nothing to do |
| the strong rhotic and the reduced vowel | [ʀ], [ə] | [ʁ], [ɨ] | writes the spec symbols |

Infopédia marks the nasality of a nasal diphthong once, on the glide (trem `ˈtɾɐj̃`, tensão `tẽˈsɐw̃`). The spec writes the nucleus nasal too, [ɐ̃j̃] and [ɐ̃w̃] (Mateus & d'Andrade 2000), so the build writes `ɐj̃` as `ɐ̃j̃` and `ɐw̃` as `ɐ̃w̃`.

The build compares the rules with the mapped reading, so a word whose only difference was [ɐj] against [ej] is not a rules miss. A reading with a stress mark between a consonant and the vowel after it (yakuza `jakˈuzɐ` for `jaˈkuzɐ`) places the mark inside the onset, and the build takes the next reading of the word or leaves the word out.

The primary stress mark of an entry stands before the onset of the stressed syllable. The onset is the longest sequence before the stressed vowel that a Portuguese syllable can open with: one consonant, or one of the fourteen obstruent + liquid clusters that Cunha & Cintra list as inseparable (bl, br, cl, cr, dr, fl, fr, gl, gr, pl, pr, tl, tr, vr; *Nova Gramática do Português Contemporâneo*, 7th ed., p. 64). Mateus & d'Andrade give the same fourteen as the onset clusters of European Portuguese ("The syllable structure in European Portuguese", D.E.L.T.A. 14(1), 1998, pp. 14-15, examples (2)).

Cunha & Cintra (p. 64) say that a medial gn, pn, ps, pt or tm can stand in one syllable or in two (a-pto, ap-to). Mateus & d'Andrade decide this for European Portuguese. The clusters of their example (1), [ɡn pt ks tm] among them, "do not belong to the same syllable" (p. 15), and they place "an empty nucleus between the consonants" that "is not filled at the phonetic level in EP" (pp. 17-18). So a consonant before the onset opens a syllable of its own, and the mark goes after it. Infopédia often puts the mark before the whole cluster, and the build moves it:

| Word | Infopédia | Entry |
| :--- | :--- | :--- |
| agnelo | `ɐˈɡnelu` | `ɐɡˈnelu` |
| afixar | `ɐfiˈksaɾ` | `ɐfikˈsaɾ` |
| axioma | `ɐˈksjomɐ` | `ɐkˈsjomɐ` |
| epiblasto | `ɛpiˈblaʃtu` | `ɛpiˈblaʃtu` |
| anguífero | `ɐ̃ˈɡwifɨɾu` | `ɐ̃ˈɡwifɨɾu` |

A glide after a consonant goes with the vowel after it ([kw ɡw], and [sj] in axioma). An affricate of a loanword is one consonant (ketchup `kɛˈtʃɐp`). A cluster at the start of a word stays whole, because Cunha & Cintra (p. 64) call an initial gn, pn, ps inseparable (gnomo `ˈɡnomu`). A glide alone between two vowels "can associate with the onset of the following syllable ... and it becomes then ambisyllabic" (Mateus & d'Andrade, p. 29), so the entry keeps its mark on either side of it (gaiolo `ɡajˈolu`, kilowatt `kilɔˈwɔt`).

A morpheme boundary outranks the onset rule. The mark never moves across a prefix seam that `silabificador.morphology` lists (sub + locar, but not sublime). The build reads the seam with `build_lexicon.prefix_seam`, keeps the entry's mark there, and lists the word in `stress_seam_words` of the build report.

The build moves only the mark: each entry keeps its sounds and its stressed vowel. `lexicon_build.onset_stress` places the mark, and the build report counts the entries in `stress_onset`. The pt-BR entries follow the same rule. In Brazilian Portuguese the split clusters take an epenthetic vowel (Mateus & d'Andrade, p. 16: pa[ki]to), so their first consonant is outside the stressed syllable there too (flexão `flekˈsɐ̃w̃`).

Each token of an entry must be in the spec's token inventory. A nasal glide after a nasal vowel counts as inside it when the spec emits that glide in a nasal diphthong (mãe `ˈmɐ̃j̃`), so proibição `pɾuibiˈsɐ̃w̃` can be an entry. `build_lexicon.py --excluded` lists each reading and headword that the build leaves out, with the reason.

Three kinds of word are residual words in pt-PT too, because the spelling cannot show the fact: the height of a stressed mid vowel (orthography2ipa#1824), the value of an ⟨x⟩ before a vowel or at the end of a word ([ʃ] xadrez, [ks] táxi, [z] exame, [s] próximo), and ⟨qu gu⟩ with [w] before ⟨e i⟩ (cinquenta). `lexical_class` finds a word that differs from the rules in these only, and that word never joins a lead. The comparison keeps every difference that the board scores.

An unstressed vowel is a residual class too, in four slots where the rules give a default and a word can take another value: an initial ⟨o⟩ or ⟨ho⟩ before a consonant ([ɔ o u]: odrada [o], honesto [u]), an initial ⟨e⟩ or ⟨he⟩ before a consonant ([i e ɛ]: ebó [e]), ⟨a e o⟩ before a coda ⟨l⟩ (golpada [ɔ]), and ⟨a e o⟩ before a coda stop (adactilia [a]). A fifth slot is the vowel where AO90 dropped a silent ⟨c p⟩ (ativo [a] from activo). Cunha & Cintra (p. 53) state that a learned word keeps this vowel unreduced. The build finds the dropped consonant with `--preao`, the aspell `pt_PT-preao` word list: the form with ⟨c⟩ or ⟨p⟩ restored must be in the list and must not be a pt-PT headword of its own (pacto beside pato). In a slot, the entry may take only a value of the vowel letter that the orthography2ipa lattice ranks at that grapheme (`G2P.ipa_lattice`). The Lisbon [ɐ] for an initial ⟨e⟩ is never a value. A word that differs from the rules in any other place is not a residual word. A reading with two primary stresses has no class.

A word under a cited rule stays a lead: a word that a `PT_LEX_CLOSE_*` or `PT_LEX_OPEN_*` rule lists, a written accent, and a rhizotonic present form of a verb of the first or second conjugation with ⟨e⟩ or ⟨o⟩ in the stem. Cunha & Cintra (pp. 429-433) give the stem vowel of such a form by the models levar, lograr, dever and mover and their stated exceptions, and a noun with the same spelling can have the other height (rogo, gosto). `lexicon_build.rhizotonic_verb_form` finds the form when the source holds its infinitive.

A word that the rules get wrong, and that no lead holds out, must pass four more tests before it becomes a pt-PT entry. A residual word must pass the first three tests only, and it is out when no source agrees with it and pt.wiktionary or WikiPron pt-PT gives the rules' reading: one source against one does not settle the word, so the rules keep it. `build_lexicon.py --screened` lists each word with the test it fails, or with the sources that agree with it. The sidecar field `lexical_classes` names each residual entry, its class, and the second sources that agree with it, or `no second source`.

1. The reading is of the same headword. An Infopédia row can transcribe a neighbouring headword or a cut reading. The first syllable must start with a consonant of the same class, and the consonants differ by at most one edit plus one per four consonants. The syllable count is the same, or differs by one where a vowel deletes or a glide forms. The reading ends on the same consonant class and keeps a final coda. This test also drops some correct loanwords, such as *kiwi* and *pipeline*.
2. The word is not a one-letter headword, an interjection spelled as a vowel and ⟨h⟩ (*ah*, *eh*, *oh*), a closed-class word, or a homograph with two readings by sense (*pola*: the archaic contraction [pulɐ] and the noun [ˈpɔlɐ]), because the lexicon cannot choose by context. A word in the bifonia list of heterophonic homographs is out for the same reason. A dictionary reads these as a letter name or a stressed citation form, which would replace the reduced article *o* [u] in every sentence. A closed-class word is one that the spec reads unstressed (`stress.cliticless_words`), or that a row of the dataset tags as a preposition, conjunction, determiner, pronoun or contraction, or a demonstrative or its contraction with ⟨de em a⟩ (Cunha & Cintra p. 343: *esta*, *neste*, *daquele*, *mesmo*).
3. The only difference from the rules is not an open orthography2ipa defect, such as ⟨ã⟩ read [ã] (*afã*, *fã*). Such an entry would hide the defect. `lexicon_build.OPEN_RULE_BUGS` lists each defect by its issue number. A reading that a hand check found wrong is also left out (`lexicon_build.KNOWN_SOURCE_DEFECTS`), and so is a reading with the Lisbon [ɐ] before a palatal or a Lisbon [ɐj] that has no pt-PT [ej].
4. A second source gives the same reading: a hand-typed pt.wiktionary reading for European Portuguese or with no region, or WikiPron pt-PT where it gives the word exactly one reading. A dataset row merged from Infopédia and pt.wiktionary repeats the Infopédia reading, so its agreement is recorded, but it keeps no entry on its own. WikiPron pt comes from the en.wiktionary `{{pt-IPA}}` template, which lists several variants for many words, and a match against one of them is no evidence. The Lisbon reading of the Portal da Língua Portuguesa is generator output: its agreement is recorded, but it keeps no entry on its own. The stress is compared only where both readings mark it, and WikiPron marks none.

## Build, measure and prune

The scripts run the installed orthography2ipa. They score with the board harness of orthography2ipa at the git tag of that version, which they check out once under `.cache/o2i-harness/`. They read gold files from `.cache/gold/`.

```bash
python scripts/build_lexicon.py en-GB wikipron --report build-report.json
python scripts/build_lexicon.py pt-PT infopedia --homographs heterophonic_homographs.csv \
    --preao preao_words.txt --report build-report.json
python scripts/build_lexicon.py pt-BR nilc --nilc unitex_sample_transcribed.txt \
    --michaelis entries.jsonl --homographs heterophonic_homographs.csv \
    --report build-report.json
python scripts/measure.py en-GB ipadict:en-GB cmudict:en
python scripts/measure.py pt-PT ep_dialects:pt-PT wikipron:pt-PT
python scripts/prune_check.py
```

`build_lexicon.py` keeps a word only when the rules get it wrong under the board's scoring. Words that share a spelling pattern and the same error at it form a lead. A lead is a question for the linguistic literature, not a rule. Its words stay out of the lexicon until a cited source states a rule for the pattern, or states that the pattern is lexical. The build report lists each lead.

`measure.py` scores a lexicon on a gold from a different source, with the rules only and with the lexicon. It refuses the gold that supplied the lexicon, and the board dataset that holds that gold. The pt-PT screen keeps the entries outside the residual classes only when a second source corroborates them, WikiPron pt-PT among them, so a pt-PT measure on WikiPron is not independent of the selection. The residual entries that WikiPron does not corroborate are independent of it. `ep_dialects` is a small expert-human set of European Portuguese sentences that no build reads.

`build_lexicon.py` sorts each entry into an exception or a patch with the rules of `entry_kinds.py`, which the next section states.

`prune_check.py` exits with status 1 when the rules alone now get an entry right. A patch that the rules get right is the expected result: its rule landed, and `--write` removes it. An exception that the rules get right means that its class is wrong, because the spelling does give its reading. The check lists it and fails, also with `--write`, and never removes it: a person decides where the word goes. CI runs the check on each pull request, and a weekly job removes the stale patches and opens a draft pull request.

## Exceptions and patches

An entry is an exception when its class is one that the spelling cannot show, by a cited source. An entry with an exception part is an exception, because it stays needed after the rule of its patch part lands. Every other entry is a patch, and its gap is the rule that could reach it. A gap is an orthography2ipa pull request, a spec rule that misfires, a section of `rule-leads.md` in the o2i-lexicons audit of the workspace wiki, or a lead that this file states.

| Code | Exception | Patch |
| :--- | :--- | :--- |
| `pt-PT` | the height of a stressed mid vowel (Cunha & Cintra p. 40; AO90 Base IX 3.º for ⟨ei oi⟩), ⟨x⟩ (AO90 Base III; Ciberdúvidas 4068), ⟨qu gu⟩ with [w] (AO90 Base XIV 1.º; Cunha & Cintra p. 79), an initial ⟨e⟩ in an open syllable of a learned word (Cunha & Cintra p. 53; Mateus & d'Andrade 1998 p. 26 (b)) or before /R/ (Mateus & d'Andrade 1998 p. 26 (c)), an initial ⟨o⟩ as [o] or [ɔ] (Mateus & d'Andrade 1998 p. 27), a loan spelled outside the native system (AO90 Base I 2.º-3.º) | a stressed vowel in an ending that takes one value in at least 90% of the Infopédia words (⟨-oide -dora -eno -ona -oma -ena -edo -ostro -olho -osto -orro⟩), a misfire of a `PT_SUFFIX_*` or prepalatal rule, a learned first element under an initial ⟨e⟩, a vowel before a coda stop or a coda ⟨l⟩, an unreduced learned vowel, and a word with no class |
| `pt-BR` | the height of a stressed mid vowel (Cunha & Cintra p. 40; orthography2ipa#1824), ⟨x⟩ (AO90 Base III), a loan spelled outside the native system | a verb form that the NILC file tags only as a verb: the stem vowel of a rhizotonic form follows the model verbs of Cunha & Cintra pp. 429-433, and the preterite and imperfect forms are a lead; the ⟨s⟩ of trans- before a vowel |
| `en-GB` | a proper noun or an acronym, because no spelling rule gives the reading of a name or of an acronym. The citation names the reading's provenance, Wiktionary via WikiPron, and says that no dictionary checked it | every other entry, because nothing shows that a rule cannot reach it. An inflection in -s -es -ies -ed -ing whose base is a WikiPron headword and no entry has the gap `lead: en-GB inflection morphology`: the rules read the base right, so a morphology rule could read the inflection. Any other entry has the gap `lead: en-GB spelling rules not audited` |

orthography2ipa#2218 keeps an unstressed ⟨e o⟩ full before a coda stop and leaves ⟨a⟩ reduced. So the gap of a vowel before a coda stop is #2218 only where the rules reduce an ⟨e o⟩ that the source keeps full. An ⟨a⟩ that the source keeps as [a], a vowel that the source reduces where #2218 keeps it full, and a close [e o] where #2218 gives [ɛ ɔ] are leads of their own.

The sources: Celso Cunha and Lindley Cintra, *Nova Gramática do Português Contemporâneo*, 7th ed.; Maria Helena Mateus and Ernesto d'Andrade, "The syllable structure in European Portuguese", *D.E.L.T.A.* 14(1), 1998; the Acordo Ortográfico da Língua Portuguesa de 1990 (AO90); Ciberdúvidas da Língua Portuguesa, answer 4068.

## The pt-BR lexicon

The NILC file transcribes the speech of São Paulo city, so the entries could go under `pt-BR` or under `pt-BR-x-sp`. The file's features fit neither spec without a map:

| Feature | NILC file | `pt-BR` | `pt-BR-x-sp` |
| :--- | :--- | :--- | :--- |
| Strong rhotic | [x] | [ʁ] | [x], [ɣ] between voiced sounds |
| Coda rhotic | [x], [ɣ] before a voiced sound | [ɾ] | [ɾ] |
| Final ⟨r⟩ of an infinitive | kept | dropped | dropped |
| Yod before a final /S/ | none | none | a stressed vowel takes it |
| Final vowels | [ɪ ʊ ə] | [i u ɐ] | [i u ɐ] |

The entries go under `pt-BR`. What the rules cannot reach is lexical: the quality of a stressed mid vowel and the value of ⟨x⟩. Those facts are not São Paulo facts, and the `pt-BR-x-sp` yod contradicts the file. A lexicon on `pt-BR` does not reach its child lects.

`lexicon_build.nilc_to_pt_br` writes each reading in the `pt-BR` norm before the comparison with the rules. A word that differs from the rules only in the São Paulo features is rules-right, so it never becomes an entry.

Three kinds of word are residual words, because the spelling cannot show the fact: the height of a stressed mid vowel (orthography2ipa#1824), ⟨x⟩ as [ks] (táxi, fixo), and ⟨qu gu⟩ with [w] before ⟨e i⟩ (frequente). `lexical_class` finds a word that differs from the rules in these only, and that word never joins a lead. A word under a cited rule stays a lead: a word that a `PT_LEX_CLOSE_*` or `PT_LEX_OPEN_*` rule lists, a written accent, and a vowel before a nasal, which `BR_NASAL_STRESSED_*` closes. Every other shared miss is a rule lead for the specs.

A word that the rules get wrong, and that no lead holds out, must pass the tests of `screen_nilc`. It reads the same headword as the rules, and it is not a closed-class word. It is no homograph: a verb form and a noun or adjective with one spelling can differ in the stressed mid vowel, and a word in the bifonia list of heterophonic homographs is out for the same reason. A second independent source must then give the same reading. That source is a hand-typed pt.wiktionary Brazil line, Michaelis, or WikiPron pt-BR where it gives the word one reading. WikiPron pt-BR is the output of the `{{pt-IPA}}` template, so it counts only as it does for pt-PT. The published Aeiouadô lexicon is machine-generated and never counts.

Michaelis prints a broad notation, so it counts only for the stress and the height of the stressed vowel. `same_stress` aligns two readings sound by sound and asks whether their stressed vowels pair, so a post-tonic glide against a hiatus, the epenthetic [i] and a dropped infinitive ⟨r⟩ are no stress difference. Michaelis is editor-made and its method is unstated, and it has defects of its own. Some entries put the stress mark on the wrong vowel (chato [ʃa′tu], ousadia [owz′adiә]), and some print the reading of another word (erótico [eroz′ivu]). So a Michaelis reading never stands alone, and it never supplies an entry.

The build also mines the words that Michaelis and a hand-typed pt.wiktionary Brazil line hold and the NILC file does not. The reading comes from the pt.wiktionary line, and Michaelis corroborates it. So such a line may differ from the rules only in the height of the stressed vowel, and the entry is the rules' reading with that height. The sidecar field `wiktionary_readings` names these words.

The Michaelis readings are "all rights reserved" and stay out of this repository. A Michaelis agreement keeps an entry, and the entry holds a reading of the NILC file or of pt.wiktionary.

## Licence

The code is Apache-2.0. Each data file keeps the licence of its source, which its `.meta.json` sidecar states. The `en-GB` file is CC BY-SA 4.0, the licence of the Wiktionary text it comes from. The `pt-PT` file is CC BY-SA 4.0, the licence that the card of the portuguese-unified dataset states. The `pt-BR` file is CC BY-SA 4.0, because it holds pt.wiktionary readings beside the NILC readings. The NILC readings are BSD 3-Clause, Copyright (c) 2014, Gustavo Mendonça, and `o2i_lexicons/data/pt-BR/LICENSE.nilc` holds that notice.
