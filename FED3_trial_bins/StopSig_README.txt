StopSig Trialsbin README
========================

Purpose of this script
----------------------

This script analyzes FED3 StopSig data by reconstructing individual Regular
and Stop trials from the raw event log. It converts each detected trial start
into one trial-level row, identifies the first recognized terminal event,
classifies the trial outcome, calculates timing and sequential-context
variables, and produces summary, peri-stop, PCA, Prism-friendly, and graphical
outputs.

The main outputs are:

    1. A reconstructed trial-level dataset.
    2. One-row-per-file/mouse summary metrics.
    3. Trial-type and optional dark/light phase summaries.
    4. Rolling-accuracy and latency trajectories.
    5. Peri-stop datasets and plots aligned around Stop trials.
    6. PCA outputs when enough mice and usable features are available.
    7. Diagnostic validation tables and stacked trial rasters.


Core task terminology
---------------------

The script recognizes two trial-start events:

    >Left_Regular_trial
        Starts a Regular trial.

    >Left_Stop_trial
        Starts a Stop trial.

The script recognizes four completed terminal events:

    Right_Regular_(correct)
        RegularCorrect
        Sequence label: Regular LRP
        Correct = 1
        Response type = RightPoke

    NoPoke_Regular_(incorrect)
        RegularIncorrect
        Sequence label: Regular LN
        Correct = 0
        Response type = Withhold

    NoPoke_STOP_(correct)
        StopCorrect
        Sequence label: Stop LNP
        Correct = 1
        Response type = Withhold

    Right_STOP_(incorrect)
        StopIncorrect
        Sequence label: Stop LR
        Correct = 0
        Response type = RightPoke

The shorthand sequence labels can be read conceptually as:

    L = left-poke trial initiation
    R = right-poke response
    N = no right poke / withholding
    P = pellet delivery

Therefore:

    Regular LRP = initiated Regular trial, right-poke response, pellet
    Regular LN  = initiated Regular trial, no response, no pellet expected
    Stop LNP    = initiated Stop trial, successful withholding, pellet
    Stop LR     = initiated Stop trial, failed inhibition/right response

"Correct" is task-contingent. A right poke is correct on a Regular trial but
incorrect on a Stop trial. Withholding is incorrect on a Regular trial but
correct on a Stop trial.


Input files and required columns
--------------------------------

The script expects raw FED3 StopSig CSV files containing these columns:

    MM:DD:YYYY hh:mm:ss
    Event
    Left_Poke_Count
    Right_Poke_Count
    Pellet_Count

If any required column is absent, that file is skipped and its error is
recorded.

The following columns are used when present:

    Block_Pellet_Count
    Retrieval_Time
    InterPelletInterval
    Poke_Time
    FR

Numeric columns are converted with invalid values changed to blank/NaN.
Event text is stripped of surrounding whitespace before matching.

RawCSVRow is created as the physical CSV row number, starting at 2 because row
1 is assumed to contain the column headings.


Metadata input
--------------

The user can load an existing Excel metadata file or enter metadata through
the GUI. A newly entered file is saved as:

    StopSig_Metadata.xlsx

The first column must be Filename. The first three non-Filename columns are
interpreted, in order, as:

    1. mouse identifier
    2. sex
    3. group/genotype

The literal column names can be customized, but their order matters. Each
Filename value must exactly match one of the selected CSV filenames. Leading
and trailing whitespace is removed from text loaded from an existing metadata
file.


How trials are reconstructed
----------------------------

Each recognized trial-start event creates one trial.

For every start event, the script defines an interval beginning on that start
row and ending immediately before the next recognized start event. For the
last trial, the interval extends to the end of the file.

Within that interval, the script searches for recognized terminal events. The
first recognized terminal event is used to classify the trial.

If one or more recognized terminal events are present:

    Completed = 1
    TerminalEvent = first recognized terminal event
    TerminalEventCount = total recognized terminal events in the interval

If no recognized terminal event is present:

    Completed = 0
    Outcome = Incomplete
    Sequence = Incomplete
    Correct = blank/NaN
    EndTime = timestamp of the last valid row in the interval

This means TotalTrials is the number of detected trial starts, not merely the
number of completed terminal outcomes.


Trial-type validation
---------------------

The start event independently specifies Regular or Stop, and the terminal
event also implies Regular or Stop. The script compares these values:

    TrialTypeMismatch = 1
        Start-derived trial type and terminal-derived trial type disagree.

    TrialTypeMismatch = 0
        They agree.

    TrialTypeMismatch = blank
        The trial is incomplete and has no terminal-derived trial type.

TerminalEventCount greater than 1 is also retained as a diagnostic. The first
terminal event still determines the outcome, but MultipleTerminalTrials in the
Summary counts intervals containing more than one recognized terminal event.


Pellet confirmation and reward validation
-----------------------------------------

After a completed terminal event is found, the script searches from that
terminal row to the end of the current trial interval for a Pellet event.

    PelletConfirmed = 1 if at least one Pellet event is found
    PelletConfirmed = 0 otherwise

The first detected Pellet event supplies PelletTime and pellet-related raw
values.

The script assumes that correct completed trials should be rewarded and
incorrect completed trials should not be rewarded:

    PelletExpected = Correct

Therefore:

    RewardMismatch = 1 if PelletConfirmed differs from PelletExpected
    RewardMismatch = 0 if they agree
    RewardMismatch = blank for incomplete trials

Examples:

    Correct trial with pellet       -> no mismatch
    Correct trial without pellet    -> mismatch
    Incorrect trial without pellet  -> no mismatch
    Incorrect trial with pellet     -> mismatch

RewardMismatch is a quality-control flag. It does not change Correct or the
trial outcome.


Latency calculations
--------------------

Terminal latency
~~~~~~~~~~~~~~~~

TerminalLatency_s is the time from the trial-start event to the first terminal
event that completes the trial.

In plain language:

    How long did it take for the animal to either respond or withhold after the
    left trial-start event?

The trial-start events are:

    >Left_Regular_trial
    >Left_Stop_trial

The terminal events are:

    Right_Regular_(correct)
    NoPoke_Regular_(incorrect)
    NoPoke_STOP_(correct)
    Right_STOP_(incorrect)

The script first attempts to calculate terminal latency from the raw
Block_Pellet_Count column:


    EventMillisLatency_s =
        (terminal Block_Pellet_Count - start Block_Pellet_Count) / 1000

This candidate is accepted only if it lies from 0 to 60 seconds inclusive.
Despite the raw column name, the script is treating the difference as a
millisecond-style event timer when it passes this validity check.

If that value is missing or invalid, the script falls back to:

    TimestampLatency_s = terminal timestamp - start timestamp

The final selected value is:

    TerminalLatency_s =
        EventMillisLatency_s, if valid
        otherwise TimestampLatency_s

LatencySource records which value was selected:

    Block_Pellet_Count
    Timestamp

Important note:

    In this StopSig CSV format, Block_Pellet_Count appears to behave like a
    millisecond event clock even though the column name says pellet count. The
    script uses only the difference between start and terminal values, and only
    accepts it when it gives a plausible 0-60 second latency.


Why the latency columns and plot axes use seconds, not milliseconds
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Several raw values in the CSV can make this confusing, especially
Block_Pellet_Count.

The important distinction is:

    Raw Block_Pellet_Count values
        Appear to be millisecond-style event-clock values.

    Exported latency columns ending in _s
        Are converted to seconds.

    Plot axes labeled "seconds"
        Are plotting the converted _s columns, so the axis label is correct.

For example:

    start Block_Pellet_Count    = 340625
    terminal Block_Pellet_Count = 344096

    raw difference = 344096 - 340625
                   = 3471

If this raw difference is interpreted as milliseconds:

    3471 ms / 1000 = 3.471 seconds

The script stores:

    EventMillisLatency_s = 3.471

and, if this value passes the validity check, also uses it as:

    TerminalLatency_s = 3.471

So even though the source difference looks like milliseconds, the exported value
is already divided by 1000 and is therefore in seconds.

The same rule applies to:

    RightResponseLatency_s
    WithholdDuration_s
    PelletDeliveryLatency_s
    InterTrialInterval_s
    AvailableInitiationLatency_s
    RegularCorrectRT_s

The suffix "_s" means seconds.

The main exception is:

    StopSignalDelay_ms

This is deliberately stored in milliseconds because stop-signal delay is a task
setting conventionally expressed in ms.


Response-specific latency columns
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    RightResponseLatency_s
        TerminalLatency_s for RightPoke outcomes:

            Regular LRP
            Stop LR

        Formula:

            RightResponseLatency_s = TerminalLatency_s

        only when ResponseType == RightPoke.

        Otherwise this column is blank / NaN.

        This includes Regular LRP and Stop LR trials.

    WithholdDuration_s
        TerminalLatency_s for Withhold outcomes:

            Regular LN
            Stop LNP

        Formula:

            WithholdDuration_s = TerminalLatency_s

        only when ResponseType == Withhold.

        Otherwise this column is blank / NaN.

        This includes Regular LN and Stop LNP trials.

    PelletDeliveryLatency_s
        Time from the terminal behavioral event to the pellet event.

        Formula:

            PelletDeliveryLatency_s = PelletTime - EndTime

        Defined only when a Pellet event was confirmed and both timestamps
        are available.

    InterTrialInterval_s
        Time from the previous trial terminal event to the current trial-start
        event.

        Formula:

            InterTrialInterval_s =
                current StartTime - previous EndTime

        The first reconstructed trial has no previous interval.

Task timing settings
~~~~~~~~~~~~~~~~~~~~

The script records task timing settings on each trial:

    StopSignalDelay_ms
    ResponseWindow_s
    RegularOmissionTimeout_s
    StopErrorNoise_s
    StopErrorTimeout_s
    StopErrorLockout_s

In the original script version, StopSignalDelay_ms = 300 and ResponseWindow_s =
4 were fixed values recorded on each trial. They were not estimated from the
event timestamps.

In the configurable-timing version of the script, the GUI asks the user for
these values and uses the entered values in the output.

The timeout settings matter specifically for AvailableInitiationLatency_s,
because the script needs to know when the animal was allowed to initiate the
next trial after an error or timeout.


Next-trial initiation latency
-----------------------------

AvailableInitiationLatency_s asks:

    After the previous trial was over, and after any reward period, timeout, or
    stop-error lockout had ended, how long did the animal wait before initiating
    the current trial?

In plainer terms:

    It is the animal's voluntary waiting time to start the next trial, after the
    task should have made the next trial available.

This is different from InterTrialInterval_s.

    InterTrialInterval_s starts counting immediately after the previous terminal
    event.

    AvailableInitiationLatency_s starts counting only after the task-imposed
    unavailable period is over.

So for timeout/error trials, AvailableInitiationLatency_s is intended to remove
the forced waiting period and keep the animal-controlled part of the delay.

This is why peri-stop "Next-Trial Initiation Latency (seconds)" plots should be
read as adjusted initiation latency, not raw time since the previous trial ended.
For timeout/error trials, the task-imposed timeout or lockout is accounted for
before AvailableInitiationLatency_s is calculated.

The availability time is inferred from the previous sequence:

    Previous Regular LRP or Stop LNP
        The previous trial was rewarded.

        AvailabilityTime = previous PelletTime

        If PelletTime is missing, previous EndTime is used as a fallback.

    Previous Regular LN
        The previous trial was a regular no-poke error.

        AvailabilityTime =
            previous EndTime + RegularOmissionTimeout_s

        Default:

            previous EndTime + 30 seconds

    Previous Stop LR
        The previous trial was a stop-trial right-poke error.

        AvailabilityTime =
            previous EndTime + StopErrorNoise_s + StopErrorTimeout_s

        Default:

            previous EndTime + 2 seconds noise + 90 seconds timeout

        Therefore:

            default StopErrorLockout_s = 2 + 90 = 92 seconds

    Other previous outcome
        AvailabilityTime = previous EndTime

The raw value is:

    RawAvailableInitiationLatency_s =
        current StartTime - AvailabilityTime

The analysis value is clipped at zero:

    AvailableInitiationLatency_s = max(raw latency, 0)

Thus, a negative raw latency is retained for diagnosis but contributes as zero
to the analyzed initiation-latency metric. AvailabilityBasis records which
rule was used.

Worked examples:

    Example after Regular LRP or Stop LNP

        Previous PelletTime = 13:46:05
        Current StartTime   = 13:47:08

        AvailableInitiationLatency_s =
            13:47:08 - 13:46:05
            = 63 seconds

    Example after Regular LN with a 30-second timeout

        Previous EndTime  = 13:45:26
        Timeout           = 30 seconds
        AvailabilityTime  = 13:45:56
        Current StartTime = 13:45:58

        RawAvailableInitiationLatency_s =
            13:45:58 - 13:45:56
            = 2 seconds

        AvailableInitiationLatency_s = 2 seconds

    Example after Stop LR with 2 seconds noise + 90 seconds timeout

        Previous EndTime  = 15:16:33
        Noise             = 2 seconds
        Timeout           = 90 seconds
        AvailabilityTime  = 15:18:05
        Current StartTime = 15:18:54

        RawAvailableInitiationLatency_s =
            15:18:54 - 15:18:05
            = 49 seconds

        AvailableInitiationLatency_s = 49 seconds

Important note about inference:

    The raw CSV does not explicitly store the programmed timeout durations as
    separate settings columns.

    Timeout poke events such as RightinTimeout and LeftinTimeOut show that the
    animal poked during a timeout, and the delay between a terminal event and
    the next trial start can suggest the minimum lockout duration. For example,
    in the validation CSV, the shortest Regular LN-to-next-start gap is about
    30 seconds and the shortest Stop LR-to-next-start gap is about 92 seconds.

    However, those gaps cannot perfectly recover the task settings because the
    animal may wait longer than the required timeout before starting the next
    trial.

    Therefore, custom timeout/noise values should be entered by the user rather
    than inferred automatically from the CSV.

The script also calculates:

    CumulativeAvailableInitiationLatency_s
        Running sum of available initiation latencies across the session.

    CumulativeMeanAvailableInitiationLatency_s
        Running sum divided by the number of nonmissing latency observations.

    PhaseCumulativeAvailableInitiationLatency_s
        Running sum calculated separately within each Phase.

    PhaseCumulativeMeanAvailableInitiationLatency_s
        Phase-specific running sum divided by the phase-specific count of
        valid latency observations.


Sequential-context columns
--------------------------

The Trials sheet retains several columns describing the immediately preceding
trial:

    PreviousTrialType
    PreviousOutcome
    PreviousSequence
    PreviousCorrect

OutcomeStreakLength is the number of consecutive trials with the same Correct
value. An incomplete trial resets the streak.

PrecedingRegularRunLength is populated on Stop trials. It counts the number of
consecutive Regular trials since the preceding Stop trial. The counter resets
whenever a Stop trial is encountered.


Dark/light phase assignment
---------------------------

If dark/light analysis is enabled, the user enters the light start and light
end times. The defaults are:

    Light start = 07:00
    Light end   = 19:00

The phase logic supports both ordinary daytime intervals and light intervals
that cross midnight.

Each trial receives:

    StartPhase
        Phase at StartTime.

    EndPhase
        Phase at EndTime/terminal time.

    PhaseCrossing
        TRUE if StartPhase and EndPhase differ.

    Phase
        Equal to EndPhase.

Therefore, a trial is assigned to the phase in which its terminal event or
incomplete endpoint occurred. Phase-crossing trials are retained rather than
excluded.

If dark/light analysis is disabled:

    StartPhase = All
    EndPhase = All
    Phase = All
    PhaseCrossing = FALSE


Trial indices
-------------

The script exports several trial-number columns:

    Trial
        Trial-start sequence across the full session.

    TypeTrial
        Trial number calculated separately within Regular and Stop trials.

    PhaseTrial
        Trial number calculated separately within each phase.

    PhaseTypeTrial
        Trial number calculated separately within each Phase x TrialType
        combination.

When phase analysis is disabled, PhaseTrial equals Trial and PhaseTypeTrial
equals TypeTrial.


Rolling and cumulative accuracy
-------------------------------

The user selects a rolling window, with a default of 20 trials.

For a binary Correct series:

    RollingCorrectCount = sum of valid Correct values in the window
    RollingTrialCount = number of nonmissing Correct values in the window
    RollingAccuracy = RollingCorrectCount / RollingTrialCount * 100

The first rows use all available observations because min_periods = 1.
Incomplete trials have Correct = blank and do not contribute to the rolling
numerator or denominator, although they remain rows in the full Trial index.

The script calculates:

    RollingAccuracy
        Rolling accuracy across all trial types, indexed by Trial.

    TypeRollingAccuracy
        Rolling accuracy separately within Regular and Stop trials, indexed
        by TypeTrial.

    PhaseRollingAccuracy
        Rolling accuracy separately within each phase.

    PhaseTypeRollingAccuracy
        Rolling accuracy separately within each Phase x TrialType group.

The corresponding correct-count and trial-count columns are also exported.

Cumulative accuracy is calculated across the full session:

    CumulativeCorrect = cumulative sum of Correct, treating blanks as zero
    CumulativeCompletedTrials = cumulative count of nonmissing Correct values
    CumulativeAccuracy =
        CumulativeCorrect / CumulativeCompletedTrials * 100

CumulativePellets is the running sum of PelletConfirmed.


Core summary metric formulas
----------------------------

Trial counts
~~~~~~~~~~~~

    TotalTrials
        Number of detected trial starts, including incomplete trials.
        Displayed in the main Summary sheet as Trial Starts.

    CompletedTrials
        Number of rows where Completed = 1.
        Displayed as Total Trials.

    IncompleteTrials
        Number of rows where Completed = 0.

    RegularTrials
        Number of completed Regular trials.

    StopTrials
        Number of completed Stop trials.

    StopTrialPercent = StopTrials / CompletedTrials * 100

Accuracy metrics
~~~~~~~~~~~~~~~~

    OverallAccuracy =
        sum(Correct across completed trials) / CompletedTrials * 100

    RegularAccuracy =
        correct Regular trials / completed Regular trials * 100

    StopAccuracy =
        correct Stop trials / completed Stop trials * 100

    BalancedAccuracy = mean(RegularAccuracy, StopAccuracy)

BalancedAccuracy gives Regular and Stop performance equal weight regardless of
how frequent each trial type was. It is therefore different from
OverallAccuracy when Regular and Stop trial counts are unequal.

    RegularOmissionRate = 100 - RegularAccuracy

    StopFailureRate = 100 - StopAccuracy

In this task, RegularOmissionRate is the percentage of completed Regular trials
ending in Regular LN. StopFailureRate is the percentage of completed Stop
trials ending in Stop LR.

Quality-control metrics
~~~~~~~~~~~~~~~~~~~~~~~

    PelletsConfirmed
        Sum of PelletConfirmed across reconstructed trials.

    RewardMismatches
        Number of completed trials where observed pellet presence disagreed
        with Correct/PelletExpected.

    TrialTypeMismatches
        Number of completed trials where start-derived and terminal-derived
        trial types disagreed.

    MultipleTerminalTrials
        Number of reconstructed intervals containing more than one recognized
        terminal event.

    RightNoLeftEvents
        Count of raw Right_no_left events.

    LeftTimeoutEvents
        Count of raw LeftinTimeOut events.

    RightTimeoutEvents
        Count of raw RightinTimeout events.

    SessionDuration_h =
        (latest EndTime - earliest StartTime) / 3600

Latency summary metrics
~~~~~~~~~~~~~~~~~~~~~~~

These metrics are calculated in the Summary sheet. Each value summarizes one
trial-level latency column across the relevant subset of completed trials. 
Below, "RT" stands for "Response Time" or "Response Latency."

MeanRegularCorrectRT_s
    Meaning:
        Average right-poke response latency on correct Regular trials.

    Trial subset:
        Outcome == RegularCorrect
        Sequence == Regular LRP

    Trial-level source column:
        RightResponseLatency_s

    Formula:
        MeanRegularCorrectRT_s =
            mean(RightResponseLatency_s for Regular LRP trials)


MedianRegularCorrectRT_s
    Meaning:
        Median right-poke response latency on correct Regular trials.

    Trial subset:
        Outcome == RegularCorrect
        Sequence == Regular LRP

    Formula:
        MedianRegularCorrectRT_s =
            median(RightResponseLatency_s for Regular LRP trials)


MeanStopFailureRT_s
    Meaning:
        Average right-poke response latency on failed Stop trials.

    Trial subset:
        Outcome == StopIncorrect
        Sequence == Stop LR

    Trial-level source column:
        RightResponseLatency_s

    Formula:
        MeanStopFailureRT_s =
            mean(RightResponseLatency_s for Stop LR trials)


MedianStopFailureRT_s
    Meaning:
        Median right-poke response latency on failed Stop trials.

    Trial subset:
        Outcome == StopIncorrect
        Sequence == Stop LR

    Formula:
        MedianStopFailureRT_s =
            median(RightResponseLatency_s for Stop LR trials)


MeanCorrectWithhold_s
    Meaning:
        Average successful withholding duration on correct Stop trials.

    Trial subset:
        Outcome == StopCorrect
        Sequence == Stop LNP

    Trial-level source column:
        WithholdDuration_s

    Formula:
        MeanCorrectWithhold_s =
            mean(WithholdDuration_s for Stop LNP trials)

    Important note:
        This is not a reaction time in the usual right-poke sense.
        It is the duration from Stop trial start to the NoPoke_STOP terminal
        event, i.e. how long the animal withheld until the trial resolved.


MeanInterTrialInterval_s
    Meaning:
        Average time from the previous trial's terminal event to the current
        trial's start event.

    Trial-level source column:
        InterTrialInterval_s

    Formula:
        MeanInterTrialInterval_s =
            mean(InterTrialInterval_s across reconstructed trials with a
            nonmissing value)


MedianInterTrialInterval_s
    Meaning:
        Median time from the previous terminal event to the current trial start.

    Formula:
        MedianInterTrialInterval_s =
            median(InterTrialInterval_s across reconstructed trials with a
            nonmissing value)


MeanAvailableInitiationLatency_s
    Meaning:
        Average animal-controlled waiting time to initiate the next trial after
        the previous trial was expected to become available again.

    Trial-level source column:
        AvailableInitiationLatency_s

    Formula:
        MeanAvailableInitiationLatency_s =
            mean(AvailableInitiationLatency_s across trials with a nonmissing
            value)


MedianAvailableInitiationLatency_s
    Meaning:
        Median animal-controlled waiting time to initiate the next trial after
        task-imposed reward/timeout/lockout periods were accounted for.

    Formula:
        MedianAvailableInitiationLatency_s =
            median(AvailableInitiationLatency_s across trials with a nonmissing
            value)

Main conceptual distinction:

RightResponseLatency_s
    Used when the animal makes a right poke.
    Applies to Regular LRP and Stop LR.

WithholdDuration_s
    Used when the animal withholds / makes no right poke.
    Applies to Regular LN and Stop LNP.

InterTrialInterval_s
    Raw gap from previous trial ending to next trial starting.

AvailableInitiationLatency_s
    Adjusted gap after subtracting task-imposed unavailable time,
    such as timeout or stop-error lockout.


Sequence count, latency, and percentage metrics
-----------------------------------------------

The Summary includes direct counts for:

    Regular LRP count
    Regular LN count
    Stop LNP count
    Stop LR count

It also includes sequence-specific latency totals and means:

    Regular LRP latency LR sum (secs)
    Regular LRP latency LR avg (secs)
        RightResponseLatency_s for Regular LRP trials.

    Regular LRP latency RP sum (secs)
    Regular LRP latency RP avg (secs)
        PelletDeliveryLatency_s for Regular LRP trials.

    Stop LNP latency NP sum (secs)
    Stop LNP latency NP avg (secs)
        PelletDeliveryLatency_s for Stop LNP trials.

    Stop LR latency LR sum (secs)
    Stop LR latency LR avg (secs)
        RightResponseLatency_s for Stop LR trials.

Sequence percentages use several different denominators:

    Regular LRP/total regular (%) = Regular LRP / all Regular trials * 100
    Regular LN/total regular (%)  = Regular LN / all Regular trials * 100

    Stop LNP/total stop (%) = Stop LNP / all Stop trials * 100
    Stop LR/total stop (%)  = Stop LR / all Stop trials * 100

    Regular LRP/total trials (%) = Regular LRP / all completed trials * 100
    Regular LN/total trials (%)  = Regular LN / all completed trials * 100
    Regular trials/total trials (%) = all Regular / all completed * 100

    Stop LNP/total trials (%) = Stop LNP / all completed trials * 100
    Stop LR/total trials (%)  = Stop LR / all completed trials * 100
    Stop trials/total trials (%) = all Stop / all completed * 100

    LRP/total pellets (%) = Regular LRP / confirmed pellets * 100
    LNP/total pellets (%) = Stop LNP / confirmed pellets * 100

The pellet-denominator percentages are validation-style metrics. If pellet
delivery and correct outcomes match perfectly, Regular LRP plus Stop LNP should
account for the confirmed pellets. Reward mismatches can make these values less
straightforward.


Post-error and post-stop adjustment metrics
-------------------------------------------

These metrics ask whether behavior on a Regular trial changes depending on what
happened on the immediately preceding reconstructed trial.

The basic structure is:

    previous trial = trial N - 1
    current trial  = trial N

The current trial must be a completed Regular trial for these adjustment
analyses.

The previous trial is used only to classify what came before the current Regular
trial.

Important current-trial subsets:

    Current completed Regular trials
        TrialType == Regular
        Completed == 1

    Current RegularCorrect trials
        TrialType == Regular
        Outcome == RegularCorrect
        Sequence == Regular LRP

Current RegularCorrect trials are used for response-latency comparisons because
RightResponseLatency_s exists for right-poke responses. Regular LN trials are
not used in the response-latency means because they are no-poke/withhold trials,
not right-poke response trials.

Accuracy comparisons use all completed current Regular trials, because both
Regular LRP and Regular LN are needed to calculate Regular accuracy.

Post-error slowing
~~~~~~~~~~~~~~~~~~

Question:

    Are correct Regular right-poke responses slower after an error than after a
    correct trial?

Previous-trial groups:

    Previous incorrect trial:
        PreviousCorrect == 0

    Previous correct trial:
        PreviousCorrect == 1

Current-trial filter:

    Outcome == RegularCorrect

Trial-level source column:

    RightResponseLatency_s

Intermediate means:

    MeanRT_after_error =
        mean(RightResponseLatency_s for current RegularCorrect trials
             where PreviousCorrect == 0)

    MeanRT_after_correct =
        mean(RightResponseLatency_s for current RegularCorrect trials
             where PreviousCorrect == 1)

Final formula:

    PostErrorSlowing_s =
        MeanRT_after_error - MeanRT_after_correct

Interpretation:

    Positive value:
        Correct Regular responses were slower after errors.

    Negative value:
        Correct Regular responses were faster after errors.

    Near zero:
        Little or no difference in correct Regular response latency after errors
        versus after correct trials.

Important note:

    This metric does not ask whether the current trial was correct more often
    after an error. It only looks at right-poke response latency on current
    RegularCorrect trials.

General post-stop effects
~~~~~~~~~~~~~~~~~~~~~~~~~

These metrics compare current Regular trials that followed a Stop trial versus
current Regular trials that followed a Regular trial.

Previous-trial groups:

    After Stop:
        PreviousTrialType == Stop

    After Regular:
        PreviousTrialType == Regular


PostStopRegularAccuracyChange
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Question:

    Is Regular accuracy different after Stop trials compared with after Regular
    trials?

Current-trial filter:

    TrialType == Regular
    Completed == 1

Intermediate accuracies:

    RegularAccuracy_after_stop =
        mean(Correct for current completed Regular trials
             where PreviousTrialType == Stop) * 100

    RegularAccuracy_after_regular =
        mean(Correct for current completed Regular trials
             where PreviousTrialType == Regular) * 100

Because Correct is coded as:

    RegularCorrect / Regular LRP = 1
    RegularIncorrect / Regular LN = 0

the mean of Correct multiplied by 100 gives percent accuracy.

Final formula:

    PostStopRegularAccuracyChange =
        RegularAccuracy_after_stop - RegularAccuracy_after_regular

Interpretation:

    Positive value:
        Regular accuracy was higher after Stop trials.

    Negative value:
        Regular accuracy was lower after Stop trials.


PostStopRegularRTChange_s
~~~~~~~~~~~~~~~~~~~~~~~~~

Question:

    Are correct Regular right-poke responses slower or faster after Stop trials
    compared with after Regular trials?

Current-trial filter:

    Outcome == RegularCorrect

Trial-level source column:

    RightResponseLatency_s

Intermediate means:

    MeanRT_after_stop =
        mean(RightResponseLatency_s for current RegularCorrect trials
             where PreviousTrialType == Stop)

    MeanRT_after_regular =
        mean(RightResponseLatency_s for current RegularCorrect trials
             where PreviousTrialType == Regular)

Final formula:

    PostStopRegularRTChange_s =
        MeanRT_after_stop - MeanRT_after_regular

Interpretation:

    Positive value:
        Correct Regular responses were slower after Stop trials.

    Negative value:
        Correct Regular responses were faster after Stop trials.


PostStopInitiationChange_s
~~~~~~~~~~~~~~~~~~~~~~~~~~

Question:

    Does the animal take longer to initiate the next Regular trial after a Stop
    trial compared with after a Regular trial?

Current-trial filter:

    TrialType == Regular
    Completed == 1

Trial-level source column:

    AvailableInitiationLatency_s

Intermediate means:

    MeanInitiation_after_stop =
        mean(AvailableInitiationLatency_s for current completed Regular trials
             where PreviousTrialType == Stop)

    MeanInitiation_after_regular =
        mean(AvailableInitiationLatency_s for current completed Regular trials
             where PreviousTrialType == Regular)

Final formula:

    PostStopInitiationChange_s =
        MeanInitiation_after_stop - MeanInitiation_after_regular

Interpretation:

    Positive value:
        The animal waited longer to initiate Regular trials after Stop trials.

    Negative value:
        The animal initiated Regular trials sooner after Stop trials.

Stop-error versus Stop-success effects
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These metrics compare current Regular trials after failed Stop trials versus
current Regular trials after successful Stop trials.

Previous-trial groups:

    After Stop Error:
        PreviousSequence == Stop LR

    After Stop Success:
        PreviousSequence == Stop LNP


PostStopErrorAccuracyChange
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Question:

    Is Regular accuracy different after a failed Stop trial compared with after a
    successful Stop trial?

Current-trial filter:

    TrialType == Regular
    Completed == 1

Intermediate accuracies:

    RegularAccuracy_after_stop_error =
        mean(Correct for current completed Regular trials
             where PreviousSequence == Stop LR) * 100

    RegularAccuracy_after_stop_success =
        mean(Correct for current completed Regular trials
             where PreviousSequence == Stop LNP) * 100

Final formula:

    PostStopErrorAccuracyChange =
        RegularAccuracy_after_stop_error
        - RegularAccuracy_after_stop_success

Interpretation:

    Positive value:
        Regular accuracy was higher after failed Stop trials than after
        successful Stop trials.

    Negative value:
        Regular accuracy was lower after failed Stop trials than after
        successful Stop trials.


PostStopErrorRTChange_s
~~~~~~~~~~~~~~~~~~~~~~~

Question:

    Are correct Regular responses slower or faster after failed Stop trials
    compared with after successful Stop trials?

Current-trial filter:

    Outcome == RegularCorrect

Trial-level source column:

    RightResponseLatency_s

Intermediate means:

    MeanRT_after_stop_error =
        mean(RightResponseLatency_s for current RegularCorrect trials
             where PreviousSequence == Stop LR)

    MeanRT_after_stop_success =
        mean(RightResponseLatency_s for current RegularCorrect trials
             where PreviousSequence == Stop LNP)

Final formula:

    PostStopErrorRTChange_s =
        MeanRT_after_stop_error - MeanRT_after_stop_success

Interpretation:

    Positive value:
        Correct Regular responses were slower after failed Stop trials than after
        successful Stop trials.

    Negative value:
        Correct Regular responses were faster after failed Stop trials than after
        successful Stop trials.


PostStopErrorInitiationChange_s
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Question:

    Does the animal take longer to initiate a Regular trial after a failed Stop
    trial compared with after a successful Stop trial?

Current-trial filter:

    TrialType == Regular
    Completed == 1

Trial-level source column:

    AvailableInitiationLatency_s

Intermediate means:

    MeanInitiation_after_stop_error =
        mean(AvailableInitiationLatency_s for current completed Regular trials
             where PreviousSequence == Stop LR)

    MeanInitiation_after_stop_success =
        mean(AvailableInitiationLatency_s for current completed Regular trials
             where PreviousSequence == Stop LNP)

Final formula:

    PostStopErrorInitiationChange_s =
        MeanInitiation_after_stop_error
        - MeanInitiation_after_stop_success

Positive latency changes indicate longer/slower latencies in the first-named
condition. Positive accuracy changes indicate higher accuracy in the
first-named condition.

The Summary also reports the opportunity counts:

    RegularTrialsAfterRegular
    RegularTrialsAfterStop
    RegularTrialsAfterStopSuccess
    RegularTrialsAfterStopError

These counts should be checked before interpreting differences. A metric is
blank/NaN when one of the required comparison means cannot be calculated.


Trial-type and phase summaries
------------------------------

TrialType_Summary contains one row per file/mouse and trial type. It reports:

    Trials
        All reconstructed rows of that type, including incomplete rows.

    CompletedTrials
    CorrectTrials
    Accuracy
    RightPokeTrials
    WithholdTrials
    MeanTerminalLatency_s
    MedianTerminalLatency_s

If phase splitting is enabled, Phase_Summary recalculates the main summary
metrics separately for rows assigned to Dark and Light.

Important phase-summary details:

    - Phase is based on each trial's EndPhase.
    - PreviousTrialType, PreviousSequence, and PreviousCorrect were calculated
      in the full trial sequence before phase filtering. A phase-specific
      adjustment metric may therefore use a previous trial from the other
      phase.
    - Raw diagnostic event counts are not divided by phase. The phase summary
      passes an empty event-count series, so Right_no_left and timeout counts
      in Phase_Summary are zero and should not be interpreted as phase-specific
      raw-event totals.
    - SessionDuration_h within a phase is the time from the earliest start to
      latest end among that phase's rows. If a recording spans repeated phases,
      this is not the summed exposure time spent only in that phase.


Peri-stop analysis
------------------

The user selects a peri-stop window, with a default of 10 trials before and 10
trials after each Stop trial.

Purpose
~~~~~~~

Peri-stop analysis asks:

    What happens to Regular-trial performance and initiation latency in the
    trials immediately before and after Stop trials?

This is an event-aligned analysis. The event being aligned to is always a Stop
trial.

Important terminology:

    Anchor trial
        The Stop trial placed at RelativeTrial = 0.

    Surrounding trial
        A reconstructed trial before, at, or after the anchor.

    Metric
        The value sampled from each surrounding trial, such as Regular accuracy,
        Regular LRP response latency, or next-trial initiation latency.

So, in a plot title such as:

    Regular LRP L to R Latency Around All Stop Trials

the anchor is not Regular LRP. The anchor is "All Stop Trials." The y-axis is
Regular LRP L-to-R latency measured from surrounding trials around those Stop
anchors.


Anchor selection
~~~~~~~~~~~~~~~~

Every reconstructed row whose TrialType is Stop is treated as an anchor. For
each Stop anchor, the script extracts surrounding reconstructed trials from:

    RelativeTrial = -peri_window ... 0 ... +peri_window

    RelativeTrial = 0 is the Stop anchor itself.
    Negative values occur before the Stop trial.
    Positive values occur after the Stop trial.

Example with peri_window = 3:

    RelativeTrial = -3
        The third reconstructed trial before the Stop anchor.

    RelativeTrial = -2
        The second reconstructed trial before the Stop anchor.

    RelativeTrial = -1
        The trial immediately before the Stop anchor.

    RelativeTrial = 0
        The Stop anchor itself.

    RelativeTrial = +1
        The trial immediately after the Stop anchor.

    RelativeTrial = +2
        The second reconstructed trial after the Stop anchor.

    RelativeTrial = +3
        The third reconstructed trial after the Stop anchor.

The window is based on reconstructed trial number, not clock time. If another
Stop trial occurs within the peri-stop window, it remains in the window as a
surrounding trial.


Anchors are categorized as:

    Stop Success = anchor Sequence is Stop LNP
    Stop Error   = any other Stop anchor sequence

In normal completed data, Stop Error corresponds to Stop LR. Under the current
implementation, an incomplete Stop anchor is also placed in Stop Error because
its sequence is not Stop LNP. This should be kept in mind when incomplete Stop
trials are present.

The anchor's Phase is assigned to every peri-stop row for that anchor. Thus a
Dark peri-stop plot means the Stop anchor occurred in Dark; surrounding trials
can cross into another phase.


Peri-stop output families
~~~~~~~~~~~~~~~~~~~~~~~~~

The script creates three anchor groups:

    AllStop
        All Stop anchors.

    StopSuccess
        Only Stop anchors whose sequence is Stop LNP.

    StopError
        Only Stop anchors whose category is Stop Error.
        In normal completed data, this corresponds to Stop LR.

For each anchor group, the script exports and plots three metrics:

    RegularAccuracy
        Regular-trial accuracy around the Stop anchor.

    RegularCorrectRT_s
        Regular LRP L-to-R response latency around the Stop anchor.

    AvailableInitiationLatency_s
        Next-trial initiation latency around the Stop anchor.

This creates plot/output concepts such as:

    Regular-Trial Accuracy Around All Stop Trials

        Anchor group:
            all Stop trials

        Y-axis metric:
            RegularAccuracy from surrounding Regular trials


    Regular LRP L to R Latency Around Successful Stop LNP Trials

        Anchor group:
            Stop Success anchors only

        Y-axis metric:
            RegularCorrectRT_s from surrounding RegularCorrect / Regular LRP
            trials


    Next-Trial Initiation Latency Around Failed Stop LR Trials

        Anchor group:
            Stop Error anchors only

        Y-axis metric:
            AvailableInitiationLatency_s from surrounding trials

The first phrase in the title describes the y-axis metric. The phrase after
"Around" describes the Stop anchor group.


Peri-stop trial-level columns include:

    AnchorTrial
    AnchorSequence
    AnchorCategory
    RelativeTrial
    SurroundingTrial
    SurroundingTrialType
    SurroundingSequence
    SurroundingCorrect

The plotted/exported peri-stop metrics are:

    RegularAccuracy
        Meaning:

            Accuracy of surrounding Regular trials.

        Formula for each surrounding row:

            if SurroundingTrialType == Regular:
                RegularAccuracy = SurroundingCorrect * 100
            else:
                RegularAccuracy = blank / NaN

        Since Correct is coded as 1 for correct and 0 for incorrect:

            Regular LRP -> 100
            Regular LN  -> 0
            Stop trials -> blank / NaN

    RegularCorrectRT_s
        Meaning:

            L-to-R response latency for surrounding correct Regular trials.

        Formula for each surrounding row:

            if the surrounding trial's Outcome is RegularCorrect:
                RegularCorrectRT_s = RightResponseLatency_s
            else:
                RegularCorrectRT_s = blank / NaN

        This means Regular LN trials and Stop trials are blank for this metric.

    AvailableInitiationLatency_s
        Meaning:

            Animal-controlled latency to initiate each surrounding trial after
            the previous trial was expected to become available.

        Formula for each surrounding row:

            AvailableInitiationLatency_s =
                surrounding trial's AvailableInitiationLatency_s

        This metric is not restricted to RegularCorrect trials. It can exist for
        Regular and Stop surrounding trials, including the Stop anchor at
        RelativeTrial = 0 if the anchor has a valid initiation-latency value.


Peri-stop latency units and timeout handling
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Peri-stop latency plots use seconds when the y-axis says seconds.

For example:

    Regular LRP L to R Latency (seconds)
        plots RegularCorrectRT_s.

    Next-Trial Initiation Latency (seconds)
        plots AvailableInitiationLatency_s.

Both source columns already store seconds, not milliseconds.

The next-trial initiation latency peri-stop plots use the adjusted
AvailableInitiationLatency_s value. This means:

    - after rewarded trials, timing starts from pellet delivery;
    - after Regular LN trials, timing starts after the regular omission timeout;
    - after Stop LR trials, timing starts after stop-error noise plus timeout;
    - if the raw latency would be negative, the plotted analysis value is clipped
      to zero.

Therefore, the peri-stop initiation-latency plots are not simply plotting the
raw gap from one trial ending to the next trial starting. They are plotting the
animal-controlled waiting time after the task was expected to make the next
trial available.


Why RelativeTrial = 0 is present in some peri-stop tabs but absent in others
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

RelativeTrial = 0 is always conceptually the Stop anchor.

However, the Prism-style peri-stop tables drop rows where the selected metric is
blank / NaN before pivoting to wide format.

Therefore:

    RegularAccuracy
        At RelativeTrial = 0, the surrounding trial is the Stop anchor, not a
        Regular trial.

        RegularAccuracy is blank at 0, so the 0 row may be absent from the
        RegularAccuracy Prism table.

    RegularCorrectRT_s
        At RelativeTrial = 0, the surrounding trial is the Stop anchor, not a
        RegularCorrect / Regular LRP trial.

        RegularCorrectRT_s is blank at 0, so the 0 row may be absent from the
        RegularCorrectRT_s Prism table.

    AvailableInitiationLatency_s
        At RelativeTrial = 0, the surrounding trial is the Stop anchor.

        Because AvailableInitiationLatency_s can be defined for Stop trials, the
        0 row can appear in the AvailableInitiationLatency_s Prism table.

So, a missing 0 row in some peri-stop Excel tabs does not mean the Stop anchor
was lost. It means the metric being exported is not defined for the Stop anchor.

At RelativeTrial = 0, RegularAccuracy and RegularCorrectRT_s are normally blank
because the anchor is a Stop trial. The vertical line at zero marks the Stop
anchor rather than a Regular performance observation.


How peri-stop values are averaged
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The raw PeriStop_Trials sheet contains one row per:

    anchor Stop trial
    x relative trial position
    x surrounding trial

If a mouse has many Stop trials, it contributes many peri-stop rows.

The PeriStop Prism tables use a mean when the same mouse contributes multiple
anchors at the same RelativeTrial:

    MouseMean(mouse, RelativeTrial) =
        mean(metric across that mouse's anchors at that RelativeTrial)

Group plots then calculate:

    GroupMean(RelativeTrial) =
        mean(MouseMean values within the plotted group)

    GroupSEM(RelativeTrial) =
        SEM(MouseMean values within the plotted group)

This two-stage averaging prevents mice with more Stop trials from directly
contributing more weight to the group trajectory.


How this relates to Bandit-style peri-event plots
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Conceptually, this is similar to a peri-event analysis:

    1. Pick an anchor event.
    2. Extract a fixed window of surrounding observations.
    3. Choose a metric to sample from those surrounding observations.
    4. Average within mouse at each relative position.
    5. Average across mice/groups for the plotted trajectory.

In StopSig, the anchor event is always a Stop trial. The metric determines which
surrounding observations contribute nonblank values.

For example:

    RegularAccuracy around Stop trials
        samples only surrounding Regular trials.

    RegularCorrectRT_s around Stop trials
        samples only surrounding RegularCorrect / Regular LRP trials.

    AvailableInitiationLatency_s around Stop trials
        samples any surrounding trial with a valid initiation-latency value.


Principal component analysis (PCA)
----------------------------------

The PCA is intended as an exploratory multivariate summary of StopSig
performance. Candidate features are:

    RegularAccuracy
    StopAccuracy
    MeanRegularCorrectRT_s
    MeanStopFailureRT_s
    MeanAvailableInitiationLatency_s
    PostErrorSlowing_s
    PostStopRegularAccuracyChange
    PostStopRegularRTChange_s
    PostStopErrorAccuracyChange
    PostStopErrorRTChange_s

If a mouse appears in multiple summary rows/files, values are averaged by mouse
before PCA. Sex and group are taken from the first row for that mouse.

A candidate feature is retained only when:

    - it has at least two nonmissing mouse values, and
    - it has more than one unique nonmissing value.

PCA is performed only when there are at least three mice and at least two
usable features.

Missing values are replaced with the across-mouse mean for that feature. The
features are then standardized using StandardScaler so each feature is centered
and scaled before a two-component PCA is fitted.

Outputs include:

    PCA_Scores
        PC1 and PC2 coordinates for each mouse.

    PCA_Loadings
        Contribution/direction of each retained feature on PC1 and PC2.

    PCA_Variance
        Explained variance ratio and percentage for PC1 and PC2.

    PCA_Input
        Mouse-level values actually supplied to the scaler after imputation.

    PCA_Diagnostics
        Imputation mean, scaling mean, scaling SD, and number of imputed
        missing values for each retained feature.

If phase analysis is enabled, Dark and Light summaries are not used to refit
separate PCA models. Instead, phase feature values are imputed with the
full-session imputation means, standardized with the full-session scaler, and
projected into the existing full-session PCA space. This makes phase scores
directly comparable to the same axes.

PCA interpretation notes:

    - PCA is descriptive and does not test statistical significance.
    - The sign of a component is arbitrary; the pattern of relative loadings
      and scores matters more than whether the axis is positive or negative.
    - Mean-imputed values should be checked in PCA_Diagnostics.
    - PC1 and PC2 do not necessarily capture all meaningful variation.
    - Correlated or conceptually overlapping accuracy/change features can
      influence the component structure.


Excel workbook overview
-----------------------

The script saves:

    StopSig_EXTRAS.xlsx

The workbook can contain the following categories of sheets:

    1. Reconstructed and validation data.
    2. Analysis settings used for the run.
    3. Mouse/file and trial-type summaries.
    4. Optional phase summaries and phase trial tables.
    5. Peri-stop long-format and Prism-wide tables.
    6. PCA tables when PCA eligibility requirements are met.
    7. One-metric summary sheets.
    8. Trial-trajectory Prism sheets.

Excel sheet names are cleaned of invalid characters and limited to Excel's
31-character maximum.


Sheet: Trials
-------------

This is the main reconstructed trial-level output. Each row represents one
recognized trial start, whether completed or incomplete.

Important column groups include:

    Identity and indexing
        Filename, metadata, Trial, TypeTrial, PhaseTrial, PhaseTypeTrial

    Classification
        TrialType, Completed, Outcome, Sequence, Correct, ResponseType

    Validation
        StartEvent, TerminalEvent, TerminalEventCount, TrialTypeMismatch,
        PelletExpected, PelletConfirmed, RewardMismatch

    Phase
        Phase, StartPhase, EndPhase, PhaseCrossing

    Timing
        StartTime, EndTime, PelletTime, TerminalLatency_s,
        TimestampLatency_s, EventMillisLatency_s, LatencySource,
        RightResponseLatency_s, WithholdDuration_s,
        PelletDeliveryLatency_s, InterTrialInterval_s,
        StopSignalDelay_ms, ResponseWindow_s,
        RegularOmissionTimeout_s, StopErrorNoise_s,
        StopErrorTimeout_s, StopErrorLockout_s

    Availability/initiation
        AvailabilityTime, AvailabilityBasis,
        RawAvailableInitiationLatency_s, AvailableInitiationLatency_s,
        cumulative and phase-cumulative initiation metrics

    Rolling/cumulative performance
        RollingAccuracy, TypeRollingAccuracy, PhaseRollingAccuracy,
        PhaseTypeRollingAccuracy, associated numerator/denominator columns,
        CumulativeCorrect, CumulativeCompletedTrials, CumulativeAccuracy,
        CumulativePellets

    Sequential context
        PreviousTrialType, PreviousOutcome, PreviousSequence,
        PreviousCorrect, PrecedingRegularRunLength, OutcomeStreakLength

    Raw-value references
        pellet and poke counters at trial start/end, retrieval/interpellet
        values, StartRawCSVRow, TerminalRawCSVRow

Use Trials to validate individual events, investigate outliers, reproduce a
metric manually, or locate the raw rows responsible for a reconstructed trial.


Sheet: Summary
--------------

This is one row per processed file/metadata row. The raw internal metric names
are changed to descriptive display names where mappings are available.

Use Summary when:

    - comparing whole-session mouse/file performance,
    - checking trial and pellet counts,
    - reviewing response and initiation latencies,
    - examining post-error and post-stop effects,
    - selecting variables for group-level statistics.

If the same mouse has multiple files, Summary still contains one row per file;
only the PCA explicitly averages those rows by mouse identifier.


Sheet: Analysis_Settings
------------------------

This sheet records the user-selected settings used for the analysis run. It is
intended to make the workbook self-documenting, especially when timeout or
peri-event settings differ across experiments.

Settings include:

    Rolling accuracy window
    Peri-stop window
    Light/dark analysis enabled
    Light cycle start
    Light cycle end
    Regular omission timeout
    Stop-error noise duration
    Stop-error timeout duration
    Stop-error total lockout
    Stop-signal delay
    Response window
    Mouse ID metadata column
    Sex metadata column
    Group metadata column

Use Analysis_Settings to confirm which timeout/noise values were used to compute
AvailabilityTime and AvailableInitiationLatency_s.


Sheet: TrialType_Summary
------------------------

This contains one row per file/mouse per TrialType, with accuracy, response
counts, and terminal-latency summaries. It is useful for directly checking the
Regular and Stop denominators underlying the main accuracy metrics.


Sheet: Event_Counts
-------------------

This contains counts of every cleaned raw Event value for each file/mouse. It
is useful for checking whether expected task events are present and whether
unexpected event labels or spelling variants occurred.


Sheet: Validation
-----------------

This compact QC sheet includes:

    Trial
    Completed
    TrialTypeMismatch
    TerminalEventCount
    PelletExpected
    PelletConfirmed
    RewardMismatch
    StartRawCSVRow
    TerminalRawCSVRow

Use it as the first place to investigate mismatches, missing terminal events,
or trials with multiple terminal events.


Peri-stop long-format sheets
----------------------------

The complete peri-stop dataset is exported as:

    PeriStop_Trials

If it exceeds 1,000,000 rows, it is split across numbered sheets:

    PeriStop_Trials_1
    PeriStop_Trials_2
    ...

This is long-format data: each row is one surrounding-trial position for one
Stop anchor. Use it for custom mixed models, filtering individual anchors, or
checking exactly which trials contribute to peri-stop means.


PCA sheets
----------

When PCA is performed, the workbook includes:

    PCA_Scores
    PCA_Loadings
    PCA_Variance
    PCA_Input
    PCA_Diagnostics

When phase projections are also available, it includes:

    PCA_Phase_Scores
    PCA_Phase_Input
    PCA_Scores_Dark / PCA_Scores_Light
    PCA_Input_Dark / PCA_Input_Light


Phase sheets
------------

When phase analysis is enabled:

    Phase_Summary
        One summary row per file/mouse per phase.

    Trials_Dark
    Trials_Light
        Full reconstructed trial rows filtered by EndPhase-based Phase.


One-metric summary sheets
-------------------------

Sheets beginning with S_ contain one selected summary metric together with
mouse, sex, and group metadata. Examples include:

    S_CompletedTrials
    S_OverallAccuracy
    S_RegularAccuracy
    S_StopAccuracy
    S_BalancedAccuracy
    S_MeanRegularCorrectRT_s
    S_MeanStopFailureRT_s
    S_PostErrorSlowing_s
    S_PostStopRegularAccuracyChange

These sheets are convenient for importing individual metrics into GraphPad
Prism. Some long names are truncated to 31 characters.


Trial-trajectory Prism sheets
-----------------------------

Sheets beginning with T_ are wide-format:

    rows = trial index
    columns = individual mice

The first rows contain group and sex metadata. When multiple observations for
the same mouse and index exist, the pivot table uses their mean.

The main trajectory sheets are:

    T_OverallRolling
        RollingAccuracy by full-session Trial.

    T_RegularRolling
        TypeRollingAccuracy by Regular TypeTrial.

    T_StopRolling
        TypeRollingAccuracy by Stop TypeTrial.

    T_Regular_L_to_R
        RegularCorrect RightResponseLatency_s by Regular TypeTrial.

    T_Regular_R_to_P
        RegularCorrect PelletDeliveryLatency_s by Regular TypeTrial.

    T_Stop_N_to_P
        StopCorrect PelletDeliveryLatency_s by Stop TypeTrial.

    T_Stop_L_to_R
        StopIncorrect RightResponseLatency_s by Stop TypeTrial.

    T_CumNextTrialInit
        Cumulative initiation latency by Trial.

    T_CumMeanNextTrialInit
        Cumulative mean initiation latency by Trial.

When phase analysis is enabled, phase-reset initiation trajectories are also
exported using PhaseTrial:

    T_CumNextInit_Dark / Light
    T_CumMeanNextInit_Dark / Light


Peri-stop Prism sheets
----------------------

Wide-format peri-stop sheets are created for:

    anchor groups
        AllStop, StopSuccess, StopError

    metrics
        Accuracy, Regular_L_to_R, NextTrialInit

Examples:

    Peri_AllStop_Accuracy
    Peri_StopSuccess_Regular_L_to_R
    Peri_StopError_NextTrialInit

Rows are RelativeTrial and columns are mice. These workbook tables pool anchors
across phases; phase-specific peri-stop variants are generated as plots but are
not separately exported as wide Peri sheets.


Plots generated by the script
-----------------------------

Figures are saved under:

    StopSig_Plots

The routing folders are:

    All
        Full-session summary and trajectory plots.

    Dark
        Non-PeriStop, non-stacked phase-specific plots ending in __Dark.png.

    Light
        Non-PeriStop, non-stacked phase-specific plots ending in __Light.png.

    PeriStop
        All PeriStop plots, including Dark and Light anchor variants.

    Stacked
        Full-session and phase-specific stacked trial rasters.

    PCA
        PCA scores, loadings, and feature-correlation plots.

Plot type takes priority over phase for PeriStop, Stacked, and PCA outputs.
Therefore a Dark peri-stop figure is stored in PeriStop, and a Dark stacked
raster is stored in Stacked.


Trajectory plots
----------------

The script produces group trajectories for:

    Rolling overall accuracy
    Rolling Regular-trial accuracy
    Rolling Stop-trial accuracy
    Cumulative next-trial initiation latency
    Cumulative mean next-trial initiation latency

If phase analysis is enabled, Dark and Light variants use PhaseTrial or
PhaseTypeTrial and the corresponding phase-specific rolling/cumulative values.

For each trajectory, the script generates multiple comparisons:

    by group
    by sex
    by combined Sex x Group
    group within each sex
    sex within each group

At each x-position, observations are first averaged within mouse. The plotted
line is then the mean across mice and the shaded band is SEM across mice.


Summary plots
-------------

Summary stripplots are produced for selected accuracy, latency, and adjustment
metrics, including:

    OverallAccuracy
    RegularAccuracy
    StopAccuracy
    BalancedAccuracy
    MeanRegularCorrectRT_s
    MeanStopFailureRT_s
    MeanAvailableInitiationLatency_s
    PostErrorSlowing_s
    PostStopRegularAccuracyChange
    PostStopRegularRTChange_s
    PostStopErrorAccuracyChange
    PostStopErrorRTChange_s

Variants compare group, sex, combined categories, and one factor within levels
of the other factor. Optional Dark and Light versions are generated from
Phase_Summary.


Peri-stop plots
---------------

Peri-stop trajectories are generated for all Stop anchors, Stop Success
anchors, and Stop Error anchors. The plotted metrics are Regular accuracy,
RegularCorrect response latency, and next-trial initiation latency.

The dashed vertical line at RelativeTrial = 0 marks the Stop anchor. Dark and
Light versions classify the entire window by the anchor's phase and are routed
to the PeriStop folder.


Stacked trial rasters
---------------------

The script creates two raster families:

    Stacked_TrialRaster
        Regular LRP, Regular LN, Stop LNP, and Stop LR are shown as distinct
        sequence colors.

    Stacked_AccuracyRaster
        Correct is yellow-green (#9ACD32).
        Incorrect is red (#FF0000).

Each mouse is one row. Mice are sorted by sex, group, then mouse identifier.
Labels use:

    Mouse | first letter of Sex | Group

White areas indicate missing/unavailable positions, such as after a mouse's
last trial or where the plotted value is blank. Phase-specific rasters use
PhaseTrial and remain in the Stacked folder.


PCA plots
---------

When PCA is available, the script generates:

    PC1 versus PC2 score plots by sex, group, and combined group
    factor-within-factor PCA variants
    optional Dark and Light projections
    PC1 and PC2 loading barplots
    PCA feature-correlation heatmap

The percentage shown on each PCA axis is the explained variance percentage
from the full-session PCA model.


Processing errors
-----------------

Files that cannot be reconstructed are skipped rather than stopping all other
files. Reasons can include missing required columns, unmatched metadata
filenames, read errors, or absence of recognized StopSig start events.

If any files are skipped, details are saved as:

    StopSig_processing_errors.txt


How to manually validate a small example
----------------------------------------

1. Open a raw StopSig CSV and find a recognized start event.

2. Treat that row as the start of a trial and stop immediately before the next
   recognized start event.

3. Within the interval, locate the first recognized terminal event.

4. Confirm that the start and terminal mapping produce the expected TrialType,
   Outcome, Sequence, ResponseType, and Correct value.

5. Check TerminalEventCount. If it exceeds 1, confirm that the first terminal
   event is the one used.

6. Search from the terminal event to the next trial start for a Pellet event.
   Compare this with PelletExpected/Correct and RewardMismatch.

7. Compare terminal latency against the selected LatencySource. If the
   Block_Pellet_Count-derived value is absent or outside 0-60 seconds, confirm
   that timestamp latency was used.

8. For the next trial, reproduce AvailabilityTime using the previous sequence
   rule and calculate RawAvailableInitiationLatency_s.

9. Check a small rolling window manually:

       rolling accuracy = valid correct trials in window
                          / valid completed trials in window * 100

   Incomplete Correct values should not enter the denominator.

10. For a Stop anchor, compare the PeriStop_Trials rows against the source
    Trial numbers at RelativeTrial -1, 0, and +1.


Common interpretation notes
---------------------------

1. OverallAccuracy is affected by the Regular/Stop trial ratio.

BalancedAccuracy gives Regular and Stop accuracy equal weight and is often
more suitable when trial types occur at very different frequencies.

2. Correct does not mean right poke.

Correct means right poke on Regular trials and withholding on Stop trials.

3. PelletsConfirmed and correct-trial counts need not match perfectly.

RewardMismatch identifies discrepancies rather than silently changing the
behavioral classification.

4. MeanStopFailureRT_s describes failed stopping.

It uses Stop LR trials, so it is the latency of the response that escaped
inhibition, not the latency of successful stopping.

5. MeanCorrectWithhold_s is based on the terminal-event latency for Stop LNP.

It is not a direct estimate of an unobserved internal stopping process.

6. Positive post-error slowing means slower correct Regular responses after
errors. It is not automatically beneficial or detrimental without context.

7. Post-stop change metrics are differences, not ratios.

Always inspect the component condition means and opportunity counts when a
difference is large or unstable.

8. Peri-stop windows overlap.

When Stop trials occur close together, one trial can appear in windows around
multiple anchors. This is expected in the long-format dataset.

9. Phase-specific peri-stop windows are anchor-phase windows.

They do not require every surrounding trial to belong to the anchor's phase.

10. Phase summaries do not contain phase-specific raw timeout event counts.

Those columns are zero under the current phase-summary implementation.

11. Cumulative full-session and phase-cumulative initiation metrics differ.

The PhaseCumulative columns reset their running calculation by Phase; the
ordinary cumulative columns do not.

12. PCA availability can change across datasets.

Features with insufficient observations or no variation are removed, and PCA
is omitted when the minimum mouse/feature requirements are not met.


Recommended workflow
--------------------

For a new dataset:

1. Open Validation first.

   Check incomplete trials, reward mismatches, trial-type mismatches, and
   intervals with multiple terminal events.

2. Inspect Trials for several mice.

   Confirm event classification, latency source, pellet matching, phase
   assignment, and next-trial availability logic.

3. Review TrialType_Summary and Summary.

   Check Regular and Stop denominators before interpreting accuracy or
   adjustment metrics.

4. Inspect the stacked sequence and accuracy rasters.

   Look for missing sections, unusual outcome runs, between-mouse differences,
   and phase-specific patterns.

5. Examine rolling trajectories.

   Choose the rolling window with the expected trial count and desired balance
   between responsiveness and smoothness in mind.

6. Examine PeriStop_Trials before relying on peri-stop plots.

   Check anchor counts, incomplete Stop anchors, overlapping windows, and the
   number of valid Regular observations at each RelativeTrial.

7. Use one-metric and T_ sheets for Prism analyses.

8. Treat PCA as exploratory and inspect PCA_Diagnostics, loadings, explained
   variance, and feature correlations alongside the score plots.
