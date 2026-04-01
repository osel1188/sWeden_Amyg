=== CHALLENGE: Sex-Based Voltage Analysis ===
Source: free-text concept

## Your Position

- Split ~70 neurostimulation sessions by participant sex (male/female) from an Excel file
- Analysis 1: Compute mean, median, STD of interval voltages per participant, compare between sexes
- Analysis 2: Count distinct voltage changes per interval using a 2-minute sliding window to collapse rapid successive operator adjustments into single "search events"
- Additionally: explore creative analyses (stability, asymmetry, time-to-stable, etc.)
- The implicit assumption is that sex is a meaningful grouping variable for voltage-level operator behavior and stimulation characteristics

## Opposition

### 1. The problem may be misdiagnosed

The voltage values set during stimulation are **operator-chosen**, not participant-driven. The operator adjusts voltages based on participant feedback (comfort, sensation thresholds), equipment readings, and protocol targets. Any sex difference in voltage therefore reflects an interaction between the operator's decision-making and the participant's response --- it is not a clean biological signal.

Recent TI research makes this explicit: a 2025 study in *Brain Stimulation* found that anatomical variability (skull thickness, CSF-to-head ratio) mediates >40% of inter-individual variability in stimulation outcomes, and that "sex differences in TIS outcomes appear to be substantially mediated by anatomical variations rather than being direct sex effects" ([ScienceDirect](https://www.sciencedirect.com/science/article/pii/S1935861X25002748)). If you find that males receive higher voltages, is that because of sex per se, or because males tend to have thicker skulls requiring higher voltages to achieve equivalent field strength? Without anatomical covariates, the analysis cannot distinguish these explanations.

Furthermore, if multiple operators conducted sessions across the ~70 participants, operator identity is a confound. One operator may consistently set higher voltages or search longer. If operator assignment correlates even weakly with participant sex (e.g., scheduling patterns), apparent sex differences may actually be operator differences.

### 2. Critical assumptions that may not hold

**Assumption 1: The 2-minute sliding window correctly delineates "search events."**

The 2-minute window is an arbitrary heuristic with no empirical justification from the data. Research on sliding window methods consistently shows that window parameters are the dominant factor in detection performance --- more influential than noise or signal characteristics ([PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC4889509/)). If the operator pauses for 2 minutes and 10 seconds mid-search (perhaps to ask the participant a question), the algorithm splits one logical search into two events. If they complete two genuinely independent adjustments 1 minute 50 seconds apart, those collapse into one. The signal processing literature advocates for adaptive thresholds over fixed windows for exactly this reason ([ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0306261924002332)).

Without a sensitivity analysis (e.g., testing windows of 1, 2, 3, 5 minutes and showing results are robust), any findings from this metric are fragile.

**Assumption 2: ~70 sessions split by sex provides adequate statistical power.**

With ~70 sessions split roughly 40/30 between sexes (based on ~40 female, ~36 male participants in the Excel), each subgroup has ~30-35 sessions. The *Journal of Neuroscience* has documented that median statistical power in neuroscience studies ranges between 8% and 31% ([J Neurosci](https://www.jneurosci.org/content/40/21/4076)). A *Biology of Sex Differences* review warns that "most studies are underpowered to examine associations separately for males and females" and that "small sample size with reduced statistical power has been identified as a central problem" specifically in sex-difference research ([PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC9327177/)).

With 4 channels x 2 blocks x multiple metrics (voltage, changes, stability, asymmetry, time-to-stable), you are running dozens of statistical tests. Even with FDR correction, the effective power per test is very low. You risk either (a) finding nothing and incorrectly concluding no sex differences exist, or (b) finding spurious significant results that won't replicate.

**Assumption 3: Condition (active vs sham) does not interact with sex.**

Active and sham protocols use different frequency configurations (beat frequency vs no beat). If condition assignment is not perfectly balanced by sex (which randomization does not guarantee at n=70), any apparent sex difference could be a condition effect in disguise. The plan mentions condition as a potential grouping factor but treats it as secondary. Given that condition directly affects the stimulation protocol and potentially the operator's approach to voltage adjustment, it should be a primary stratification variable, not an afterthought.

### 3. Stronger alternatives exist

**Alternative 1: Within-participant paired analysis instead of between-group comparison.**

If any participants have multiple sessions, a within-participant design (comparing Block 1 vs Block 2, or session 1 vs session 2) eliminates all between-subject confounds including sex, anatomy, and operator assignment. This is statistically far more powerful per data point. Even with a single session per participant, comparing Block 1 to Block 2 within-subject and then examining whether the *change pattern* differs by sex is more informative than raw group means.

**Alternative 2: Mixed-effects modeling instead of Mann-Whitney U.**

Rather than running many separate Mann-Whitney tests (one per channel, per block, per metric), a linear mixed-effects model with participant as a random effect and sex, condition, block, and channel as fixed effects can answer all questions simultaneously with proper correction for the nested data structure. This approach: (a) handles the repeated measures (multiple channels, multiple blocks per participant), (b) naturally controls for condition, (c) provides interaction terms (sex x condition, sex x block) that the planned univariate tests cannot, and (d) makes far more efficient use of the limited sample size.

**Alternative 3: Bayesian estimation instead of null-hypothesis testing.**

With n~35 per group, null-hypothesis significance testing will frequently return "not significant" results that are uninformative (failing to reject H0 is not evidence for H0). Bayesian estimation (e.g., posterior distributions of group differences with credible intervals) would show the *magnitude* and *uncertainty* of any sex difference, which is more useful for an exploratory analysis. A Bayes factor could explicitly quantify evidence for vs against a sex effect.

### 4. What this position ignores

**Multiple comparisons burden.** The plan proposes: 4 channels x 2 blocks x ~6 metrics (mean voltage, median voltage, STD voltage, change count, stability, time-to-stable) x 2 groupings (overall + stratified by condition) = ~96 statistical tests. Without rigorous correction, this is a false-discovery minefield. The *PLOS Biology* critique of sex-difference research specifically warns against "unjustified emphasis on marginally significant findings or findings that did not survive correction for multiple comparisons" ([PLOS Biology](https://journals.plos.org/plosbiology/article?id=10.1371/journal.pbio.3001253)).

**Temporal confounds.** If the study enrolled participants over months, early sessions may differ systematically from late sessions (operator experience improves, equipment calibration drifts, protocol refinements). If enrollment was not sex-balanced over time, temporal confounds masquerade as sex effects.

**The "creative analyses" risk scope creep without hypothesis.** Adding asymmetry, stability, time-to-stable, and condition interactions is exploratory. Exploratory analyses are valuable, but presenting many exploratory metrics alongside confirmatory statistics (p-values, effect sizes) without clearly labeling them as exploratory encourages cherry-picking the one metric that happens to show p<0.05.

**Channel non-independence.** A1 and A2 come from the same waveform generator; B1 and B2 from the other. Treating all 4 channels as independent observations inflates the effective sample size. The plan's channel-pair asymmetry analysis acknowledges this pairing but the primary descriptive statistics treat channels independently.

### 5. The strongest case against

**You are running a massively underpowered, multiply-compared exploratory analysis on operator behavior data while framing it as a biological sex comparison.**

The voltages are set by operators, not by biology. The sample is ~35 per group --- below the conventional threshold where sex-difference claims become credible in neuroscience. The analysis plan involves dozens of statistical tests across channels, blocks, and metrics without pre-registration or clear primary vs exploratory designation. The 2-minute sliding window is an untested heuristic that could produce different results at 1.5 or 3 minutes. And the most relevant confounds (operator identity, condition assignment balance, anatomical variability, temporal enrollment patterns) are not controlled for.

This combination means that any "significant" finding is more likely to be a statistical artifact than a real sex difference, and any null finding cannot be interpreted as evidence of no difference. The analysis as designed cannot produce trustworthy conclusions in either direction.

The strongest version of this plan would: (1) use mixed-effects models to handle the nested structure and control confounds simultaneously, (2) pre-specify one or two primary metrics with power calculations, (3) label everything else as explicitly exploratory with FDR correction, (4) include a sensitivity analysis for the sliding window parameter, and (5) frame findings as "operator-mediated voltage patterns associated with participant sex" rather than "sex differences in stimulation."

## Sources

- [Anatomically mediated variability of hippocampal electric fields in TIS](https://www.sciencedirect.com/science/article/pii/S1053811925006445) --- inter-individual anatomical variability as primary driver of TI stimulation differences
- [On the need of individually optimizing TIS due to inter-individual variability](https://www.sciencedirect.com/science/article/pii/S1935861X25002748) --- sex effects mediated by anatomy, not direct sex effects
- [Sex differences in the human brain: a roadmap for more careful analysis](https://pmc.ncbi.nlm.nih.gov/articles/PMC9327177/) --- small sample sizes as central problem in sex-difference neuroimaging research
- [How hype and hyperbole distort the neuroscience of sex differences](https://journals.plos.org/plosbiology/article?id=10.1371/journal.pbio.3001253) --- critique of unjustified emphasis on marginal findings in sex-difference research
- [Consideration of Sample Size in Neuroscience Studies](https://www.jneurosci.org/content/40/21/4076) --- median power of 8-31% in neuroscience studies
- [Remembering the null hypothesis when searching for brain sex differences](https://bsd.biomedcentral.com/articles/10.1186/s13293-024-00585-4) --- underpowered studies and premature conclusions
- [Sliding window correlation performance for dynamic functional connectivity](https://pmc.ncbi.nlm.nih.gov/articles/PMC4889509/) --- window length as dominant factor in detection performance
- [Dynamic adaptive event detection with change-point weighting](https://www.sciencedirect.com/science/article/abs/pii/S0306261924002332) --- adaptive thresholds superior to fixed windows
- [Optimal sample size planning for Wilcoxon-Mann-Whitney test](https://pmc.ncbi.nlm.nih.gov/articles/PMC6491996/) --- power considerations for Mann-Whitney U
- [Use and misuse of corrections for multiple testing](https://www.sciencedirect.com/science/article/pii/S2590260123000115) --- FDR vs FWER trade-offs in exploratory studies

## Assessment

**Moderate-to-strong concerns.** The opposition raises genuine methodological issues that the plan should address, but they do not make the analysis worthless --- they make it need better framing and statistical machinery.

The strongest points are: (1) the operator-mediated nature of voltage data means "sex differences in voltage" is a misleading frame, (2) the multiple comparisons burden is severe for n~35/group, and (3) the fixed 2-minute window needs sensitivity validation. These are addressable but non-trivial.

The plan's creative additions (asymmetry, stability, time-to-stable) are genuinely interesting but compound the multiple-testing problem. The most defensible version of this analysis would use mixed-effects models with pre-specified primary outcomes and clearly labeled exploratory metrics. The plan is worth executing, but with significant methodological guardrails added.
