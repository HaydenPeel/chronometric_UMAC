"""Python reconstruction of Task/library/stimsetup_final.js trial design.
Run with the Python interpreter in your virtual environment.
This generates a trial schedule; it does not display stimuli.
"""
import csv
import random
from collections import Counter
from pathlib import Path

SEED = 20261030  # Change for a different reproducible trial order
rng = random.Random(SEED)
CELLS = [('lo','L'), ('lo','R'), ('hi','L'), ('hi','R')]
COMBOS = [('top','congruent'), ('top','incongruent'),
          ('bottom','congruent'), ('bottom','incongruent')]
SHIFTS = {('lo','L',1):0,('lo','L',2):2,('lo','R',1):1,('lo','R',2):3,
          ('hi','L',1):2,('hi','L',2):0,('hi','R',1):3,('hi','R',2):1}
TIME_CLASSES = [[start + 4*k for k in range(15)] for start in range(1,5)]

base = []
for cell_index, (reward, patch) in enumerate(CELLS):
    for repetition in (1,2):
        shift = SHIFTS[(reward,patch,repetition)]
        for combo_index, (target, congruency) in enumerate(COMBOS):
            class_index = (combo_index + shift) % 4
            for spread_index, time_bin in enumerate(TIME_CLASSES[class_index], start=1):
                distractor = target if congruency == 'congruent' else ('bottom' if target == 'top' else 'top')
                base.append(dict(designTrialId=len(base)+1, reward=reward, patch=patch,
                    cellIndex=cell_index, repetitionWithinCell=repetition,
                    comboId=combo_index+1, comboLabel=f'{target}-{congruency}',
                    targetPosition=target, congruency=congruency, timeBin=time_bin,
                    viewingMs=time_bin*(50/3), timeClassIndex=class_index+1,
                    spreadIndex=spread_index, classShift=shift,
                    distractorPosition=distractor,
                    correctResponse='z' if target=='top' else 'm',
                    isShortTrial=time_bin*(50/3)<=200, trialType='main'))

by_cell = {}
for trial in base:
    by_cell.setdefault((trial['timeBin'],trial['reward'],trial['patch']), []).append(trial)
blocks = [[] for _ in range(8)]
for time_bin in range(1,61):
    for cell_index, (reward, patch) in enumerate(CELLS):
        pair = sorted(by_cell[(time_bin,reward,patch)], key=lambda t:t['repetitionWithinCell'])
        assert len(pair)==2
        group_index=(time_bin-1)//4
        within_group=(time_bin-1)%4
        rotated=(cell_index+within_group+group_index)%4
        first_block=2*rotated
        if (time_bin+cell_index)%2==1:
            pair.reverse()
        for offset, trial in enumerate(pair):
            blocks[first_block+offset].append({**trial,'blockId':first_block+offset+1})

def valid_next(seq, t):
    if any(p['comboLabel']==t['comboLabel'] for p in seq[-3:]): return False
    if seq and seq[-1]['isShortTrial'] and t['isShortTrial']: return False
    for key in ('reward','correctResponse'):
        if len(seq)>=5 and all(p[key]==t[key] for p in seq[-5:]): return False
    return True

def stats(seq):
    repeat=sum(any(seq[i]['comboLabel']==seq[j]['comboLabel'] for j in range(max(0,i-3),i)) for i in range(len(seq)))
    short=sum(seq[i]['isShortTrial'] and seq[i-1]['isShortTrial'] for i in range(1,len(seq)))
    def max_run(key):
        longest=run=0
        last=None
        for t in seq:
            run=run+1 if t[key]==last else 1
            last=t[key];longest=max(longest,run)
        return longest
    reward_run=max_run('reward');response_run=max_run('correctResponse')
    return (repeat,short,reward_run,response_run)

def constrained_shuffle(trials, max_attempts=4000):
    best=None;best_score=float('inf')
    for attempt in range(1,max_attempts+1):
        pool=trials.copy();rng.shuffle(pool);seq=[]
        while pool:
            idx=next((i for i,t in enumerate(pool) if valid_next(seq,t)),None)
            if idx is None:break
            seq.append(pool.pop(idx))
        candidate=seq+pool
        a,b,c,d=stats(candidate)
        score=1000*(a+b)+100*(max(0,c-5)+max(0,d-5))+len(trials)-len(seq)
        if score<best_score:best=candidate;best_score=score
        if (a,b)==(0,0) and c<=5 and d<=5 and len(seq)==len(trials):
            return candidate,attempt,True
    return best,max_attempts,False

all_trials=[]
for block_id, block in enumerate(blocks, start=1):
    ordered,attempts,success=constrained_shuffle(block)
    if not success:
        print(f'WARNING: Block {block_id}: best-effort shuffle; ordering constraints NOT fully satisfied')
    for position,t in enumerate(ordered,start=1):
        all_trials.append({**t,'presentationOrderWithinBlock':position,
                           'globalTrialIndex':len(all_trials)+1})
    print(f'Block {block_id}: 60 trials, ordering constraints passed ({attempts} attempt(s))')

assert len(all_trials)==480
assert Counter(t['timeBin'] for t in all_trials)==Counter({i:8 for i in range(1,61)})
assert all(sum(t['timeBin']==i for t in block)==1 for block in
           [all_trials[j:j+60] for j in range(0,480,60)] for i in range(1,61))
assert all(Counter((t['reward'],t['patch']) for t in all_trials[j:j+60])==
           Counter({cell:15 for cell in CELLS}) for j in range(0,480,60))
# Ordering constraints are soft in the original JS: its shuffler also returns a best-effort fallback.
ordering_pass=all(stats(all_trials[j:j+60])[:2]==(0,0) and max(stats(all_trials[j:j+60])[2:])<=5
                  for j in range(0,480,60))
assert Counter(t['comboId'] for t in all_trials)==Counter({i:120 for i in range(1,5)})
assert all(Counter((t['reward'],t['patch'],t['timeBin']) for t in all_trials)[(*cell,i)]==2
           for cell in CELLS for i in range(1,61))

path=Path(__file__).with_name('chronometric_trial_schedule.csv')
with path.open('w',newline='',encoding='utf-8') as f:
    writer=csv.DictWriter(f,fieldnames=list(all_trials[0]))
    writer.writeheader();writer.writerows(all_trials)
print(f'\nPASS: 480 balanced trials, 8 blocks, 60 time bins.')
print(f'Ordering constraints all satisfied: {ordering_pass}')
print(f'Saved: {path}')
print('\nFirst five trials:')
for t in all_trials[:5]:
    print(f"  bin={t['timeBin']:2} viewing={t['viewingMs']:7.2f}ms "
          f"onset={2000-t['viewingMs']:7.2f}ms reward={t['reward']} "
          f"side={t['patch']} target={t['targetPosition']} "
          f"congruency={t['congruency']}")
