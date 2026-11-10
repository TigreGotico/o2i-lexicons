# Rule leads

A lead is a spelling pattern that a group of words shares, together with one error of the o2i rules at that pattern. A lead is a candidate for an o2i rule. When a rule with a cited source lands, `prune_check.py` finds the patches that the rules now read right, and they leave the package ([kinds](kinds.md)).

A patch states its lead in its gap. A long lead has a section on this page, and the gap names it as `docs/leads.md § <section>`. A short lead is written into the gap itself. The last part of this page lists the leads that no entry carries yet, because each one waits for a source or for a change in the build.

The Infopédia counts on this page come from the pt-PT Infopédia rows of the portuguese_unified lexicon, the source of the pt-PT files: 93,979 single words, first reading only. The rules readings come from orthography2ipa 7.122.23a2 with an empty lexicon. The entry counts are the entries of the files in this package.

## pt-PT sections that gaps name

### word-initial e

The word starts with a learned first element under an unstressed ⟨e⟩ in an open syllable: eco-, epi-, equi-, eritr-, etil-, etol-, ego-, endo- or ecto- (`entry_kinds.LEARNED_E`). The rules give [i], the value that Mateus & d'Andrade (1998, p. 26 (b)) give a word-initial /e ɛ/ with no coda. Cunha & Cintra (p. 53) state that the unstressed vowels of learned words (cultismos) do not reduce.

| Initial vowel in the entry | Entries | Examples |
| :--- | ---: | :--- |
| [e] | 95 | epibolia, epicanto, epiciclo, epicureu |
| [ɛ] | 27 | ecologia, ecológico, epiblasto, epicamente |

The 122 entries need a rule that knows the learned elements and the value of each one.

### coda l

orthography2ipa#2213 gives an unstressed ⟨a e o⟩ before a ⟨l⟩ that closes the syllable a full vowel: [a], [ɛ], [o]. Its source is Cunha & Cintra (p. 53). In 42 entries, Infopédia gives another full vowel in that slot.

| Rules | Entry | Entries | Examples |
| :--- | :--- | ---: | :--- |
| [o] | [ɔ] | 26 | acolpado, colportagem, folclore, golpada |
| [o] | [u] | 10 | boldreguice, polvorosa, solfatara, toldeia |
| [ɛ] | [e] | 5 | carregável, felpado, felpar |
| [a] | [ɐ] | 1 | albuminólise |

The words in golp- keep the stressed [ɔ] of golpe, and the words in folclor- come from the English loan folklore. These families are leads for a derivation rule.

### learned words

An unstressed vowel of a learned word does not reduce. Cunha & Cintra (p. 53) write: "Também não se reduziram as vogais átonas de cultismos, como o [a] de *actor*; o [ɛ] de *director*; o [ɔ] de *adopção*". Before AO90, a silent ⟨c⟩ or ⟨p⟩ marked the full vowel. AO90 drops that consonant, and pt-PT reads AO90 spelling, so the spelling has no cue left. Each word of this lead is the AO90 form of a word that the aspell pt_PT-preao list spells with ⟨a e o⟩, then a silent ⟨c p⟩, then ⟨c ç t⟩.

| Rules | Entry | Slots | Examples |
| :--- | :--- | ---: | :--- |
| [ɨ] | [ɛ] | 161 | adjetivo, arquitetar, abjeção |
| [ɐ] | [a] | 66 | ativo, ator, abstração |
| [u] | [ɔ] | 6 | adotar, adoção, noturno |

The 233 entries need a rule that has the pre-AO90 form of the word.

### Entries in ⟨-oide⟩

Infopédia gives the open diphthong [ɔj] in 198 of the 198 words in a stressed ⟨-oide⟩. orthography2ipa#2250 reads this ending, so the files hold no entry with this gap.

### Entries in ⟨-dora⟩

Infopédia gives the close [o] in 66 of the 71 words in a stressed ⟨-dora⟩. orthography2ipa#2251 reads this ending and ⟨-tora -sora⟩, so the files hold no entry with this gap.

## pt-PT leads that a gap states

### Stressed endings

An ending is a lead when its stressed vowel takes one value in at least 90% of at least 25 single-word Infopédia rows (`entry_kinds.DOMINANT_ENDINGS`). The counts below are the paroxytone words of each ending, where the stress falls on the vowel of the ending.

| Ending | Value | Infopédia | Entries |
| :--- | :--- | ---: | ---: |
| ⟨-orro⟩ | [o] | 29 of 29 | 13 |
| ⟨-osto⟩ | [o] | 33 of 33 | 16 |
| ⟨-ostro⟩ | [o] | 28 of 28 | 23 |
| ⟨-olho⟩ | [o] | 42 of 46 | 21 |
| ⟨-oma⟩ | [o] | 134 of 135 | 56 |
| ⟨-ona⟩ | [o] | 125 of 130 | 88 |
| ⟨-ena⟩ | [e] | 88 of 90 | 56 |
| ⟨-eno⟩ | [e] | 154 of 160 | 97 |
| ⟨-edo⟩ | [e] | 64 of 68 | 54 |
| ⟨-queta⟩ | [e] | 27 of 29 | 24 |
| ⟨-eso⟩ | [e] | 26 of 28 | 11 |
| ⟨-eca⟩ | [ɛ] | 110 of 110 | 1 |
| ⟨-ose⟩ | [ɔ] | 286 of 297 | 1 |

### Other gaps

| Gap | Entries | Evidence |
| :--- | ---: | :--- |
| an unstressed ⟨a⟩ before a coda stop keeps [a] | 74 | orthography2ipa#2218 opens ⟨e o⟩ before a stop and a consonant (Cunha & Cintra pp. 53 and 88) and leaves ⟨a⟩ out |
| the source reduces a vowel before a coda stop that orthography2ipa#2218 keeps full | 18 | Infopédia gives [ɨ] or [u] where the rule gives [ɛ] or [ɔ] |
| the source has a close mid vowel before a coda stop | 2 | Infopédia gives [e] or [o] where the rule gives [ɛ] or [ɔ] |
| the stems honest- and honor- take an initial [u] | 11 | Infopédia gives an initial [u] in 11 of the 12 words of the two stems |
| Mateus & d'Andrade 1998 p. 26 (b): [i] with no coda | 2 | ebrié and ebriés, where Infopédia gives the [i] of the page |
| the ⟨m⟩ of ⟨mn⟩ | 3 | AO90 Base IV 2.º: "Conservam-se ou eliminam-se, facultativamente, quando se proferem numa pronúncia culta [...] o m da sequência mn, em amnistia, amnistiar, indemne, indemnidade, indemnizar". The entries indemnidade, indemnizar and indemnização pronounce the [m], and the rules drop it |
| a doubled consonant letter | 2 | lobby and zapping. Each Infopédia word with ⟨bb dd ff gg kk ll mm nn pp tt zz⟩ has one consonant there |
| an initial ⟨s⟩ before a consonant | 2 | snobismo and swing. The initial ⟨s⟩ is [s] in 65 of the 67 Infopédia words. The two others are schnitzel and schumpeteriano |
| an English loan spelling | 10 | antidumping, freelance, jogging, ketchup, puzzle, rap, shorts, skinhead, timing, windsurf. The gap names ⟨tch⟩, ⟨zz⟩ or a final ⟨-ing⟩ when the word has one, and Infopédia gives the reading |

Two gaps name no lead. `PT_STRESSED_E_PREPALATAL_CLOSE misfires` (13 entries) marks a stressed ⟨e⟩ before ⟨lh nh j ch⟩ where orthography2ipa#2215 gives [e] and Infopédia gives [ɛ]. `no lead: the rules miss the word outside every class and lead` (23 entries) marks a word with no pattern.

## pt-PT leads that no entry carries

### ⟨-oio⟩

The 18 Infopédia words in a stressed ⟨-oio⟩ split: [oj] in 10 (apoio, arroio, joio, poio) and [ɔj] in 8 (comboio, foio, loio, paloio). The spelling does not show the value. The 1945 Acordo, Base XVI, drops the acute of comboio "por idêntica falta de pronúncia uniforme". The rules give [oj] in all 18 words.

comboio is [ɔj] in Infopédia [kõˈbɔju], WikiPron pt-PT and the Portal da Língua Portuguesa Lisbon reading. The files hold it as an exception with the stressed-mid-vowel class. A word list in o2i can take it.

### ⟨-mente⟩ and ⟨-idade⟩ after an open ⟨oi⟩

Infopédia gives [ɔj] in all 5 of its words in ⟨-oicamente⟩ and ⟨-oicidade⟩: estoicamente, estoicidade, heroicamente, heroicidade and monozoicidade. The Portal Lisbon reading agrees. The 1945 Acordo, Base XXIII, writes the open vowel of such derivatives with a grave accent: heròicamente, bòiazinha, jòiazinha, heròizinho. The rules give [oj] in all 5, because orthography2ipa#2265 opens a stressed ⟨oi⟩ only, and the engine marks no secondary stress in these words. Other derivatives keep [oj] in Infopédia: estoicismo, boicote, moicano. A rule must key on ⟨-mente⟩ and ⟨-idade⟩, not on every derivative.

### ⟨-iedade⟩

Infopédia has 39 words in ⟨-iedade⟩.

| First reading | Words | Examples |
| :--- | ---: | :--- |
| [jɛ] | 33 | ansiedade, notoriedade, piedade, seriedade |
| [jɐ] | 3 | espuriedade, saciedade, sociedade |
| [jə] | 2 | acessoriedade, compulsoriedade |
| [iɛ] | 1 | propriedade |

The rules give [iɨ] in all 39. At 85% the share is below the 90% of a stressed-ending lead, and no source read states the value. The files hold saciedade and sociedade as no-lead patches with [jɐ], and a [jɛ] rule would give the second Infopédia reading of sociedade.

A search for a source that states this vowel, or its cause, found none. Cunha & Cintra (*Nova Gramática do Português Contemporâneo*, p. 53) list the unstressed vowels that European Portuguese does not reduce. These are a vowel from the crasis of two identical vowels (padeiro), a vowel from an old diphthong (dourar), the vowels of learned words (actor, director, adopção), a word-initial ⟨o⟩ or ⟨e⟩, a vowel before a coda ⟨l⟩, and the stressed vowel of a simple word in its derivatives, mostly in ⟨-mente⟩ and ⟨-inho⟩. The ⟨e⟩ of ⟨-iedade⟩ is not the stressed vowel of its base (sócio, vário, pio). The learned-word clause gives no example in ⟨-iedade⟩, and other learned words in ⟨-idade⟩ reduce their pretonic ⟨e⟩: Infopédia gives celebridade [sələbriˈdad(ə)], serenidade [sərəniˈdad(ə)] and sinceridade [sĩsəriˈdad(ə)]. The abstract of Mateus & d'Andrade (D.E.L.T.A. 14(1), 1998, pp. 13-32) names onset clusters, epenthetic vowels and word-initial vowels; the full text was not read. Mateus & d'Andrade, *The Phonology of Portuguese* (2000), Barbosa, *Introdução ao Estudo da Fonologia e Morfologia do Português* (1994), and Vigário, *The Prosodic Word in European Portuguese* (2003), had no copy that could be read. This lead waits for one of these books.

### Nouns with a verb-form homograph

breja, brejo, estro, obra and relho have an open stressed vowel in Infopédia (ˈbrɛʒɐ, ˈɔbrɐ), and the rules give a close one. Each word is also a rhizotonic form of a verb (breger, estrar, obrar, relhar), and Cunha & Cintra (pp. 429-433) decide the stem vowel of such a verb form. So the build keeps each word a lead with no class, and the files hold the five words as no-lead patches. The verb rule gives the vowel of the verb form. It may not decide the vowel of the noun, so the build needs a part-of-speech test before it applies that rule.

### sequoia

Infopédia gives sequoia [səˈkɔjɐ], with ⟨qu⟩ as [k]. The rules give [sɨˈkwɔjɐ]. orthography2ipa#2265 reaches the [ɔj], so ⟨qu⟩ is the only difference. The files hold sequoia as a no-lead patch.

### Stress

These five words differ from Infopédia in stress only. The build compares the rules with a source reading without stress (`build_lexicon.py`), so it finds the rules right and keeps no entry for them. A comparison with stress would admit them on the agreement of WikiPron. WikiPron writes no stress, so that agreement does not test the stress.

| Word | Rules | Infopédia |
| :--- | :--- | :--- |
| angus | ɐ̃ˈɡuʃ | ˈɐ̃ɡuʃ |
| bantu | bɐ̃ˈtu | ˈbɐ̃tu |
| campus | kɐ̃ˈpuʃ | ˈkɐ̃puʃ |
| pãozinho | ˈpɐ̃w̃ziɲu | pɐ̃w̃ˈziɲu |
| wiki | wiˈki | ˈwiki |

Each one waits for a second source that marks stress.

## pt-BR and en-GB gaps

| Code | Gap | Entries |
| :--- | :--- | ---: |
| pt-BR | the stem vowel of a pt-BR preterite or imperfect form | 7 |
| pt-BR | the ⟨s⟩ of the prefix trans- before a vowel is [z] | 1 |
| pt-BR | an English loan spelling (sexy) | 1 |
| en-GB | en-GB spelling rules not audited | 2,151 |
| en-GB | en-GB inflection morphology | 188 |

The [pt-BR](languages/pt-BR.md) and [en-GB](languages/en-GB.md) pages give the detail.
