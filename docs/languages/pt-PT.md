# pt-PT

The `pt-PT` lexicon serves the o2i `pt-PT` spec. Its file is `infopedia.tsv` in both kind directories.

## Source

The readings come from the [portuguese-unified-pronunciation-lexicon](https://huggingface.co/datasets/TigreGotico/portuguese-unified-pronunciation-lexicon) dataset. The build reads only its Infopédia rows: the rows whose source is Infopédia, the Porto Editora dictionary, alone or shared with Wiktionary. The tier is `lexicon-derived`. The license is CC BY-SA 4.0, the license that the dataset card states.

## From the Infopédia notation to the pt-PT norm

Infopédia transcribes European Portuguese with features of Lisbon speech. It writes ⟨ei⟩ as [ɐj] (leite `ˈlɐjt(ə)`) and a stressed ⟨e⟩ before a palatal as [ɐ]. The o2i `pt-PT` spec does not have these features (leite `ˈlejtɨ`), and the `pt-PT-x-lisbon` spec has them. So the build puts each Infopédia reading in the `pt-PT` norm before it compares the reading with the rules.

Infopédia writes three sounds with other symbols than the spec, and the build writes the spec's symbols (`lexicon_build.INFOPEDIA_NOTATION`):

| Infopédia | Spec | Sound |
| :--- | :--- | :--- |
| `ə` | `ɨ` | the reduced vowel |
| `r` | `ɾ` | the tap |
| `ʀ` | `ʁ` | the strong rhotic |

A reading that writes `r` where the spelling has the strong rhotic is left out, because there `r` is not the tap. The strong rhotic positions are an initial ⟨r⟩, ⟨rr⟩, and ⟨r⟩ after ⟨n l s⟩. Infopédia writes an optional vowel as `(ə)`, and the entry takes the full form.

The build handles the Lisbon features as follows:

| Feature | Infopédia | `pt-PT` spec | Build |
| :--- | :--- | :--- | :--- |
| ⟨ei⟩, ⟨e⟩ before ⟨x⟩, English [eɪ] | [ɐj] | [ej] | writes [ej] where the rules read the vowel as ⟨e⟩ or ⟨a⟩, and leaves any other [ɐj] out (`lexicon_build.lisbon_to_pt_pt`) |
| stressed ⟨e⟩ before a palatal | [ɐ] | [e] or [ɛ], by word | leaves the word out, because the vowel cannot be recovered |
| nasal diphthong | `ɐj̃`, `ɐw̃`, nasal on the glide only | [ɐ̃j̃], [ɐ̃w̃] | writes the nucleus nasal too |

## The stress mark

Each entry carries the stress of Infopédia (`"stress": "source"`). The primary stress mark stands before the onset of the stressed syllable (`lexicon_build.onset_stress`). The onset is one consonant, or one of the obstruent + liquid clusters that Cunha & Cintra list as inseparable (*Nova Gramática do Português Contemporâneo*, 7th ed., p. 64).

Mateus & d'Andrade ("The syllable structure in European Portuguese", *D.E.L.T.A.* 14(1), 1998, pp. 15-18) put an empty nucleus between the consonants of a cluster such as [ɡn pt ks tm]. So a consonant before the onset opens a syllable of its own, with an empty nucleus, and the mark goes after that consonant. Infopédia often puts the mark before the whole cluster, and the build moves it:

| Word | Infopédia | Entry |
| :--- | :--- | :--- |
| agnelo | `ɐˈɡnelu` | `ɐɡˈnelu` |
| afixar | `ɐfiˈksar` | `ɐfikˈsaɾ` |
| epiblasto | `ɛpiˈblaʃtu` | `ɛpiˈblaʃtu` (the cluster [bl] is an onset) |

A cluster at the start of a word stays whole (gnomo `ˈɡnomu`). The mark never moves across a prefix seam that `silabificador.morphology` lists. The build moves only the mark: each entry keeps its sounds and its stressed vowel.

## How the build selects an entry

A word that differs from the rules only in a fact that the spelling cannot show is a residual word. These facts count (`lexicon_build.lexical_class` and `lexicon_build.vowel_slots`):

- the height of a stressed mid vowel
- the value of ⟨x⟩ before a vowel or at the end of a word ([ʃ] xadrez, [ks] táxi, [z] exame, [s] próximo)
- ⟨qu gu⟩ with [w] before ⟨e i⟩ (cinquenta)
- an unstressed vowel in a slot where the rules give a default and a word can take another value: an initial ⟨o ho e he⟩ before a consonant, ⟨a e o⟩ before a coda ⟨l⟩ or a coda stop, and a vowel where AO90 dropped a silent ⟨c p⟩ (ativo from activo)

In a vowel slot, the entry may take only a value that the o2i lattice ranks at that letter. A residual word never joins a lead. A residual word with a stressed mid vowel stays a lead when a cited o2i rule decides its height. That is the case for a word that a `PT_LEX_CLOSE_*` or `PT_LEX_OPEN_*` rule lists, a written accent, and a rhizotonic present form of a first or second conjugation verb.

A word that the rules get wrong and that no lead holds must pass the tests of `screen_infopedia` in `scripts/build_lexicon.py`. A residual word must pass tests 1 to 3 only.

1. The reading is of the same headword. An Infopédia row can transcribe a neighbouring headword or a cut reading.
2. The word is not a one-letter headword, an interjection, a closed-class word, or a homograph with two readings by sense. A word in the [bifonia](https://github.com/TigreGotico/bifonia) list of heterophonic homographs is out for the same reason.
3. The only difference from the rules is not an open o2i defect (`lexicon_build.OPEN_RULE_BUGS`), and a hand check did not find the reading wrong (`lexicon_build.KNOWN_SOURCE_DEFECTS`).
4. A second source gives the same reading: a hand-typed pt.wiktionary reading for European Portuguese or with no region, or WikiPron pt-PT where it gives the word one reading.

A residual word is out when no second source agrees with it and pt.wiktionary or WikiPron pt-PT gives the rules' reading. Here too, WikiPron counts only for a word that it gives one reading. A row that Infopédia and pt.wiktionary share repeats the Infopédia reading, so it keeps no entry on its own. Neither does the Lisbon reading of the [Portal da Língua Portuguesa](https://www.portaldalinguaportuguesa.org/), which is generator output. The sidecar field `lexical_classes` names the class of each residual entry and the second sources that agree with it.

## Kinds

| Kind | Classes |
| :--- | :--- |
| Exception | the height of a stressed mid vowel, the value of an ⟨x⟩ before a vowel (also beside other differences), ⟨qu gu⟩ with [w], an unstressed initial ⟨e⟩ or ⟨o⟩ in the classes that `entry_kinds.py` names, and kilowatt, a unit that AO90 Base I 2.º c) names |
| Patch | a stressed vowel in an ending that `entry_kinds.DOMINANT_ENDINGS` lists, a misfire of a `PT_SUFFIX_*` or prepalatal rule, a learned first element under an initial ⟨e⟩, an initial ⟨e⟩ with the value that Mateus & d'Andrade 1998 p. 26 give ([i] with no coda, [ɛ] before a coda /L/, deleted before a coda /S/), a vowel before a coda stop or a coda ⟨l⟩, an unreduced learned vowel, the ⟨m⟩ of ⟨mn⟩ that AO90 Base IV 2.º keeps where it is pronounced, a loan spelled outside the native system, and a word with no class |

An ending is in `DOMINANT_ENDINGS` when its stressed vowel takes one value in at least 90% of at least 25 single-word Infopédia rows. The spelling then shows the value, so a rule could take it. The sidecars give the exact citation or gap of each word.

## Known limits

Some exception citations support the class more weakly than the contract asks. Cunha & Cintra p. 40 show that the height of a stressed mid vowel is distinctive. They do not state that no ending predicts it. For an unstressed initial vowel, the cited pages state the class or a variation, and the reading of the word comes from Infopédia.

No source states that the reading of a loan is lexical, so a loan is a patch. A loan that differs from the rules only in a doubled consonant letter or an initial ⟨s⟩ before a consonant has the lead of that spelling. Every other loan has the gap `lead: pt-PT English loan spelling`, with ⟨tch⟩, ⟨zz⟩ or a final ⟨-ing⟩ when the word has one, and Infopédia gives its reading. That gap names the spelling of the loan, not the error of the rules. [AO90](https://www.portaldalinguaportuguesa.org/acordo.php?action=acordo&version=1990) Base I 2.º c) names kW-kilowatt among the units of measure that keep ⟨k w y⟩, so kilowatt is an exception. The Base gives the spelling and Infopédia gives the reading.

A patch with no class has the gap `no lead: the rules miss the word outside every class and lead`, which names no rule. The [rule leads](../leads.md) page gives the evidence for each lead that a gap names.

A lexicon on `pt-PT` does not reach a child lect such as `pt-PT-x-lisbon`.

---
[← pt-BR](pt-BR.md) · [Home](../index.md) · [Building and pruning →](../building.md)
