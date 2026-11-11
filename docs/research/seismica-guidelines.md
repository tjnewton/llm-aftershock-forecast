# Seismica: rules for authors

What the journal's own pages say, as read when this file was committed. Short quotes are the
pages' words; everything else is paraphrase. "Not found" means the pages read are silent.
Re-read the pages before submission: the style guide says it was last updated January 2025.

Sources (all under https://seismica.library.mcgill.ca/): `/about/submissions`,
`/author-guidelines`, `/policies`, `/submission-checklist`, `/templates`, `/reviewer-guidelines`,
`/style-guide`; the template repository https://github.com/WeAreSeismica/templates and its
Overleaf mirror https://www.overleaf.com/latex/templates/seismica/bvnbjbkycdjb. Not read:
`/editor-guidelines`, `/code-of-conduct`, `/faq`. On `/policies`, the Ethical Guidelines were
read in full; the Editor and Reviewer sections further down only as a summary.

## What this means for our paper
- **Length:** "no more than 10,000 words and 10 display items (i.e., figures, tables) in the
  main text." The registered analysis has far more than 10 tables (section 6 of
  docs/preregistration-v2.md), so the main text carries the primary test, test B and a few
  figures; the sensitivity, secondary and descriptive tables go in a supplement.
- **Article type:** Research Article by default. A null-results Report exists and has its own
  required sections (below); which one fits is known only after the registered analysis. The
  site says nothing about pre-registration, registered reports, benchmarks or prospective
  tests, so the frozen protocol and its hash are ours to explain in Methods.
- **Framing:** the reviewer guidelines give "accurately predicting future earthquakes in space
  and time" as an example of unsubstantiated pseudoscience, and list "A clear hypothesis or
  motivation for the study hasn't been established" as grounds for rejection. The paper says
  probabilistic aftershock forecasts throughout, never prediction, and states hypothesis A in
  the introduction.
- **AI disclosure:** the pipeline's code was written with an LLM assistant, which the policy
  counts as a contribution to scientific content; the disclosure belongs in Methods, not only
  in the acknowledgments. Its wording is the author's to approve.
- **Archive:** GitHub alone is not accepted. A Zenodo snapshot with a DOI is cited beside the
  repository URL (already planned: prereg section 9).
- **Reviews are published** with the paper (transparent peer review).
- **Scope:** "statistical seismology" is listed; forecast evaluation is not named. The site
  invites a question to info@seismica.org when unsure.

## Article types
- All types: at most 10,000 words and 10 display items in the main text. Longer needs the
  Executive Editor for Production's agreement first.
- Research Article: "typically from 3,000 to 10,000 words in length (excluding references and
  figure captions) and up to 10 figures."
- Fast Report: time-sensitive, about 3,000 words and 2-3 display items, supplement under 1,000
  words and 10 display items, accelerated review that must be justified.
- Reports (null results, software, data): the same limits. Null results are considered "where
  they are illuminating or instructive in the context of previous published studies"; required
  sections are background, methods, null results, discussion against previous work and a
  take-home message.
- Opinions and reviews are invited; commentaries about 3,000 words and 3 figures, after
  contacting the board.

## Required parts of the manuscript
- Abstract in English, "maximum 200 words, no references included."
- Author contributions in CRediT roles only.
- Data and Code Availability Statement. "please contact the authors for data access" is not
  acceptable for data that can be distributed.
- References, with DOIs where they exist; nothing uncited.
- Competing Interests statement (state that there are none if so); funding is disclosed there.
- ORCID of the corresponding author, in the text at first submission.
- Encouraged, not required: a non-technical summary of about 200 words; up to two
  second-language abstracts of at most 200 words each.
- In the "Comments to the Editor" box: the main-text word count (without abstract, captions and
  references), suggested reviewers, and any preprint's DOI and license.

## Format
- First submission: PDF, with line numbers, double spacing, 12 pt or larger, figures inside the
  text. No template is required at submission; the Seismica template is "strongly"
  encouraged.
- At acceptance the paper must be in a Seismica template: LaTeX (pdflatex; `submission_latex`
  in the templates repository, mirrored on Overleaf), docx or odt (slower in production).
- LaTeX: do not modify the class file, add packages or keep custom macros. Class options:
  anonymous, breakmath, languages, preprint, report, supplement. `\citep` and `\citet` only.
  At most three levels of headings. Label equations; vectors and matrices in bold.
- Figures: 86 mm or 180 mm wide, at most 200 mm high, at least 300 dpi, multi-panel figures in
  one file, perceptually uniform colormaps that are safe for color-vision deficiency. Separate
  full-resolution files at acceptance (png; the author guidelines also allow pdf).
- Tables: simple ones in the text; complex ones are better in the supplement.
- Supplement: PDF uploaded with the submission, not copyedited or typeset. Data tables and
  other files go to a repository (the Seismica community on Zenodo is recommended).

## References
- LaTeX submissions use the template's BibTeX style; others use APA 7th edition. Full author
  lists (no AGU-style truncation), consistent journal abbreviations.
- Work "submitted" or "in review" may be cited only as a preprint with a DOI. No personal
  communications.

## Style guide
Checked by the copyeditors:
- Define every acronym at first use.
- Hyphen in compounds, en dash for number ranges.
- Capitalize "Figure", "Table" and "Section" in the text, not "equation". "Figure" or "Fig.",
  one or the other throughout. Panels are lower-case letters: "Figure 1a". Supplementary items
  are "Supplemental Figure S4a", "Supplemental Section S1".
- Magnitudes: "When magnitude refers to any kind of magnitude type, write as M<5, M≥7. Do not
  use spaces." Moment magnitude is Mw (LaTeX `$\rm{M\_w}$`).

Best practice, not checked:
- *p*-value, *t*-test (italic letter, hyphen, lower case).
- Non-breaking space between number and unit.
- Dates "25 January 2022" or "25/01/2022"; 24-hour times, UTC unless stated.
- SI units. Do not abbreviate latitude or longitude.
- British or American spelling, consistent throughout (author guidelines).
- Not found: any rule on "forecast" against "prediction", or on naming earthquakes.

## Preprints, license, fees
- Preprints are welcome on any server; disclose the DOI and license at submission and link the
  published DOI afterwards. CC-BY recommended for the preprint.
- Published under CC-BY 4.0; authors keep copyright. No fees to publish or read.

## Data and code
- Repositories must give a DOI and long-term archiving (Zenodo, Figshare, Dryad and others).
  "Personal websites and code repositories like GitHub do not meet the standards for long-term,
  DOI citable archiving": archive a static copy and cite it with the version used.
- Code: "the minimum requirement... is that they can be executed to reproduce the results
  presented in the manuscript", with documentation and a license.
- A readme explains file formats; open formats recommended.
- For review, the archive may be public or shared by a private link. An embargo is allowed if
  the statement gives its end date.
- For seismic network data, cite the FDSN network code and its citation.

## AI tools and authorship
The policy (Ethical Guidelines, under "Originality"), sentence by sentence:
1. AI tools, LLMs and LLM agents included, can make valid contributions to research and
   writing, and their use to improve submissions is permitted.
2. Responsibility for the content "lies solely with the authors"; AI tools "cannot be granted
   co-authorship status."
3. "We ask the authors to always verify any results coming out of any interactions with AI."
4. AI use "should be explicitly mentioned in the manuscript."
5. If AI "significantly contributed to the scientific content (e.g., writing code, symbolic
   mathematics, etc.)", the mention goes in the Methods section. "Significantly" is not
   defined.
6. For writing help alone a statement in the acknowledgments is enough; suggested wording: "We
   used [AI tool name + version] to assist in drafting the manuscript."

It bans no particular use and does not mention AI-made figures or data. Reviewers "may not
paste text from submitted manuscripts into ChatGPT or similar AI language models."
Authorship needs a considerable contribution (creating software used in the study counts) and
approval of the submitted version by every author.

## Peer review
- Transparent: on acceptance the decisions, the reviewers' comments and the authors' replies
  are published. Reviewers are anonymous unless they sign. Double-anonymous review on request;
  the LaTeX `anonymous` option still prints the data availability section.
- Desk rejection: out of scope, not original, of insufficient interest, poor language, or data
  rules not met.
- What reviewers are asked (their guidelines): "Are the methods appropriate and described in
  sufficient detail to be transparent and reproducible?"; "Are the conclusions adequate and
  supported by the data?"; "Is the paper unnecessarily long?"; "If the study disagrees
  significantly with the current academic consensus, is there a substantial case?" Grounds for
  revision include "Lack of error analysis, flawed error analysis, or lack of information
  about assumptions."
- Times: reviews due in 4 weeks, a first decision aimed for within 8 weeks, a revision due
  within 6 months, with a response letter, a tracked-changes version and a clean version.

## Not found on the pages read
Pre-registration, registered reports, benchmark or prospective-test papers; a word or display
limit for supplements (other than Fast Reports); which reference style the template's `.bst`
produces.
