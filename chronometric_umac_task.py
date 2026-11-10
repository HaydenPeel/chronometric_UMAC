"""UMAC adaptation of chronometric task: fixed versus variable reward.

Keep chronometric_trial_schedule.csv alongside this file.
"""
import csv
import math
import random
from datetime import datetime
from pathlib import Path
from psychopy import core, event, visual

HERE = Path(__file__).resolve().parent
SCHEDULE = HERE / 'chronometric_trial_schedule.csv'
DEBUG = False  # Set True for abbreviated debugging trials
DEBUG_TRIALS = 5
BLOCKS_TO_RUN = 1  # Pilot: one full 60-trial block; set to 8 for full experiment
PRACTICE_TRIALS = 16
PRACTICE_SEED = 20261102  # Reproducible independent practice shuffle
UMAC_SEED = 20261103  # Reproducible 100/0 outcome assignment
MAX_PRACTICE_REPEATS = None  # Original JS repeats until criterion
COUNTERBALANCE = 0  # 0: blue low/orange high; 1: reversed
FULLSCREEN = True  # Timing test: use the monitor’s fullscreen mode
REFRESH_HZ = 60
TARGET_MS = 2000
POST_GO_MS = 100
MAX_OFFSET_MS = 200
FEEDBACK_MS = 800  # Original JS default
ITI_MS = 1000
WIDTH, HEIGHT = 900, 500  # Logical drawing area, not display resolution
MEDAL_DIR = HERE / "chronometric_medals"
# Reward colour mapping must be checked against participant counterbalancing in original index.html.
REWARD_COLORS = ({'lo': '#009dff', 'hi': '#ff6117'} if COUNTERBALANCE == 0
                 else {'lo': '#ff6117', 'hi': '#009dff'})
POINTS_PER_MEDAL = 2500  # Original VMAC thresholds; reconsider for UMAC reward scale
# Existing low/high colours now mean STABLE/VARIABLE. COUNTERBALANCE reverses their mapping.
REWARD_LABELS = {'lo': 'Stable (50)', 'hi': 'Variable (100/0)'}


def assign_umac_rewards(rows, seed):
    """Assign 50 to stable and exactly half 100 / half 0 within each variable-reward group.

    Groups are defined by phase/block when passed separately. Does not change trial order.
    """
    rng = random.Random(seed)
    for row in rows:
        row['assigned_reward_points'] = 50 if row['reward'] == 'lo' else None
    variable = [row for row in rows if row['reward'] == 'hi']
    rng.shuffle(variable)
    for idx, row in enumerate(variable):
        row['assigned_reward_points'] = 100 if idx < len(variable) // 2 else 0
    return rows



def load_trials():
    with SCHEDULE.open(newline='', encoding='utf-8-sig') as f:
        all_trials = list(csv.DictReader(f))
    if len(all_trials) != 480:
        raise ValueError(f'Expected 480 schedule rows; found {len(all_trials)}')
    trials = [t for t in all_trials if 1 <= int(t['blockId']) <= BLOCKS_TO_RUN]
    for block in range(1, BLOCKS_TO_RUN + 1):
        if sum(int(t['blockId']) == block for t in trials) != 60:
            raise ValueError(f'Expected 60 trials in block {block}')
    for block in range(1, BLOCKS_TO_RUN + 1):
        assign_umac_rewards([t for t in trials if int(t['blockId']) == block], UMAC_SEED + block)
    if DEBUG:
        return [t for t in trials if int(t['presentationOrderWithinBlock']) <= DEBUG_TRIALS]
    return trials


def draw_blank_frames(win, milliseconds):
    """Refresh during feedback/ITI instead of core.wait, to avoid false dropped-frame reports."""
    for _ in range(round(milliseconds * REFRESH_HZ / 1000)):
        win.flip()


def run_trial(win, trial, practice_mode="main"):
    viewing_ms = float(trial['viewingMs'])
    onset_frame = 0 if practice_mode == "accuracy" else round((TARGET_MS - (500 if practice_mode == "timing" else viewing_ms)) * REFRESH_HZ / 1000)
    offset_frame = None if practice_mode == "accuracy" else round((TARGET_MS + POST_GO_MS) * REFRESH_HZ / 1000)
    reward = trial['reward']
    color = REWARD_COLORS[reward]
    colored_side = 'left' if trial['patch'] == 'L' else 'right'
    correct_key = 'up' if trial['targetPosition'] == 'top' else 'down'

    # PsychoPy logical canvas 900x500; geometry remains an approximation of browser canvas.
    # Convert from canvas coordinates (origin top-left) to PsychoPy pixel coordinates
    # (origin at the window centre; positive y is upward).
    left_x = WIDTH * (0.32 - 0.5)
    right_x = WIDTH * (0.68 - 0.5)
    top_bar_y_canvas = 40
    bottom_bar_y_canvas = HEIGHT - 40 - 24
    stimulus_center_canvas_y = ((top_bar_y_canvas + 24) + bottom_bar_y_canvas) / 2
    stim_y = HEIGHT / 2 - stimulus_center_canvas_y
    patches = []
    for side, x in [('left', left_x), ('right', right_x)]:
        distractor = side == colored_side
        marker_pos = trial['distractorPosition'] if distractor else trial['targetPosition']
        circle = visual.Circle(win, radius=80, pos=(x, stim_y),
                               fillColor=color if distractor else '#dfdfdf',
                               lineColor='#000000', lineWidth=2)
        marker = visual.Circle(win, radius=15,
                               pos=(x, stim_y + (50 if marker_pos == 'top' else -50)),
                               fillColor='#000000', lineColor='#000000')
        patches.append((circle, marker))

    bars = []
    for canvas_y in (top_bar_y_canvas, bottom_bar_y_canvas):
        y = HEIGHT / 2 - (canvas_y + 12)
        outline = visual.Rect(win, width=WIDTH * .70, height=24, pos=(0, y),
                              fillColor=None, lineColor='#ffffff', lineWidth=2)
        fill = visual.Rect(win, width=1, height=24, pos=(0, y),
                           fillColor='#ffffff', lineColor=None)
        bars.append((outline, fill))

    clock = core.Clock()
    first_response = None
    observed_onset_ms = None
    observed_offset_ms = None
    # Frame interval recording only covers the active trial, not feedback or ITI.
    win.frameIntervals.clear()
    win.recordFrameIntervals = True
    try:
        frame = 0
        while practice_mode == "accuracy" or frame <= offset_frame:
            progress = min(1, math.floor((frame * 1000 / REFRESH_HZ) / 500) / 4)
            if practice_mode != "accuracy":
                for outline, fill in bars:
                    outline.draw()
                    if progress:
                        fill.width = WIDTH * .70 * progress
                        fill.draw()
            if practice_mode == "accuracy" or onset_frame <= frame < offset_frame:
                for circle, marker in patches:
                    circle.draw()
                    marker.draw()
            if frame == 0:
                win.callOnFlip(clock.reset)
                win.callOnFlip(event.clearEvents, eventType='keyboard')
            win.flip()
            if frame == onset_frame:
                observed_onset_ms = clock.getTime() * 1000
            if offset_frame is not None and frame == offset_frame:
                observed_offset_ms = clock.getTime() * 1000
            for key, timestamp in event.getKeys(keyList=['up', 'down', 'escape'], timeStamped=clock):
                if key == 'escape':
                    raise KeyboardInterrupt
                if first_response is None:
                    first_response = (key, timestamp * 1000)
            if first_response is not None:
                break
            frame += 1
    finally:
        win.recordFrameIntervals = False

    intervals = list(win.frameIntervals)
    # Flip timestamps describe software-observed updates, not photodiode measurements.
    actual_visible_ms = (observed_offset_ms - observed_onset_ms) if (observed_offset_ms is not None and observed_onset_ms is not None) else None
    response_key, rt_ms = first_response if first_response else (None, None)
    offset_ms = rt_ms - TARGET_MS if rt_ms is not None else None
    timing_success = offset_ms is not None and abs(offset_ms) <= MAX_OFFSET_MS
    if practice_mode == "accuracy":
        timing_success = None  # No timing criterion in accuracy practice
    correct = response_key == correct_key
    # UMAC: points depend on assigned outcome, not graded time based accuracy
    display_score = int(trial['assigned_reward_points']) if timing_success else 0
    points_earned = display_score if timing_success and correct and practice_mode == 'main' else 0

    if practice_mode == 'accuracy':
        feedback_label = 'CORRECT!' if correct else 'INCORRECT'
    elif practice_mode == 'timing':
        feedback_label = 'GOOD!' if timing_success else ('TOO FAST!' if rt_ms is not None and offset_ms < -MAX_OFFSET_MS else 'TOO SLOW!')
    elif not timing_success:
        if rt_ms is None:
            feedback_label = 'NO RESPONSE'
        elif offset_ms < -MAX_OFFSET_MS:
            feedback_label = 'TOO EARLY'
        else:
            feedback_label = 'TOO LATE'
    elif practice_mode == 'full':
        # Show both accuracy and timing, without points or colour-contingency cues.
        accuracy_text = 'CORRECT' if correct else ('NO RESPONSE' if rt_ms is None else 'INCORRECT')
        timing_text = ('ON TIME' if timing_success else
                       ('NO RESPONSE' if rt_ms is None else
                        ('TOO EARLY' if offset_ms < -MAX_OFFSET_MS else 'TOO LATE')))
        feedback_label = f'{accuracy_text}\n{timing_text}'
    else:
        # Main experiment only: show assigned reward and crossed-out potential on errors.
        feedback_label = f'+{display_score}'

    feedback = visual.TextStim(win, text=feedback_label, height=40,
                               color=color if (timing_success and practice_mode == 'main') else '#ffffff', bold=True)
    strike_circle = None
    strike_line = None
    if timing_success and not correct and practice_mode == 'main':
        # Original browser feedback: white prohibition symbol over potential points.
        strike_circle = visual.Circle(win, radius=45, pos=(0, 0), fillColor=None,
                                      lineColor='#ffffff', lineWidth=5)
        strike_line = visual.Line(win, start=(-32, 32), end=(32, -32),
                                  lineColor='#ffffff', lineWidth=5)

    # Every win.flip() clears the previous drawing. Redraw feedback on EACH
    # refresh so it remains visible for the full requested duration.
    for _ in range(round(FEEDBACK_MS * REFRESH_HZ / 1000)):
        feedback.draw()
        if strike_circle is not None:
            strike_circle.draw()
            strike_line.draw()
        win.flip()

    draw_blank_frames(win, ITI_MS)

    if practice_mode == 'accuracy':
        outcome = 'correct' if correct else 'incorrect'
    elif rt_ms is None:
        outcome = 'miss'
    elif not timing_success:
        outcome = 'too_early' if offset_ms < -MAX_OFFSET_MS else 'too_late'
    elif not correct:
        outcome = 'incorrect'
    else:
        outcome = 'correct_scored'

    return {
        **trial,
        'phase': practice_mode, 'practice_attempt': '', 'practice_trial': '',
        'response': response_key or '', 'correct_key_actual': correct_key,
        'correct': correct, 'rt_ms': rt_ms, 'offset_ms': offset_ms,
        'timing_success': timing_success, 'outcome': outcome,
        'onset_delay_ms': (observed_onset_ms - (0 if practice_mode == 'accuracy' else (TARGET_MS - (500 if practice_mode == 'timing' else viewing_ms)))) if observed_onset_ms is not None else None,
        'onset_observed': observed_onset_ms is not None,
        'processing_time_ms_planned': (rt_ms - (0 if practice_mode == 'accuracy' else (TARGET_MS - (500 if practice_mode == 'timing' else viewing_ms)))) if rt_ms is not None else None,
        'processing_time_ms_observed_flip': (rt_ms - observed_onset_ms) if rt_ms is not None and observed_onset_ms is not None else None,
        'planned_onset_frame': onset_frame, 'planned_offset_frame': offset_frame,
        'observed_onset_ms': observed_onset_ms, 'observed_offset_ms': observed_offset_ms,
        'visible_duration_ms_observed_flip': actual_visible_ms,
        'long_frame_intervals': sum(x > 1.5 / REFRESH_HZ for x in intervals),
        'max_frame_interval_ms': max(intervals) * 1000 if intervals else None,
        'reward_condition_umac': 'stable' if reward == 'lo' else 'variable',
        'display_score': display_score, 'points_earned': points_earned,
    }


def show_screen(win, heading, body, footer='Press SPACE to continue'):
    """Draw an instruction/break screen until Space; Escape aborts safely."""
    title = visual.TextStim(win, text=heading, pos=(0, 165), height=34,
                            color='white', bold=True, wrapWidth=1500)
    content = visual.TextStim(win, text=body, pos=(0, 0), height=25,
                              color='white', wrapWidth=1450, alignText='center')
    prompt = visual.TextStim(win, text=footer, pos=(0, -180), height=22,
                             color='#8eeaff')
    event.clearEvents(eventType='keyboard')
    while True:
        title.draw()
        content.draw()
        prompt.draw()
        win.flip()
        keys = event.getKeys(keyList=['space', 'escape'])
        if 'escape' in keys:
            raise KeyboardInterrupt
        if 'space' in keys:
            return


def save_results(results, output):
    if not results:
        return
    with output.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)


def block_summary(results, block):
    current = [r for r in results if r.get('phase') == 'main' and int(r['blockId']) == block]
    total = sum(int(r['points_earned']) for r in results if r.get('phase') == 'main')
    medal_level = min(6, total // POINTS_PER_MEDAL)
    next_medal = (medal_level + 1) * POINTS_PER_MEDAL
    return (f'TOTAL POINTS: {total:,}'
            + f'\nMedals earned: {medal_level} of 6'
            + (f'\nNext medal at {next_medal:,} points' if medal_level < 6 else '\nAll medals earned!'))


def show_block_screen(win, results, block, final=False):
    """Block scores and original medal PNGs."""
    total = sum(int(r['points_earned']) for r in results if r.get('phase') == 'main')
    earned = min(6, total // POINTS_PER_MEDAL)
    title = visual.TextStim(win, text=f'BLOCK {block} COMPLETE', pos=(0, 180),
                            height=36, bold=True, color='white')
    content = visual.TextStim(win, text=block_summary(results, block),
                              pos=(0, 45), height=22, color='white',
                              alignText='center', wrapWidth=1400)
    prompt = visual.TextStim(win, text='Press SPACE to finish' if final else 'Take a break. Press SPACE when ready.',
                             pos=(0, -205), height=20, color='#8eeaff')
    medals = []
    for i in range(1, 7):
        path = MEDAL_DIR / f'reward{i}.png'
        if path.exists():
            medal = visual.ImageStim(win, image=str(path), size=(75, 75),
                                     pos=((i - 3.5) * 90, -145),
                                     opacity=1.0 if i <= earned else .2)
            medals.append(medal)
    event.clearEvents(eventType='keyboard')
    while True:
        title.draw()
        content.draw()
        for medal in medals:
            medal.draw()
        prompt.draw()
        win.flip()
        keys = event.getKeys(keyList=['space', 'escape'])
        if 'escape' in keys:
            raise KeyboardInterrupt
        if 'space' in keys:
            return


def run_practice(win, all_schedule, results, output):
    """Original three stages: 16 accuracy, 16 timing, 16 combined.

    The JS shuffles the full design and slices 48 trials. Here, use an independent
    seeded shuffle so practice doesn't change the main-block schedule.
    """
    pool = list(all_schedule)
    random.Random(PRACTICE_SEED).shuffle(pool)
    # Ensure accuracy practice includes 8 congruent and 8 incongruent trials.
    # Other stages use a shuffled pool without altering the main experiment schedule.
    congruent = [t for t in pool if t['congruency'] == 'congruent'][:8]
    incongruent = [t for t in pool if t['congruency'] == 'incongruent'][:8]
    if len(congruent) != 8 or len(incongruent) != 8:
        raise ValueError('Not enough practice trials for congruency balancing')
    accuracy_trials = congruent + incongruent
    random.Random(PRACTICE_SEED + 1).shuffle(accuracy_trials)
    used = {id(t) for t in accuracy_trials}
    remaining = [t for t in pool if id(t) not in used]
    practice_stages = [accuracy_trials, remaining[:16], remaining[16:32]]
    for idx, rows in enumerate(practice_stages):
        assign_umac_rewards(rows, UMAC_SEED + 100 + idx)
    stages = [
        ('accuracy', 'PRACTICE 1: ACCURACY',
         'Look at the GREY circle.\nBlack dot at TOP: UP arrow.\nBlack dot at BOTTOM: DOWN arrow.\n\nFocus on choosing the correct response.', .75),
        ('timing', 'PRACTICE 2: TIMING',
         'Press UP or DOWN when the bars finish filling, at 2 seconds.\n\nGOOD! means your timing was within the target window.\nTOO FAST! or TOO SLOW! means adjust your response timing.', .50),
        ('full', 'PRACTICE 3: COMBINED',
         'Now combine ACCURACY and TIMING.\n\nRespond to the black dot in the GREY circle,\nand try to respond when the bars finish filling.\n\nAfter each trial, you will see whether your choice was correct\nand whether your response was on time.', None),
    ]
    for stage_index, (mode, title, instructions, threshold) in enumerate(stages):
        attempt = 0
        while True:
            attempt += 1
            show_screen(win, title, instructions)
            stage_trials = practice_stages[stage_index]
            if DEBUG:
                stage_trials = stage_trials[:DEBUG_TRIALS]
            stage_results = []
            for j, trial in enumerate(stage_trials, 1):
                result = run_trial(win, trial, practice_mode=mode)
                result['practice_attempt'] = attempt
                result['practice_trial'] = j
                stage_results.append(result)
                results.append(result)
                save_results(results, output)
                print(f'  {mode} {j}/{len(stage_trials)}: {result["outcome"]}, '
                      f'points={result["points_earned"]}, long_frames={result["long_frame_intervals"]}')
            if threshold is None:
                break
            n_pass = sum(r['correct'] if mode == 'accuracy' else r['timing_success']
                         for r in stage_results)
            rate = n_pass / len(stage_results)
            if rate >= threshold:
                show_screen(win, 'PRACTICE PASSED',
                            f'{n_pass}/{len(stage_results)} successful trials ({rate:.0%}).')
                break
            show_screen(win, 'REPEAT PRACTICE',
                        f'{n_pass}/{len(stage_results)} successful trials ({rate:.0%}).\n'
                        f'You need at least {threshold:.0%}. Please try again.')
            if MAX_PRACTICE_REPEATS is not None and attempt >= MAX_PRACTICE_REPEATS:
                show_screen(win, 'PRACTICE NOT PASSED',
                            'Maximum practice attempts reached. Ending this test.')
                raise KeyboardInterrupt
    show_screen(win, 'PRACTICE COMPLETE',
                'You are ready to begin the experiment.\n\nPress SPACE to continue.')


def main():
    trials = load_trials()
    with SCHEDULE.open(newline='', encoding='utf-8-sig') as f:
        all_schedule = list(csv.DictReader(f))
    output = HERE / f"chronometric_with_practice_results_{datetime.now():%Y%m%d_%H%M%S}.csv"
    print(f'Practice (3 stages) + {len(trials)} main trials across {BLOCKS_TO_RUN} block(s). DEBUG={DEBUG}')
    win = visual.Window(size=(WIDTH, HEIGHT), fullscr=FULLSCREEN, units='pix',
                        color='#333333', colorSpace='hex', waitBlanking=True)
    results = []
    try:
        show_screen(win, 'TIMED DOT CHOICE',
                    'Your task is to identify the black dot in the GREY circle.\n\n'
                    'Black dot at the TOP: press UP arrow.\n'
                    'Black dot at the BOTTOM: press DOWN arrow.\n\n'
                    'Aim to respond at 2 seconds, when the timing bars finish.\n'
                    'After practice, you can earn points for correct, well-timed responses.\n\n'
                    'Try to respond accurately AND at the right time.')
        run_practice(win, all_schedule, results, output)
        show_screen(win, 'EXPERIMENT SESSION',
                    f'You will complete {BLOCKS_TO_RUN} blocks of 60 trials.\n\n'
                    'After each block you can take a break and see your total points and medals.\n\n'
                    'Respond to the grey-circle dot accurately and at 2 seconds.')
        previous_block = None
        for i, trial in enumerate(trials, 1):
            block = int(trial['blockId'])
            if previous_block is not None and block != previous_block:
                save_results(results, output)
                show_block_screen(win, results, previous_block)
            if block != previous_block:
                show_screen(win, f'BLOCK {block} OF {BLOCKS_TO_RUN}',
                            'Respond to the black dot in the GREY circle.\n'
                            'UP for top; DOWN for bottom.\n'
                            'Time your response for 2 seconds.')
            result = run_trial(win, trial)
            results.append(result)
            print(f"Trial {i}/{len(trials)} (block {block}): "
                  f"duration={float(trial['viewingMs']):.2f} ms, "
                  f"outcome={result['outcome']}, points={result['points_earned']}, "
                  f"onset_delay={result['onset_delay_ms']}, "
                  f"long_frames={result['long_frame_intervals']}")
            previous_block = block
        save_results(results, output)
        if previous_block is not None:
            show_block_screen(win, results, previous_block, final=True)
            show_screen(win, 'EXPERIMENT COMPLETE',
                        f'Final score: {sum(r["points_earned"] for r in results if r["phase"] == "main"):,} points.\n\nThank you for participating.',
                        'Press SPACE to finish')
    except KeyboardInterrupt:
        print('Stopped early with Escape. Saving completed trials.')
    finally:
        win.close()
        save_results(results, output)
        print(f'Saved {len(results)} practice + main trial records to {output}')


if __name__ == '__main__':
    main()
