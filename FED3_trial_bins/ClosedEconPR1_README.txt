ClosedEcon PR1 Trialsbin README
================================

Purpose of this script
----------------------

This script analyzes FED3 Closed Economy PR1 data by reconstructing pellet-to-pellet
work intervals.

In this script, one completed trial is one pellet delivery:

    Trial 1 = interval ending at pellet 1
    Trial 2 = interval ending at pellet 2
    Trial 3 = interval ending at pellet 3

The script converts raw FED3 event logs into:

    1. A reconstructed trial-level dataset.
    2. One-row-per-mouse summary metrics.
    3. FR-level demand metrics.
    4. Optional dark/light and dark/light-exclusive versions of those metrics.
    5. Prism-friendly sheets for summary, trial trajectory, and demand plots.
    6. Diagnostic plots routed into consistent plot folders.


Important conceptual distinction: Trial vs FR vs Block
------------------------------------------------------

Trial
~~~~~

Trial is created by the script. It is the sequential number of pellet deliveries
reconstructed from the raw file.

If a mouse earns 500 pellets, then it has 500 completed trials.

Trial number increases continuously across the session:

    Trial 1, Trial 2, Trial 3, ..., Trial N


FR
~~

FR is the fixed-ratio / progressive-ratio cost recorded in the FED3 file.

FR answers:

    What response requirement was associated with this pellet interval?

FR is not the same thing as trial number. A mouse may earn many pellets at FR1,
many pellets at FR2, many pellets at FR3, and so on.


Block
~~~~~

Block is reconstructed by the script. A new block is detected when
Block_Pellet_Count resets.

If concatenated files are used, a change in Concat_# is also treated as a possible
block boundary. This helps with FED3 auto-restarts or manually concatenated raw
files.


Input files and metadata
------------------------

The script expects raw FED3 CSV files from a ClosedEcon PR1 task.

Required raw columns are:

    - MM:DD:YYYY hh:mm:ss
    - Event
    - FR
    - Left_Poke_Count
    - Right_Poke_Count
    - Pellet_Count
    - Block_Pellet_Count
    - Retrieval_Time

The script also uses metadata to identify each mouse and its group variables.
The metadata headers do not have to literally be "Mouse ID", "Sex", or
"Genotype"; the GUI asks the user which columns correspond to:

    - mouse ID
    - sex
    - genotype/group

The metadata file must contain a Filename column so each raw file can be matched
to the correct animal metadata.

Duplicate raw filenames are rejected because metadata matching would be
ambiguous.


Active poke side
----------------

The script asks which poke side is active:

    Left
    Right
    Auto

If the active side is known, entering it directly is safest.

If Auto is selected, the script attempts to infer the active side from the
Active_Poke column when that column is present and consistent.

Once the active side is known:

    if active side is Left:
        ActivePokes   = LeftPokes
        InactivePokes = RightPokes

    if active side is Right:
        ActivePokes   = RightPokes
        InactivePokes = LeftPokes


How trials are reconstructed
----------------------------

The script parses the timestamp column:

    MM:DD:YYYY hh:mm:ss

It converts relevant raw columns to numeric values where possible:

    FR
    Left_Poke_Count
    Right_Poke_Count
    Pellet_Count
    Block_Pellet_Count
    Retrieval_Time
    InterPelletInterval
    Poke_Time
    Correct_Poke
    Binary_Left_Pokes
    Binary_Right_Pokes
    Binary_Pellets

Pellet events are identified using:

    Event == "Pellet"

and, if present:

    Binary_Pellets == 1

Each pellet event marks the end of a completed reconstructed trial.

For each completed trial, the script takes the interval from immediately after
the previous pellet to the current pellet, then summarizes all work inside that
interval.

The first trial begins at the first row of the raw file and ends at the first
pellet event.


How left and right pokes are calculated
---------------------------------------

The script primarily uses cumulative raw poke count columns:

    Left_Poke_Count
    Right_Poke_Count

For a reconstructed interval:

    LeftPokes  = last Left_Poke_Count  - first Left_Poke_Count
    RightPokes = last Right_Poke_Count - first Right_Poke_Count

There is one adjustment:

If the first row of the interval is itself a poke, that poke is already included
in the cumulative count at the start of the interval. A simple end-minus-start
calculation would miss it. The script adds that first poke back:

    if first row is a left poke:
        LeftPokes = LeftPokes + 1

    if first row is a right poke:
        RightPokes = RightPokes + 1

Negative poke counts are clipped to zero.


Completed trials and incomplete final intervals
-----------------------------------------------

Completed trial
~~~~~~~~~~~~~~~

A completed trial is an interval ending in pellet delivery.

In the Trials sheet:

    Completed = 1

For completed trials:

    PokesPerPellet       = TotalPokes
    ActivePokesPerPellet = ActivePokes

This is because each completed trial corresponds to exactly one earned pellet.


Incomplete final interval
~~~~~~~~~~~~~~~~~~~~~~~~~

The script can optionally include a final unfinished interval if the mouse made
pokes after the final pellet but did not earn another pellet before the file
ended.

In the Trials sheet:

    Completed = 0

For incomplete final intervals:

    PokesPerPellet       = blank / NaN
    ActivePokesPerPellet = blank / NaN
    RetrievalTime        = blank / NaN
    InterPelletInterval  = blank / NaN

The incomplete interval contributes to whole-session poke totals, but it is not
counted as a completed pellet trial.


Dark/light phase assignment
---------------------------

If dark/light analysis is enabled, the script asks for light cycle start and end
times.

Each reconstructed trial receives:

    Phase
        The phase used for splitting analyses.

    StartPhase
        Phase at the beginning of the interval.

    EndPhase
        Phase at the end of the interval.

    PhaseCrossing
        TRUE if StartPhase and EndPhase differ.

For ClosedEcon PR1:

    Phase = EndPhase

For completed trials, EndTime is the pellet time, so a trial is assigned to the
phase in which the pellet was earned.

The script keeps phase-crossing trials in the main dark/light analysis. This is
intentional because high-ratio trials can be long, and automatically excluding
boundary-crossing trials could bias duration, vigor, and demand metrics.

The script also exports exclusive dark/light sheets and plots where
PhaseCrossing == False.


Trial vs PhaseTrial
-------------------

The script exports:

    Trial
        Full-session trial number.

    PhaseTrial
        Trial number within the assigned Phase.

Full-session plots use Trial.

Dark/light-specific plots use PhaseTrial.


Core trial-level formulas
-------------------------

These are calculated for each reconstructed interval in the Trials sheet.

Each interval is either:

    - a completed pellet interval, where Completed == 1, or
    - an optional unfinished final interval, where Completed == 0


Duration_s
~~~~~~~~~~

Meaning:

    The length of the reconstructed interval in seconds.

Formula:

    Duration_s = EndTime - StartTime

Notes:

    StartTime is the first timestamp in the interval.
    EndTime is the pellet timestamp for completed intervals.


Duration_min
~~~~~~~~~~~~

Meaning:

    The same interval duration expressed in minutes.

Formula:

    Duration_min = Duration_s / 60

Notes:

    Duration_min is used as the denominator for rate metrics such as Vigor,
    TotalPokeRate, and InactivePokeRate.


LeftPokes and RightPokes
~~~~~~~~~~~~~~~~~~~~~~~~

Meaning:

    The number of left-side and right-side pokes reconstructed inside the
    interval.

Formula:

    LeftPokes  = last Left_Poke_Count  - first Left_Poke_Count
    RightPokes = last Right_Poke_Count - first Right_Poke_Count

Adjustment:

    If the first row of the interval is itself a left poke:

        LeftPokes = LeftPokes + 1

    If the first row of the interval is itself a right poke:

        RightPokes = RightPokes + 1

Notes:

    Negative values are clipped to zero.


ActivePokes and InactivePokes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Meaning:

    ActivePokes are pokes on the programmed active side.
    InactivePokes are pokes on the non-active side.

Formula if active side is Left:

    ActivePokes = LeftPokes
    InactivePokes = RightPokes

Formula if active side is Right:

    ActivePokes = RightPokes
    InactivePokes = LeftPokes

Notes:

    These values depend on the active side selected in the GUI or inferred from
    the Active_Poke column when Auto is used.


TotalPokes
~~~~~~~~~~

Meaning:

    Total poke output during the reconstructed interval.

Formula:

    TotalPokes = ActivePokes + InactivePokes


Accuracy
~~~~~~~~

Meaning:

    The percentage of pokes made on the active side during the interval.

Formula:

    Accuracy (%) = (ActivePokes / TotalPokes) * 100

Notes:

    If TotalPokes is zero, Accuracy is blank / NaN.


InactivePokePercent
~~~~~~~~~~~~~~~~~~~

Meaning:

    The percentage of pokes made on the inactive side during the interval.

Formula:

    InactivePokePercent (%) = (InactivePokes / TotalPokes) * 100

Notes:

    If TotalPokes is zero, InactivePokePercent is blank / NaN.
    For a normal two-side setup, Accuracy + InactivePokePercent should usually
    equal 100 for intervals with at least one poke.


Vigor
~~~~~

Meaning:

    Active-side response rate. This is the rate of task-relevant responding.

Formula:

    Vigor = ActivePokes / Duration_min

Unit:

    active pokes per minute

Notes:

    Vigor is not total pokes per minute. It only uses ActivePokes in the
    numerator.


TotalPokeRate
~~~~~~~~~~~~~

Meaning:

    Overall response rate, regardless of whether pokes were active or inactive.

Formula:

    TotalPokeRate = TotalPokes / Duration_min

Unit:

    total pokes per minute


InactivePokeRate
~~~~~~~~~~~~~~~~

Meaning:

    Inactive-side response rate.

Formula:

    InactivePokeRate = InactivePokes / Duration_min

Unit:

    inactive pokes per minute


PokesPerPellet
~~~~~~~~~~~~~~

Meaning:

    The number of total pokes made to earn the pellet for this interval.

Formula for completed trials:

    PokesPerPellet = TotalPokes

Formula for incomplete final intervals:

    PokesPerPellet = blank / NaN

Notes:

    Because one completed ClosedEcon PR1 trial equals one pellet, the
    trial-level PokesPerPellet value is simply TotalPokes for that completed
    interval.


ActivePokesPerPellet
~~~~~~~~~~~~~~~~~~~~

Meaning:

    The number of active pokes made to earn the pellet for this interval.

For completed trials:

    ActivePokesPerPellet = ActivePokes

For incomplete final intervals:

    ActivePokesPerPellet = blank / NaN


RetrievalTime
~~~~~~~~~~~~~

Meaning:

    Pellet retrieval time recorded by the raw FED3 file for the completed pellet
    event.

Formula:

    RetrievalTime = raw Retrieval_Time value from the pellet row

Notes:

    This is blank / NaN for incomplete final intervals.


InterPelletInterval
~~~~~~~~~~~~~~~~~~~

Meaning:

    Raw FED3 interpellet interval value, if present in the file.

Formula:

    InterPelletInterval = raw InterPelletInterval value from the pellet row

Notes:

    This is blank / NaN for incomplete final intervals.


CumulativePellets
~~~~~~~~~~~~~~~~~

Meaning:

    Running count of completed pellet trials.

Formula:

    CumulativePellets = cumulative sum of Completed


CumulativeActivePokes
~~~~~~~~~~~~~~~~~~~~~

Meaning:

    Running total of active pokes across reconstructed intervals.

Formula:

    CumulativeActivePokes = cumulative sum of ActivePokes


CumulativeTotalPokes
~~~~~~~~~~~~~~~~~~~~

Meaning:

    Running total of all pokes across reconstructed intervals.

Formula:

    CumulativeTotalPokes = cumulative sum of TotalPokes


Summary metric formulas
-----------------------

The Summary sheet contains one row per mouse/file.

Some summary metrics use all reconstructed rows, including an optional
incomplete final interval. Other summary metrics use completed pellet trials
only. This distinction matters.


TotalPellets
~~~~~~~~~~~~

Meaning:

    Total number of pellets earned by the mouse.

Formula:

    TotalPellets = sum(Completed)

Rows included:

    Completed pellet trials only, because incomplete intervals have
    Completed == 0.


CompletedTrials
~~~~~~~~~~~~~~~

Meaning:

    Number of completed reconstructed pellet trials.

Formula:

    CompletedTrials = count of rows where Completed == 1

Notes:

    In this script, CompletedTrials should equal TotalPellets because one
    completed trial equals one pellet.


TotalPokes
~~~~~~~~~~

Meaning:

    Total poke output across the session.

Formula:

    TotalPokes = sum(TotalPokes)

Rows included:

    All reconstructed rows, including an optional incomplete final interval.


LeftPokes and RightPokes
~~~~~~~~~~~~~~~~~~~~~~~~

Meaning:

    Whole-session totals for left-side and right-side pokes.

Formulas:

    LeftPokes = sum(LeftPokes)

    RightPokes = sum(RightPokes)


ActivePokes and InactivePokes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Meaning:

    Whole-session totals for active-side and inactive-side pokes.

Formulas:

    ActivePokes = sum(ActivePokes)

    InactivePokes = sum(InactivePokes)


Accuracy
~~~~~~~~

Meaning:

    Pooled whole-session active-side poke percentage.

Formula:

    Accuracy (%) = (ActivePokes / TotalPokes) * 100

Notes:

    This is a pooled percentage from summed pokes, not the average of trial-level
    Accuracy values.


InactivePokePercent
~~~~~~~~~~~~~~~~~~~

Meaning:

    Pooled whole-session inactive-side poke percentage.

Formula:

    InactivePokePercent (%) = (InactivePokes / TotalPokes) * 100

Notes:

    This is the inactive-side counterpart to whole-session Accuracy.


PokesPerPellet
~~~~~~~~~~~~~~

Meaning:

    Average total pokes made per pellet earned across the whole session.

Formula:

    PokesPerPellet = TotalPokes / TotalPellets

Rows included:

    TotalPokes includes all reconstructed rows, including an optional incomplete
    final interval. TotalPellets includes completed pellet trials only.


ActivePokesPerPellet
~~~~~~~~~~~~~~~~~~~~

Meaning:

    Average active pokes made per pellet earned.

Formula:

    ActivePokesPerPellet = ActivePokes / TotalPellets


InactivePokesPerPellet
~~~~~~~~~~~~~~~~~~~~~~

Meaning:

    Average inactive pokes made per pellet earned.

Formula:

    InactivePokesPerPellet = InactivePokes / TotalPellets


TotalSessionTime_h
~~~~~~~~~~~~~~~~~~

Meaning:

    Total analyzed session duration in hours.

Formula:

    TotalSessionTime_h = (latest EndTime - earliest StartTime) / 3600

Notes:

    This uses the earliest reconstructed interval StartTime and the latest
    reconstructed interval EndTime.


PelletsPerHour
~~~~~~~~~~~~~~

Meaning:

    Whole-session pellet earning rate.

Formula:

    PelletsPerHour = TotalPellets / TotalSessionTime_h


ActivePokesPerHour
~~~~~~~~~~~~~~~~~~

Meaning:

    Whole-session active poke rate expressed per hour.

Formula:

    ActivePokesPerHour = ActivePokes / TotalSessionTime_h


FinalFR
~~~~~~~

Meaning:

    FR value on the last completed pellet trial.

Formula:

    FinalFR = FR from the final row where Completed == 1


MaxFR
~~~~~

Meaning:

    Highest FR value reached on any completed pellet trial.

Formula:

    MaxFR = maximum FR among rows where Completed == 1


MeanFR and MedianFR
~~~~~~~~~~~~~~~~~~~

Meaning:

    Average and median FR across completed pellet trials.

Formulas:

    MeanFR = mean(FR) among rows where Completed == 1

    MedianFR = median(FR) among rows where Completed == 1


MeanTrialDuration_min
~~~~~~~~~~~~~~~~~~~~~

Meaning:

    Average interval duration for completed pellet trials.

Formula:

    MeanTrialDuration_min = mean(Duration_min) among rows where Completed == 1


MeanVigor
~~~~~~~~~

Meaning:

    Average completed-trial active poke rate.

Trial-level formula:

    Vigor = ActivePokes / Duration_min

Summary formula:

    MeanVigor = mean(Vigor) among rows where Completed == 1

Expanded:

    MeanVigor = mean(ActivePokes / Duration_min) across completed pellet trials

Unit:

    active pokes per minute

Important note:

    MeanVigor is not the same as:

        sum(ActivePokes) / sum(Duration_min)

    The script averages the trial-level Vigor values.


MeanTotalPokeRate
~~~~~~~~~~~~~~~~~

Meaning:

    Average completed-trial total poke rate.

Trial-level formula:

    TotalPokeRate = TotalPokes / Duration_min

Summary formula:

    MeanTotalPokeRate = mean(TotalPokeRate) among rows where Completed == 1

Expanded:

    MeanTotalPokeRate = mean(TotalPokes / Duration_min) across completed pellet trials

Unit:

    total pokes per minute


MeanInactivePokeRate
~~~~~~~~~~~~~~~~~~~~

Meaning:

    Average completed-trial inactive poke rate.

Trial-level formula:

    InactivePokeRate = InactivePokes / Duration_min

Summary formula:

    MeanInactivePokeRate = mean(InactivePokeRate) among rows where Completed == 1

Expanded:

    MeanInactivePokeRate = mean(InactivePokes / Duration_min) across completed pellet trials

Unit:

    inactive pokes per minute


MeanInactivePokePercent
~~~~~~~~~~~~~~~~~~~~~~~

Meaning:

    Average completed-trial inactive poke percentage.

Trial-level formula:

    InactivePokePercent = (InactivePokes / TotalPokes) * 100

Summary formula:

    MeanInactivePokePercent = mean(InactivePokePercent) among rows where Completed == 1

Important note:

    MeanInactivePokePercent is not the same as pooled InactivePokePercent.

    Pooled InactivePokePercent =

        sum(InactivePokes) / sum(TotalPokes) * 100

    MeanInactivePokePercent =

        mean((InactivePokes / TotalPokes) * 100) across completed pellet trials


MeanRetrievalTime
~~~~~~~~~~~~~~~~~

Meaning:

    Average raw FED3 pellet retrieval time across completed pellet trials.

Formula:

    MeanRetrievalTime = mean(RetrievalTime) among rows where Completed == 1


MeanInterPelletInterval
~~~~~~~~~~~~~~~~~~~~~~~

Meaning:

    Average raw FED3 interpellet interval across completed pellet trials.

Formula:

    MeanInterPelletInterval = mean(InterPelletInterval) among rows where Completed == 1


BlocksCompleted
~~~~~~~~~~~~~~~

Meaning:

    Number of reconstructed blocks represented by completed pellet trials.

Formula:

    BlocksCompleted = number of unique Block values among rows where Completed == 1


IncompleteFinalInterval
~~~~~~~~~~~~~~~~~~~~~~~

Meaning:

    Whether the output includes an unfinished final interval.

Formula:

    IncompleteFinalInterval = 1 if any row has Completed == 0
    IncompleteFinalInterval = 0 otherwise


IncompleteFinalPokes
~~~~~~~~~~~~~~~~~~~~

Meaning:

    Number of pokes made in the unfinished final interval.

Formula:

    IncompleteFinalPokes = sum(TotalPokes) among rows where Completed == 0

Important distinction:

    InactivePokePercent is pooled from summed pokes.
    MeanInactivePokePercent is the mean of trial-level inactive-poke percentages.

Those are related but not identical.


Demand curve calculations
-------------------------

Demand curves are calculated from completed pellet trials only:

    Completed == 1

The script groups completed trials by FR.

For each mouse and FR:

    Pellets = number of completed trials at that FR

        Formula:

            Pellets = sum(Completed)

        Since completed trials are pellet-defined, this equals the number of
        pellets earned at that FR.

    LeftPokes = sum of left pokes at that FR

    RightPokes = sum of right pokes at that FR

    ActivePokes = sum of active pokes at that FR

    InactivePokes = sum of inactive pokes at that FR

    TotalPokes = sum of total pokes at that FR

    TotalDuration_min = sum of Duration_min at that FR

    PokesPerPellet

        Meaning:

            Average total pokes per pellet at that FR.

        Formula:

            PokesPerPellet = TotalPokes / Pellets

    ActivePokesPerPellet

        Meaning:

            Average active pokes per pellet at that FR.

        Formula:

            ActivePokesPerPellet = ActivePokes / Pellets

    InactivePokesPerPellet

        Meaning:

            Average inactive pokes per pellet at that FR.

        Formula:

            InactivePokesPerPellet = InactivePokes / Pellets

    PooledAccuracy

        Meaning:

            Pooled active-side poke percentage at that FR.

        Formula:

            PooledAccuracy (%) = (ActivePokes / TotalPokes) * 100

    InactivePokePercent

        Meaning:

            Pooled inactive-side poke percentage at that FR.

        Formula:

            InactivePokePercent (%) = (InactivePokes / TotalPokes) * 100

    PelletsPerMinute

        Meaning:

            Pellet earning rate at that FR.

        Formula:

            PelletsPerMinute = Pellets / TotalDuration_min

    MeanAccuracy

        Meaning:

            Mean of trial-level Accuracy values at that FR.

        Formula:

            MeanAccuracy = mean(Accuracy) among completed trials at that FR

    MeanVigor

        Meaning:

            Mean active poke rate at that FR.

        Trial-level formula:

            Vigor = ActivePokes / Duration_min

        Demand formula:

            MeanVigor = mean(Vigor) among completed trials at that FR

    MeanTotalPokeRate

        Meaning:

            Mean total poke rate at that FR.

        Formula:

            MeanTotalPokeRate = mean(TotalPokeRate) among completed trials at that FR

    MeanInactivePokeRate

        Meaning:

            Mean inactive poke rate at that FR.

        Formula:

            MeanInactivePokeRate = mean(InactivePokeRate) among completed trials at that FR

    MeanInactivePokePercent

        Meaning:

            Mean of trial-level inactive poke percentages at that FR.

        Formula:

            MeanInactivePokePercent = mean(InactivePokePercent) among completed trials at that FR

    MeanDuration_min

        Meaning:

            Mean completed interval duration at that FR.

        Formula:

            MeanDuration_min = mean(Duration_min) among completed trials at that FR

    MeanRetrievalTime

        Meaning:

            Mean raw FED3 retrieval time at that FR.

        Formula:

            MeanRetrievalTime = mean(RetrievalTime) among completed trials at that FR

    MeanInterPelletInterval

        Meaning:

            Mean raw FED3 interpellet interval at that FR.

        Formula:

            MeanInterPelletInterval = mean(InterPelletInterval) among completed trials at that FR

Important distinction:

    PooledAccuracy uses summed ActivePokes and TotalPokes.
    MeanAccuracy is the average of trial-level Accuracy values.

The demand curve x-axis is FR.


Excel workbook overview
-----------------------

The script saves:

    ClosedEconPR1_EXTRAS.xlsx

Main sheets:

    Trials
        One row per reconstructed interval.

    Trials_DarkLight_Exclusive
        Optional sheet containing only trials where PhaseCrossing == False.

    Summary
        One row per mouse/file.

    Demand_By_FR
        One row per mouse per FR.

    Demand_By_FR_Phase
        Optional one row per mouse per Phase per FR.

    Demand_By_FR_Phase_Excl
        Optional one row per mouse per Phase per FR, excluding phase-crossing trials.


Trial sheet columns
-------------------

The Trials sheet includes:

    Filename
    mouse ID column
    sex column
    group/genotype column
    Trial
    PhaseTrial
    Phase
    StartPhase
    EndPhase
    PhaseCrossing
    Block
    Completed
    StartTime
    EndTime
    Duration_s
    Duration_min
    FR
    ActivePokeSide
    RawActivePokeSide
    LeftPokes
    RightPokes
    ActivePokes
    InactivePokes
    TotalPokes
    Accuracy
    InactivePokePercent
    Vigor
    TotalPokeRate
    InactivePokeRate
    PokesPerPellet
    ActivePokesPerPellet
    RetrievalTime
    InterPelletInterval
    Pellet_Count
    Block_Pellet_Count
    CumulativePellets
    CumulativeActivePokes
    CumulativeTotalPokes


Summary metrics exported as individual Prism sheets
---------------------------------------------------

The script exports one Prism-friendly sheet per summary metric:

    TotalPellets
    CompletedTrials
    TotalPokes
    LeftPokes
    RightPokes
    ActivePokes
    InactivePokes
    Accuracy
    InactivePokePercent
    PokesPerPellet
    ActivePokesPerPellet
    InactivePokesPerPellet
    PelletsPerHour
    ActivePokesPerHour
    TotalSessionTime_h
    FinalFR
    MaxFR
    MeanFR
    MedianFR
    MeanTrialDuration_min
    MeanVigor
    MeanTotalPokeRate
    MeanInactivePokeRate
    MeanInactivePokePercent
    MeanRetrievalTime
    MeanInterPelletInterval
    BlocksCompleted
    IncompleteFinalInterval
    IncompleteFinalPokes


Trial trajectory Prism sheets
-----------------------------

The script exports one Prism-friendly trial trajectory sheet per trial metric:

    FR_Trial
    LeftPokes_Trial
    RightPokes_Trial
    ActivePokes_Trial
    InactivePokes_Trial
    TotalPokes_Trial
    Accuracy_Trial
    InactivePokePercent_Trial
    Vigor_Trial
    TotalPokeRate_Trial
    InactivePokeRate_Trial
    PokesPerPellet_Trial
    ActivePokesPerPellet_Trial
    Duration_min_Trial
    RetrievalTime_Trial
    InterPelletInterval_Trial
    CumulativePellets_Trial
    CumulativeActivePokes_Trial
    CumulativeTotalPokes_Trial

These sheets are wide-format:

    rows = Trial number
    columns = individual mice

For phase-specific sheets, rows use PhaseTrial instead of full-session Trial.


Demand Prism sheets
-------------------

The script exports one Prism-friendly demand sheet per demand metric:

    Demand_Pellets
    Demand_LeftPokes
    Demand_RightPokes
    Demand_ActivePokes
    Demand_InactivePokes
    Demand_TotalPokes
    Demand_TotalDuration_min
    Demand_PokesPerPellet
    Demand_ActivePokesPerPellet
    Demand_InactivePokesPerPellet
    Demand_PooledAccuracy
    Demand_InactivePokePercent
    Demand_PelletsPerMinute
    Demand_MeanAccuracy
    Demand_MeanVigor
    Demand_MeanTotalPokeRate
    Demand_MeanInactivePokeRate
    Demand_MeanInactivePokePercent
    Demand_MeanDuration_min
    Demand_MeanRetrievalTime
    Demand_MeanInterPelletInterval

When dark/light analysis is enabled, phase-specific versions are also exported.


Plot output folders
-------------------

Plots are routed into subfolders under:

    ClosedEconPR1_Plots

Current plot folders:

    All
        General full-session plots.

    Dark
        Dark-phase plots.

    Light
        Light-phase plots.

    Dark_Exclusive
        Dark-phase plots excluding phase-crossing trials.

    Light_Exclusive
        Light-phase plots excluding phase-crossing trials.

    Heatmaps
        Group/sex heatmaps.

    Stacked
        Stacked individual timecourse plots.


Important interpretation notes
------------------------------

1. Vigor is active pokes per minute.

   In this script:

       Vigor = ActivePokes / Duration_min

   It is not total pokes per minute. Total pokes per minute is TotalPokeRate.


2. Pooled percentages and mean percentages are different.

   Example:

       InactivePokePercent = pooled inactive poke percentage from summed pokes
       MeanInactivePokePercent = average of trial-level inactive poke percentages

   Both can be useful, but they answer slightly different questions.


3. Demand metrics use completed pellet trials only.

   Incomplete final work contributes to whole-session poke totals if included,
   but it is not used in Demand_By_FR because there is no earned pellet for that
   unfinished ratio interval.


4. Phase assignment is EndPhase-based.

   This is deliberate. In ClosedEcon PR1, a long interval that starts in Light
   and ends in Dark is assigned to Dark because the pellet was earned in Dark.


5. Exclusive phase outputs are stricter.

   The normal Dark/Light outputs include phase-crossing intervals.
   The exclusive outputs include only intervals that start and end in the same
   phase.


Validation checklist
--------------------

For ClosedEcon PR1, validation is usually simpler than StopSig because completed
trials are pellet-defined.

Recommended spot checks:

    1. Pick a few pellet events in the raw CSV.
       Confirm each becomes one Completed == 1 trial.

    2. For several intervals, manually check:

           LeftPokes
           RightPokes
           ActivePokes
           InactivePokes
           TotalPokes

    3. Confirm active side assignment.

    4. Confirm:

           Accuracy = ActivePokes / TotalPokes * 100
           Vigor = ActivePokes / Duration_min
           TotalPokeRate = TotalPokes / Duration_min

    5. Confirm Demand_By_FR uses only Completed == 1 rows.

    6. If dark/light analysis is used, check a few phase-boundary intervals:

           StartPhase
           EndPhase
           Phase
           PhaseCrossing

    7. Confirm exclusive dark/light sheets exclude PhaseCrossing == True rows.


Plain-language interpretation of key metrics
--------------------------------------------

    TotalPellets
        How many pellets the mouse earned.

    FinalFR
        The FR reached on the last completed pellet trial.

    MaxFR
        Highest FR reached at any completed pellet trial.

    PokesPerPellet
        How many pokes the mouse made per pellet earned.

    ActivePokesPerPellet
        How many correct/active-side pokes were made per pellet earned.

    InactivePokesPerPellet
        How many inactive-side pokes were made per pellet earned.

    Accuracy
        Percent of pokes made on the active side.

    InactivePokePercent
        Percent of pokes made on the inactive side.

    Vigor
        Active-side response rate in active pokes per minute.

    TotalPokeRate
        Overall response rate in total pokes per minute.

    InactivePokeRate
        Inactive-side response rate in inactive pokes per minute.

    PelletsPerHour
        Whole-session pellet earning rate.

    PelletsPerMinute
        FR-level pellet earning rate in demand outputs.


End of README.
