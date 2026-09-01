// Matt's closet — the single source of truth for every look he owns.
// Used by the ChatBot studio drawer AND the full-page Closet inventory.
// `hold` is his pose key in frames.json; `prop` a painted item thumbnail;
// `thumb` a full-pose thumbnail; `line` what he says when he puts it on.

export const CLOSET = [
  { id: 'guitar_electric', label: 'Guitar', kind: 'Music', hold: 'hold_guitar_electric', prop: 'prop_music_guitar_electric', line: "Handing me the axe, {n}? Name a deal and I'll write it a riff.", flirt: 'You handed me the guitar, {n}. Careful — everything I write tonight is about you.' },
  { id: 'mic_handheld', label: 'Mic', kind: 'Music', hold: 'hold_mic_handheld', prop: 'prop_music_mic_handheld', line: "Mic's live. Say the word, {n}, and I'll sing your numbers to the whole building.", flirt: 'Dedicating this one to you, {n}. Front row, best seat in the house, always yours.' },
  { id: 'headphones', label: 'Headphones', kind: 'Music', hold: 'hold_headphones', prop: 'prop_music_headphones', line: 'Cans on, world off — nothing in here but you and your pipeline, {n}.', flirt: "I could listen to anything, {n}, and I'd still rather listen to you." },
  { id: 'keytar', label: 'Keytar', kind: 'Music', hold: 'hold_keytar', prop: 'prop_music_keytar', line: "The keytar! Excellent taste, {n}. It's always been your best call.", flirt: "You picked the keytar. You've got dangerous taste, {n} — I like that in a woman." },
  { id: 'cowbell', label: 'Cowbell', kind: 'Music', hold: 'hold_cowbell', prop: 'prop_flair_cowbell', line: 'You know the rule, {n} — every meeting you book, I hit it.', flirt: "Every meeting you book, I hit it. Keep booking, {n} — I like the rhythm we've got." },
  { id: 'laptop', label: 'Laptop', kind: 'Business', hold: 'hold_laptop', prop: 'prop_biz_laptop', line: 'Laptop open, {n}. Point me at something and consider it done.', flirt: "All business, {n}? Fine. But you're the reason I stayed late." },
  { id: 'clipboard', label: 'Clipboard', kind: 'Business', hold: 'hold_clipboard', prop: 'prop_biz_clipboard', line: "Clipboard in hand. Tell me what we're chasing today, {n}.", flirt: "Give me the list, {n}. I'd do the boring half of your day just to be near you." },
  { id: 'document', label: 'RFP docs', kind: 'Business', hold: 'hold_document', prop: 'prop_biz_document_stack', line: "The RFP stack. You bring the instincts, {n}, I'll bring the paperwork.", flirt: "Paperwork's a love language if you do it right, {n}. Watch me." },
  { id: 'pointer', label: 'Pointer', kind: 'Business', hold: 'hold_pointer', prop: 'prop_biz_pointer', line: "Pointer out — walk me through it, {n}, and I'll keep up.", flirt: "Point anywhere you like, {n} — I'm already following you." },
  { id: 'coffee_mug', label: 'Coffee', kind: 'Business', hold: 'hold_coffee_mug', prop: 'prop_biz_coffee_mug', line: "Two coffees, {n}: this one's mine, the other's waiting for you.", flirt: 'Made you one, {n}. Two sugars, and an excuse to stand a bit closer.' },
  { id: 'sunglasses', label: 'Shades', kind: 'Flair', hold: 'hold_sunglasses', prop: 'prop_flair_sunglasses', line: "Shades on, {n} — your pipeline's blinding today.", flirt: "Shades on, {n} — a man's got to protect himself when you walk in like that." },
  { id: 'trophy', label: 'Trophy', kind: 'Flair', hold: 'hold_trophy', prop: 'prop_flair_trophy', line: "I keep this polished for you, {n}. The next one's got your name on it.", flirt: 'I keep it polished for you, {n}. Everything I win, I win to impress you.' },
  { id: 'confetti', label: 'Confetti', kind: 'Flair', hold: 'hold_confetti', prop: 'prop_flair_confetti', line: 'Say the word, {n}, and the whole lot goes in the air for you.', flirt: "Say the word, {n}, and it's raining on you. You've earned a hero's welcome." },
  // Stage looks — thumbnails are the poses themselves
  { id: 'stage_idle', label: 'Stage look', kind: 'Stage looks', hold: 'stage_idle', thumb: 'poses/matt_stage_idle.png',
    line: "Shirt off, confidence on — your call, {n}, and I'm not arguing.", flirt: "You took the shirt off me, {n}. Bold. I've never been more flattered." },
  { id: 'stage_guitar', label: 'Guitar', kind: 'Stage looks', hold: 'stage_guitar', thumb: 'poses/matt_stage_guitar.png',
    line: 'Unplugged tonight. Well — the shirt is, anyway.', flirt: "Unplugged, and looking right at you, {n}. This next one's slow." },
  { id: 'stage_solo', label: 'Solo', kind: 'Stage looks', hold: 'stage_solo', thumb: 'poses/matt_stage_solo.png',
    line: "One boot on the amp, {n} — that's just showbiz physics.", flirt: "Boot on the amp, eyes on you, {n}. The solo's yours — always was." },
  { id: 'stage_mic', label: 'Sing', kind: 'Stage looks', hold: 'stage_mic', thumb: 'poses/matt_stage_mic.png',
    line: 'This one goes out to the best closer in the room.', flirt: "This one goes out to the woman in the front row. That's you, {n}." },
  { id: 'stage_horns', label: 'Rock horns', kind: 'Stage looks', hold: 'stage_horns', thumb: 'poses/matt_stage_horns.png',
    line: '🤘 For those about to prospect, {n} — I salute you.', flirt: "🤘 Loud for the crowd, {n} — but I'm only playing for you." },
  { id: 'stage_towel', label: 'Post-show', kind: 'Stage looks', hold: 'stage_towel', thumb: 'poses/matt_stage_towel.png',
    line: "Great show tonight, {n}. Encore's whenever you are.", flirt: "Come backstage, {n}. Best after-party in town and you're the guest list." },
  { id: 'stage_bow', label: 'Take a bow', kind: 'Stage looks', hold: 'stage_bow', thumb: 'poses/matt_stage_bow.png',
    line: 'Take a bow with me — that pipeline of yours has earned it.', flirt: "Take the bow with me, {n}. They're clapping for you and I'm the one staring." },
  { id: 'stage_wave', label: 'Wave', kind: 'Stage looks', hold: 'stage_wave', thumb: 'poses/matt_stage_wave.png',
    line: 'Hello Cleveland! And far more importantly — hello {n}.', flirt: "Hello Cleveland — but really, hello {n}. You're why I came out here." },
  // Calendar shoot — campy 80s heartthrob tropes
  { id: 'cal_underwear', label: 'The Ad', kind: 'Calendar shoot', hold: 'cal_underwear', thumb: 'poses/matt_cal_underwear.png',
    line: '📅 Mr. January. The jeans are for dramatic effect, {n} — the savings sheets are still my best feature.', flirt: '📅 Mr. January, {n}, and you turned the page. The savings sheets are still my best feature — but you looked anyway.' },
  { id: 'cal_chippendale', label: 'Bowtie', kind: 'Calendar shoot', hold: 'cal_chippendale', thumb: 'poses/matt_cal_chippendale.png',
    line: '📅 Mr. February. Bowtie, cuffs, no shirt — formalwear where it counts.', flirt: '📅 Mr. February. Bowtie, cuffs, no shirt — dressed up entirely for you, {n}.' },
  { id: 'cal_firefighter', label: 'Firefighter', kind: 'Calendar shoot', hold: 'cal_firefighter', thumb: 'poses/matt_cal_firefighter.png',
    line: '📅 Mr. March. The hose is purely decorative, {n}. The dedication to your deals? Certified.', flirt: '📅 Mr. March. The hose is decorative, {n}. The way you walked in here is not.' },
  { id: 'cal_cowboy', label: 'Cowboy', kind: 'Calendar shoot', hold: 'cal_cowboy', thumb: 'poses/matt_cal_cowboy.png',
    line: "📅 Mr. April. This town's plenty big enough for both of us and your pipeline.", flirt: "📅 Mr. April. This town's big enough for both of us, {n} — but I'd rather it wasn't." },
  { id: 'cal_lifeguard', label: 'Lifeguard', kind: 'Calendar shoot', hold: 'cal_lifeguard', thumb: 'poses/matt_cal_lifeguard.png',
    line: '📅 Mr. May. Fully qualified in rescuing drowning deals.', flirt: '📅 Mr. May. Qualified in rescuing drowning deals, {n}, and completely out of my depth around you.' },
  { id: 'cal_mechanic', label: 'Mechanic', kind: 'Calendar shoot', hold: 'cal_mechanic', thumb: 'poses/matt_cal_mechanic.png',
    line: '📅 Mr. June. Checked under the hood, {n} — your funnel is running beautifully.', flirt: "📅 Mr. June. Checked under the hood, {n} — your funnel's purring. So am I." },
]

// Pack sections added as data:
// [pose key, label, Matt's one-liner, his flirty-vibe one-liner].
const PACKS = {
  'The Band': [
    ['instrument_electric_guitar', 'Electric', 'Standard tuning: E-A-D-G-Deal-Closed.', 'Standard tuning, {n}: E-A-D-G-and-you.'],
    ['instrument_acoustic_guitar', 'Acoustic', 'Unplugged set. Requests welcome, {n}.', "Just me and the acoustic, {n}. Sit closer, it's a quiet one."],
    ['instrument_bass', 'Bass', 'You take the melody, {n} — I will hold down everything underneath you.', "You take the melody, {n}. I'll be underneath, holding you up all night."],
    ['instrument_drums', 'Drums', 'Drums for you, {n}? Say when and I will play you in.', "Say when, {n}, and I'll play you in. My heart's already keeping the time."],
    ['instrument_keytar', 'Keytar', 'The keytar is BACK, {n} — and so is your pipeline.', 'The keytar is BACK, {n} — and so, apparently, is my nerve around you.'],
    ['instrument_saxophone', 'Sax', 'Careless Whisper mode engaged, {n}.', "Careless Whisper, {n}. I'm not even sorry."],
    ['instrument_trumpet', 'Trumpet', 'Taps, for the competition.', 'A fanfare, {n}. Every room you walk into should get one.'],
    ['instrument_trombone', 'Trombone', 'Big brass energy for big brass targets.', 'Big brass, big feelings, {n}. Mostly about you.'],
    ['instrument_violin', 'Violin', "The world's tiniest violin plays for the incumbent's renewal team.", "One violin, {n}, and it only knows one song. Guess who it's about."],
    ['instrument_cello', 'Cello', 'Something classical, since you picked it, {n}. A slow one for a big win.', 'Something slow and classical for you, {n}. Close your eyes.'],
    ['instrument_harp', 'Harp', 'The angel look, and you chose it for me, {n}. I will play something soft while you close.', "You made me an angel, {n}. Nobody's ever accused me of that before."],
    ['instrument_banjo', 'Banjo', 'Duelling banjos: me versus your quota. You win.', "Duelling banjos, {n} — you against my quota. I'd throw it to see you win."],
    ['instrument_harmonica', 'Harmonica', "The blues — for every deal marked 'lost'.", "The blues, {n}. Cure's simple: you, staying a bit longer."],
    ['instrument_accordion', 'Accordion', 'Only you could talk me into an accordion, {n} — and only you could make it work.', "Only you could talk me into this, {n}. That's the effect you have."],
    ['instrument_sitar', 'Sitar', 'My experimental phase, revived by popular demand. Well — by you, {n}.', 'My experimental phase, revived — by you, {n}. You bring it out of me.'],
  ],
  'Workout': [
    ['workout_dumbbells', 'Dumbbells', 'Curls for the closers, {n}.', "Curls for the closers, {n}. Someone's got to keep up with you."],
    ['workout_kettlebell', 'Kettlebell', 'Swinging heavy — like your win rate.', "Swinging heavy, {n} — still not the heaviest thing I've fallen for today."],
    ['workout_jump_rope', 'Jump rope', 'Cardio day. The pipeline never skips.', 'Cardio, {n}. Though honestly, you walking in does most of the work.'],
    ['workout_heavy_bag', 'Heavy bag', "This one's got the incumbent's name on it.", "This one's got the incumbent's name on it, {n}. Nobody upsets you and walks."],
    ['workout_stretch', 'Stretch', 'Always stretch before reaching for big quotas.', "Always stretch before reaching, {n}. I'm reaching well above my level here."],
  ],
  'Wildlife': [
    ['wildlife_falcon', 'Falcon', 'Trained to spot expiring contracts at 200 yards.', 'He spots an expiring contract at 200 yards, {n}. I spotted you at ten.'],
    ['wildlife_owl', 'Owl', 'The wise one says: follow up on Thursdays.', 'The wise one says follow up on Thursdays, {n}. I say ask you to lunch first.'],
    ['wildlife_macaw', 'Macaw', 'He only repeats the good bits, {n}, so he will be quoting you all day.', "He repeats the good bits, {n} — so he'll be quoting you all day. Join the club."],
    ['wildlife_fox', 'Fox', 'A fox recognizes a fox, {n}.', "A fox knows a fox, {n}. And you're the sharpest thing in this building."],
    ['wildlife_iguana', 'Iguana', "This is Iggy. Director of cold-blooded negotiation.", 'This is Iggy, {n}. Cold-blooded negotiator. Nothing like me around you.'],
    ['wildlife_python', 'Python', "The only python in this app that isn't running the backend.", "Careful, {n} — I'm the one who's wrapped around your finger."],
    ['wildlife_mantis', 'Mantis', 'She is praying for your prospects, {n}. Between the two of you they have got no chance.', "She's praying for your prospects, {n}. I'm just praying you stay for another one."],
    ['wildlife_butterflies', 'Butterflies', 'They followed you in here, {n}. I just happened to be standing still.', 'They followed you in, {n}. So did I. Same reason, frankly.'],
  ],
  'Off duty': [
    ['postshower_towel_neck', 'Fresh', 'Fresh out the shower and straight back to your pipeline, {n}. Commitment.', 'Straight out the shower and straight back to you, {n}. Priorities.'],
    ['postshower_dry_hair', 'Towel dry', 'Towel-dried and yours for the day, {n}. You dress me, I will draft the follow-ups.', "Give me twenty minutes on the hair, {n}, and I'll be worth looking at."],
    ['postshower_comb_hair', 'The comb', 'Doing the hair properly because you picked this one, {n}. Worth every second.', "Doing it properly, {n} — you picked this look, so somebody's got to earn it."],
    ['wood_axe_swing', 'Chop wood', 'Chopping wood, splitting quotas.', 'Chopping wood, splitting quotas, showing off. Mostly showing off, {n}.'],
    ['wood_log_carry', 'Haul logs', 'Heavy lifting is my department, {n}. The genius is yours.', "I'll carry the heavy end, {n}. You just walk ahead and let me watch."],
  ],
}
Object.entries(PACKS).forEach(([kind, items]) =>
  items.forEach(([hold, label, line, flirt]) => CLOSET.push({
    id: hold, label, kind, hold, line, flirt,
    thumb: `poses/matt_${hold}.png`,
  })))

export const CLOSET_KINDS = ['Music', 'Business', 'Flair', 'Stage looks',
  'Calendar shoot', 'The Band', 'Workout', 'Wildlife', 'Off duty']

export const KIND_ICONS = {
  Music: '🎸', Business: '💼', Flair: '✨', 'Stage looks': '🎤',
  'Calendar shoot': '📅', 'The Band': '🥁', Workout: '💪',
  Wildlife: '🦎', 'Off duty': '🛋️',
}

export const thumbSrc = (it) => it.thumb
  ? `/matt-frames/${it.thumb}` : `/matt-frames/props/${it.prop}.png`
