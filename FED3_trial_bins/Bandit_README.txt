Bandit Trialsbin README
=======================

Purpose of this script
----------------------

This script analyzes FED3 two-choice bandit task data in a trial-reconstructed
way.

In this script, a "trial" is a true decision event:

    Event == Left
    Event == Right

Other raw event rows are not treated as decision trials. They may still be
important in the raw file, but for the bandit analysis the behavioral unit is a
left or right choice.

The script converts raw FED3 CSV files into:

    1. Reconstructed trial-level choice/reward data.
    2. One-row-per-mouse behavior metrics.
    3. Trials-back odds ratio metrics.
    4. Exponential moving average learning curves.
    5. Switch-aligned / peak accuracy curves.
    6. Optional dark/light phase-specific outputs.
    7. Optional PCA outputs and PCA plots.
    8. GraphPad Prism-friendly wide-format sheets.
    9. Diagnostic plots routed into consistent plot folders.

In this README, "reward" and "win" mean the same thing.


Input files and metadata
------------------------

The script expects raw FED3 CSV files from a bandit task.

Required raw columns include:

    MM:DD:YYYY hh:mm:ss
    Event
    Pellet_Count
    High_prob_poke

The metadata file, or manually entered metadata, is used to identify:

    - mouse ID
    - sex
    - genotype/group

The exact names of these metadata columns do not have to be "Mouse ID", "Sex",
or "Genotype"; the script uses the first three metadata columns after Filename
as:

    mouse_col
    sex_col
    group_col


Trial reconstruction
--------------------

Definition of a trial
~~~~~~~~~~~~~~~~~~~~~

One reconstructed trial is one valid choice event:

    Left
    Right

The script first cleans the raw Event column and keeps only these two true
choice events. The reconstructed trial number is then assigned after filtering:

    Trial 1 = first Left/Right choice
    Trial 2 = second Left/Right choice
    Trial 3 = third Left/Right choice
    ...

This means Trial is an analysis index, not necessarily the same thing as raw CSV
row number.

Plain-language note:

    For all intents and purposes, the only events that become trials are true
    decisions. In this task, that means Left or Right pokes. Everything else in
    the raw CSV Event column is treated as a non-decision event log rather than
    a bandit choice. The analysis then keeps the reconstructed choice, the
    reward assigned to that choice, the current high-probability side, the
    timestamp, the reconstructed trial number, and whether the choice was made
    on the high-probability side.


Choice
~~~~~~

The Choice column is derived directly from the cleaned event:

    Event == Left  -> Choice = left
    Event == Right -> Choice = right


Reward
~~~~~~

Reward is reconstructed from Pellet_Count.

The key detail is that the pellet event usually occurs after the choice row, not
on the same row as the choice. Therefore the script looks forward from the
current choice until just before the next choice.

For each choice trial:

    start_count = Pellet_Count at the choice row

    window = rows from the current choice up to, but not including, the next
             choice

    Reward = 1 if Pellet_Count increases anywhere in that window
    Reward = 0 otherwise

Formula:

    Reward = int(any(Pellet_Count in window > start_count))

Interpretation:

    Reward = 1 means the choice was followed by pellet delivery before the next
    choice.

    Reward = 0 means no pellet was detected before the next choice.

Why the script looks forward:

    The pellet event happens after the choice, not necessarily on the same raw
    CSV row as the choice. That is why the script looks at the pellet count at
    the moment of the choice, then scans forward until the next choice. If the
    pellet count increases before the next choice, the reward is assigned to the
    previous choice.


HighProbSide and HighProb
~~~~~~~~~~~~~~~~~~~~~~~~~

HighProbSide comes from the raw High_prob_poke column.

For each reconstructed trial:

    HighProb = Choice == HighProbSide

Interpretation:

    HighProb = True
        The mouse chose the currently high-probability side.

    HighProb = False
        The mouse chose the currently low-probability side.


Switch and SwitchNumber
~~~~~~~~~~~~~~~~~~~~~~~

The bandit task can reverse which side is high-probability.

The script detects reversals by checking for changes in HighProbSide:

    Switch = HighProbSide != previous HighProbSide

The first trial is forced to:

    Switch = False

SwitchNumber is the cumulative count of detected switches:

    SwitchNumber = cumulative sum of Switch


Phase assignment
----------------

If dark/light analysis is enabled, each reconstructed trial receives:

    Phase

based on the trial timestamp and the user-entered light cycle start/end times.

If dark/light analysis is not enabled:

    Phase = All

For phase-specific outputs, the script analyzes trials assigned to each phase
separately.


Behavior metrics
----------------

Behavior metrics are calculated from reconstructed choice and reward trials.
Most of these metrics ask how the previous trial influences the current choice.

Plain-language note:

    Behavior metrics are pretty simple once you understand the odds-ratio logic.
    They use the immediate previous trial and ask whether that previous outcome
    affects the current choice. In other words, the core question is:

        Did the animal stay or shift after the previous trial was rewarded or
        unrewarded?

For a current trial i:

    C(i) = current choice
    C(i-1) = previous choice

    R(i) = current reward
    R(i-1) = previous reward

    Stay(i) = 1 if C(i) == C(i-1), else 0
    Shift(i) = 1 - Stay(i)

The first trial has no previous trial, so it cannot contribute to stay/shift
metrics.

Useful notation:

    i = current trial
    i - 1 = previous trial

    C(i) = choice on trial i
    R(i) = reward on trial i, where 1 = reward and 0 = no reward

    Stay(i) = 1 if C(i) == C(i-1), else 0
    Shift(i) = 1 - Stay(i)


WinStay
~~~~~~~

Meaning:

    Probability of staying with the same side after a rewarded previous trial.

Formula:

    WinStay =
        count(Stay == True and previous Reward == 1)
        /
        count(previous Reward == 1)

Equivalent:

    WinStay = P(Stay | previous Win)


WinShift
~~~~~~~~

Meaning:

    Probability of switching sides after a rewarded previous trial.

Formula:

    WinShift =
        count(Shift == True and previous Reward == 1)
        /
        count(previous Reward == 1)

Equivalent:

    WinShift = P(Shift | previous Win)

Normally:

    WinStay + WinShift = 1

when there is at least one previous rewarded trial.


LoseStay
~~~~~~~~

Meaning:

    Probability of staying with the same side after an unrewarded previous
    trial.

Formula:

    LoseStay =
        count(Stay == True and previous Reward == 0)
        /
        count(previous Reward == 0)

Equivalent:

    LoseStay = P(Stay | previous Loss)


LoseShift
~~~~~~~~~

Meaning:

    Probability of switching sides after an unrewarded previous trial.

Formula:

    LoseShift =
        count(Shift == True and previous Reward == 0)
        /
        count(previous Reward == 0)

Equivalent:

    LoseShift = P(Shift | previous Loss)

Normally:

    LoseStay + LoseShift = 1

when there is at least one previous unrewarded trial.


RewardAcquisition / Win rate
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Meaning:

    Proportion of reconstructed choice trials that were rewarded.

Formula:

    RewardAcquisition = mean(Reward)

Equivalent:

    RewardAcquisition = TotalRewards / TotalTrials

In exported display names, this is shown as:

    Win rate (%)

when scaled for output/plotting.


TotalTrials and TotalRewards
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

TotalTrials:

    Number of reconstructed left/right choice trials.

Formula:

    TotalTrials = count(reconstructed trials)

TotalRewards:

    Number of rewarded reconstructed trials.

Formula:

    TotalRewards = sum(Reward)


SwitchRate
~~~~~~~~~~

Meaning:

    Proportion of previous-trial comparisons where the mouse switched sides.

Formula:

    SwitchRate = mean(Shift)

Rows included:

    Trials with a valid previous choice.


LeftBias
~~~~~~~~

Meaning:

    Proportion of reconstructed trials where the mouse chose Left.

Formula:

    LeftBias = count(Choice == left) / TotalTrials

RightBias is not separately needed because:

    RightBias = 1 - LeftBias


OutcomeSensitivity
~~~~~~~~~~~~~~~~~~

Meaning:

    Whether the mouse is more likely to switch after losses than after wins.

Formula:

    OutcomeSensitivity = LoseShift - WinShift

Equivalent:

    OutcomeSensitivity = P(Shift | Loss) - P(Shift | Win)

Interpretation:

    Greater than 0:
        The mouse switches more after losses than after wins. This is consistent
        with reward-guided behavior.

    Equal to 0:
        The previous outcome does not strongly change switch probability.

    Less than 0:
        The mouse switches more after wins than after losses, which is
        counterintuitive for this task.


LearningIndex
~~~~~~~~~~~~~

Meaning:

    Overall reward-sensitive strategy score.

Formula used by the current script:

    LearningIndex = ((WinStay + LoseShift) / 2) * 100

Interpretation:

    WinStay rewards the strategy "stay after winning."

    LoseShift rewards the strategy "shift after losing."

    The script averages those two conditional probabilities and converts the
    result to a percentage.

Scale:

    0%:
        Very poor / opposite reward-sensitive behavior.

    50%:
        Roughly chance-like strategy behavior.

    100%:
        Perfect win-stay and lose-shift behavior.

Note:

    Older wording sometimes describes WinStay + LoseShift as a 0-to-2 score.
    The current script exports LearningIndex as the average of those two rates,
    multiplied by 100.


High-probability and low-probability context metrics
----------------------------------------------------

The script also asks whether previous-trial learning behavior differs depending
on whether the previous trial was a high-probability choice or a low-probability
choice.

For each previous trial:

    PrevHighProb = True if the previous choice was the high-probability side
    PrevHighProb = False if the previous choice was the low-probability side


HighProbWinStay
~~~~~~~~~~~~~~~

Meaning:

    Probability of staying after a rewarded previous high-probability choice.

Formula:

    HighProbWinStay =
        P(Stay | previous Reward == 1 and previous HighProb == True)


HighProbLoseShift
~~~~~~~~~~~~~~~~~

Meaning:

    Probability of shifting after an unrewarded previous high-probability choice.

Formula:

    HighProbLoseShift =
        P(Shift | previous Reward == 0 and previous HighProb == True)


HighProbOutcomeSensitivity
~~~~~~~~~~~~~~~~~~~~~~~~~~

Meaning:

    Outcome sensitivity within previous high-probability trials.

Formula used by the script:

    HighProbOutcomeSensitivity =
        HighProbLoseShift + HighProbWinStay - 1

Why this matches outcome sensitivity:

    WinShift = 1 - WinStay

So:

    LoseShift - WinShift
        = LoseShift - (1 - WinStay)
        = LoseShift + WinStay - 1


LowProbWinStay
~~~~~~~~~~~~~~

Meaning:

    Probability of staying after a rewarded previous low-probability choice.

Formula:

    LowProbWinStay =
        P(Stay | previous Reward == 1 and previous HighProb == False)


LowProbLoseShift
~~~~~~~~~~~~~~~~

Meaning:

    Probability of shifting after an unrewarded previous low-probability choice.

Formula:

    LowProbLoseShift =
        P(Shift | previous Reward == 0 and previous HighProb == False)


LowProbOutcomeSensitivity
~~~~~~~~~~~~~~~~~~~~~~~~~

Meaning:

    Outcome sensitivity within previous low-probability trials.

Formula:

    LowProbOutcomeSensitivity =
        LowProbLoseShift + LowProbWinStay - 1


Trials-back odds ratio
----------------------

The odds ratio asks how strongly reward history predicts staying versus
switching.

Plain-language note:

    Odds ratio calculates how much past reward influences staying versus
    switching. It is essentially:

        reward-sensitive behaviors / opposite behaviors

    The reward-sensitive behaviors are:

        rewarded -> stay
        unrewarded -> shift

    The opposite behaviors are:

        rewarded -> shift
        unrewarded -> stay

For TrialsBack = -k, the script compares current trial i with trial i-k.

For example:

    TrialsBack = -1
        Compare trial i with the immediately previous trial.

    TrialsBack = -2
        Compare trial i with the trial two choices back.

For each k, the script counts:

    A = WinStay
        previous trial was rewarded and current choice stayed

    B = WinShift
        previous trial was rewarded and current choice shifted

    C = LoseStay
        previous trial was unrewarded and current choice stayed

    D = LoseShift
        previous trial was unrewarded and current choice shifted

The standard odds ratio is:

    OddsRatio = (A * D) / (B * C)

The script uses a 0.5 continuity correction:

    OddsRatio =
        ((A + 0.5) * (D + 0.5))
        /
        ((B + 0.5) * (C + 0.5))

This avoids divide-by-zero errors when one of the event counts is zero.

So in compact form:

    OddsRatio =
        (WinStay * LoseShift)
        /
        (WinShift * LoseStay)

with the script using the adjusted +0.5 version for numerical stability.

Interpretation:

    OddsRatio > 1
        Reward history biases behavior in the expected direction:
        rewarded choices encourage staying and unrewarded choices encourage
        shifting.

    OddsRatio = 1
        Reward history does not strongly affect stay/shift behavior.

    OddsRatio < 1
        Behavior is opposite or counterintuitive relative to win-stay/lose-shift
        learning.

Trials-back interpretation:

    OR-1 compares trial i with trial i-1.

    OR-2 compares trial i with trial i-2.

    OR-3 compares trial i with trial i-3.

    And so on.

For OR-1, the script compares trial 2 with trial 1, trial 3 with trial 2, trial
4 with trial 3, and continues through all valid pairs. For OR-2, it compares
trial 3 with trial 1, trial 4 with trial 2, and so on.


Exponential moving average learning curves
------------------------------------------

The script calculates EMA curves for:

    RewardEMA
    LearningIndexEMA
    OutcomeSensitivityEMA
    CumRewards

The user chooses the smoothing window in the GUI.

Historical note about rolling reward:

    Earlier versions / explanations referred to rolling reward. That idea is
    still useful conceptually, but the current script uses EMA curves rather
    than the old simple rolling reward curve.

    A simple rolling reward curve estimates recent reward probability by taking
    the mean of Reward values inside a sliding window. For example, if the first
    three rewards are:

        1, 0, 1

    then the mean over those three trials is:

        (1 + 0 + 1) / 3 = 2 / 3

    With a window of 20, trial 20 would average trials 1-20, and trial 21 would
    average trials 2-21. Smaller windows react quickly but are noisy. Larger
    windows are smoother but slower to react.

    The current EMA approach keeps the same intuition of smoothing recent
    performance, but older trials fade gradually rather than dropping out
    abruptly at a window boundary.

General EMA formula:

    EMA_t = alpha * x_t + (1 - alpha) * EMA_(t-1)

where:

    alpha = 2 / (window + 1)

Meaning:

    - the current trial receives the highest individual weight,
    - recent trials receive moderately high weight,
    - older trials decay gradually,
    - very old trials contribute minimally.

This is different from a simple rolling mean. A rolling mean gives equal weight
to all observations inside the window and zero weight to observations outside
the window. EMA decays smoothly, which is often better for visualizing gradual
bandit learning.

Example with a large smoothing window:

    If window = 100:

        alpha = 2 / (100 + 1)
              = 0.0198

    If the previous EMA is:

        EMA_(t-1) = 0.5

    and the current trial is rewarded:

        x_t = 1

    then:

        EMA_t = (0.0198 * 1) + (0.9802 * 0.5)
              = 0.5099

    So even though the animal got rewarded on the current trial, the smoothed
    value moves only from 0.5 to 0.5099. That is the point: only repeated,
    consistent behavior gradually shifts the curve.

Expanded EMA weights:

    EMA_t =
        alpha * x_t
        + alpha * (1 - alpha) * x_(t-1)
        + alpha * (1 - alpha)^2 * x_(t-2)
        + alpha * (1 - alpha)^3 * x_(t-3)
        + ...

This means recent trials dominate, older trials fade gradually, and very old
trials contribute minimally. This is why EMA is usually more useful than a
simple rolling mean for showing broad bandit-learning trends.


RewardEMA / WinRateEMA
~~~~~~~~~~~~~~~~~~~~~~

RewardEMA is the EMA of Reward:

    RewardEMA = EMA(Reward)

Because Reward is coded:

    Reward = 1 for win
    Reward = 0 for loss

RewardEMA is a smoothed win rate.

In the Excel output, RewardEMA is scaled by 100 in the sheet:

    WinRateEMA (%)

So the plotted y-axis is percent win rate.


LearningIndexEMA
~~~~~~~~~~~~~~~~

LearningIndexEMA is not calculated by simply smoothing raw learning-index events
across all trials.

That would be misleading because win-stay and lose-shift have different
opportunity denominators:

    A trial after a win can contribute to win-stay or win-shift.
    A trial after a loss can contribute to lose-stay or lose-shift.

Plain-language note:

    Win rate EMA is simple because every trial has an outcome:

        Win = 1
        Loss = 0

    So:

        WinRateEMA = EMA(Win)

    Learning index is different because it is based on conditional behaviors.
    Not every trial is eligible for both win-stay and lose-shift. A trial
    following a win is eligible for win-stay or win-shift. A trial following a
    loss is eligible for lose-stay or lose-shift.

    This is why a simple:

        EMA(WinStayTrial + LoseShiftTrial)

    would be misleading. It smooths raw events across all trials and can make
    the values look artificially low because each event type only has
    opportunities on some trials.

The script smooths numerator and denominator opportunities separately.

For win-stay:

    WinStayEMA =
        EMA(WinStayTrial)
        /
        EMA(PrevWinTrial)

For lose-shift:

    LoseShiftEMA =
        EMA(LoseShiftTrial)
        /
        EMA(PrevLossTrial)

Then:

    LearningIndexEMA =
        ((WinStayEMA + LoseShiftEMA) / 2) * 100

This makes the EMA version conceptually match the summary LearningIndex:

    LearningIndex = average of win-stay rate and lose-shift rate


OutcomeSensitivityEMA
~~~~~~~~~~~~~~~~~~~~~

OutcomeSensitivityEMA compares smoothed lose-shift and win-shift rates.

For win-shift:

    WinShiftEMA =
        EMA(WinShiftTrial)
        /
        EMA(PrevWinTrial)

Then:

    OutcomeSensitivityEMA =
        LoseShiftEMA - WinShiftEMA

Interpretation:

    Positive values mean the mouse is more likely to shift after losses than
    after wins.


CumulativeWins
~~~~~~~~~~~~~~

CumulativeWins is the running total of rewarded trials:

    CumRewards = cumulative sum of Reward


Switch-aligned / peak accuracy analysis
---------------------------------------

Peak accuracy is a peri-switch analysis. It asks how accurately the mouse chose
the high-probability side around reversals in HighProbSide.

Plain-language note:

    Peak accuracy is used to examine how accurately mice choose the currently
    high-probability side around a probability switch or reversal.

    In the bandit task, the high-probability side can switch from Left to Right
    or from Right to Left. The script detects these switches by looking for
    changes in the High_prob_poke / HighProbSide column after trials are
    reconstructed.

The script detects a switch whenever:

    HighProbSide changes from the previous reconstructed trial

For each detected switch, the user-selected peak accuracy window is applied.

For each surrounding trial:

    RelativeTrial = trial position relative to the switch

    RelativeTrial = 0
        The first trial where the new high-probability side is active.

    Negative RelativeTrial values
        Trials before the switch.

    Positive RelativeTrial values
        Trials after the switch.

The metric is:

    PeakAccuracy = 1 if Choice == HighProbSide
    PeakAccuracy = 0 otherwise

In plain language:

    PeakAccuracy is switch-aligned high-probability choice accuracy.

Interpretation:

    Before the switch:
        High values indicate that the mouse was choosing the old high-probability
        side.

    At the switch:
        Accuracy may drop if the mouse perseverates on the previously good side.

    After the switch:
        Recovery indicates adaptation to the new high-probability side.

What the curve tells you:

    If the mouse learned the previous block well, accuracy before the switch
    should be relatively high.

    At RelativeTrial = 0, the high-probability side changes. If the mouse keeps
    choosing the previously rewarded side, accuracy usually drops because the
    previously good option has become the low-probability option.

    After the switch, positive relative trials show how quickly the mouse adapts
    to the new high-probability side. If the mouse learns the reversal well,
    accuracy should gradually recover.

This makes peak accuracy useful for visualizing reversal adaptation. It tells us
whether mice:

    - performed well before the switch,
    - were disrupted by the switch,
    - and recovered/adapted after the switch.

If dark/light analysis is enabled, switches are assigned to the phase in which
the switch trial itself occurred:

    RelativeTrial = 0 phase determines the switch phase.

This means a Dark peak-accuracy curve is aligned to switches that occurred in
Dark, even if the surrounding window extends into another phase.

Peak accuracy is a curve, not a single summary metric. It is usually most useful
as a graph/output tab rather than as a PCA feature.


PCA
---

PCA is optional and exploratory.

The script allows PCA feature groups to be selected in the GUI. Potential
feature groups include:

    - behavior metrics
    - odds ratio values
    - learning / trajectory-related metrics depending on current script options

Before PCA:

    - rows are organized by mouse,
    - selected features are assembled,
    - missing values are handled,
    - features are standardized with StandardScaler.

PCA outputs can include:

    PCA
        PCA input-like mouse-level metrics when PCA is performed.

    PCA_Loadings
        Contribution of each feature to principal components.

    PCA plots
        Joint plots by sex, group, sex x group, and optionally phase.

Important interpretation notes:

    - PCA is descriptive, not a statistical test.
    - PC1 and PC2 axes can flip sign without changing the interpretation.
    - The percentage on each PCA axis is explained variance.
    - Loadings show which variables contribute most strongly to each component.


Excel workbook overview
-----------------------

The script saves:

    Bandit_EXTRAS.xlsx

Main full-session sheets:

    OddsRatio
        Wide Prism-friendly table of odds ratio values by TrialsBack.

    BehaviorMetrics
        One row per mouse containing summary behavior metrics.

    PCA
        Exported only when PCA is performed.

    PCA_Loadings
        Exported only when PCA is performed.

    WinRateEMA (%)
        Wide trial trajectory table for RewardEMA / win rate.

    LearningIndexEMA (%)
        Wide trial trajectory table for LearningIndexEMA.

    OutcomeSensitivityEMA
        Wide trial trajectory table for OutcomeSensitivityEMA.

    CumulativeWins
        Wide trial trajectory table for cumulative rewards.

    PeakAccuracy
        Wide switch-aligned table for peak accuracy.

Optional phase sheets, when dark/light analysis is enabled:

    OddsRatio_Dark
    OddsRatio_Light

    WinRateEMA (%)_Dark
    WinRateEMA (%)_Light

    LearningIndex (%)_Dark
    LearningIndex (%)_Light

    OutcomeSensitivity_Dark
    OutcomeSensitivity_Light

    CumulativeWins_Dark
    CumulativeWins_Light

    PeakAccuracy_Dark
    PeakAccuracy_Light

    Behavior_Dark
    Behavior_Light

    PCA_Dark
    PCA_Light
        Exported when PCA is performed and phase data are available.


Plot output folders
-------------------

Plots are routed under:

    Bandit_Plots

Current plot folders:

    All
        General full-session plots.

    Dark
        Dark-phase plots.

    Light
        Light-phase plots.

    PCA
        PCA score/loading plots.

    Heatmaps
        Behavior heatmaps and correlation heatmaps.

    PeriTrial
        Peak accuracy / switch-aligned plots.

    Stacked
        Stacked cumulative-wins plus learning/outcome trajectory plots.


Graph families
--------------

The script can produce plots for:

    Odds ratio
        OddsRatio by TrialsBack.

    Peak accuracy
        Switch-aligned high-probability choice accuracy.

    Cumulative wins
        Cumulative reward acquisition across trials.

    Win rate EMA
        Smoothed reward acquisition / win rate.

    Learning index EMA
        Smoothed win-stay / lose-shift strategy quality.

    Outcome sensitivity EMA
        Smoothed sensitivity to loss-versus-win feedback.

    Stacked behavior plots
        Cumulative wins combined with LearningIndexEMA or
        OutcomeSensitivityEMA.

    Behavior metric stripplots
        Individual-mouse summary behavior metrics.

    Heatmaps
        Group x sex summary patterns.

    Correlation heatmap
        Correlations among selected PCA/behavior features.

    PCA plots
        Mouse-level PCA scores and PCA loadings.


Important interpretation notes
------------------------------

1. Reward and win are interchangeable in this script.

   Reward = 1 means the reconstructed choice produced a pellet before the next
   choice.


2. Trial means choice trial.

   A trial is not every raw event row. It is only a Left or Right choice event.


3. HighProb measures choice optimality, not reward delivery.

   A high-probability choice can still be unrewarded, and a low-probability
   choice can still occasionally be rewarded.


4. LearningIndex is strategy quality, not raw win rate.

   Win rate asks:

       Did the mouse get rewarded?

   LearningIndex asks:

       Did the mouse stay after wins and shift after losses?


5. OddsRatio is reward-history sensitivity.

   It asks whether past reward changes the odds of staying versus shifting.


6. PeakAccuracy is switch-aligned.

   It is not the same as whole-session accuracy. It specifically asks how choice
   accuracy changes around probability reversals.


Validation checklist
--------------------

Recommended spot checks:

    1. Open a raw CSV and confirm that only Left/Right events become reconstructed
       trials.

    2. For a few choices, check Pellet_Count from that choice to the next choice
       and confirm Reward is assigned correctly.

    3. Check HighProb:

           HighProb = Choice == HighProbSide

    4. Check a few switch points:

           Switch = True when HighProbSide changes.

    5. For one mouse, manually calculate WinStay, LoseShift, OutcomeSensitivity,
       and LearningIndex from a small set of trials.

    6. Check OddsRatio for TrialsBack = -1 using the same win-stay/win-shift and
       lose-stay/lose-shift counts.

    7. Check that EMA window rows in the trajectory sheets match the selected GUI
       smoothing window.

    8. For peak accuracy, confirm RelativeTrial = 0 is the first trial where the
       new high-probability side is active.


End of README.
