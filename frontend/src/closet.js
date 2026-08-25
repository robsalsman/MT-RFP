// Matt's closet — the single source of truth for every look he owns.
// Used by the ChatBot studio drawer AND the full-page Closet inventory.
// `hold` is his pose key in frames.json; `prop` a painted item thumbnail;
// `thumb` a full-pose thumbnail; `line` what he says when he puts it on.

export const CLOSET = [
  { id: 'guitar_electric', label: 'Guitar', kind: 'Music', hold: 'hold_guitar_electric', prop: 'prop_music_guitar_electric' },
  { id: 'mic_handheld', label: 'Mic', kind: 'Music', hold: 'hold_mic_handheld', prop: 'prop_music_mic_handheld' },
  { id: 'headphones', label: 'Headphones', kind: 'Music', hold: 'hold_headphones', prop: 'prop_music_headphones' },
  { id: 'keytar', label: 'Keytar', kind: 'Music', hold: 'hold_keytar', prop: 'prop_music_keytar' },
  { id: 'cowbell', label: 'Cowbell', kind: 'Music', hold: 'hold_cowbell', prop: 'prop_flair_cowbell' },
  { id: 'laptop', label: 'Laptop', kind: 'Business', hold: 'hold_laptop', prop: 'prop_biz_laptop' },
  { id: 'clipboard', label: 'Clipboard', kind: 'Business', hold: 'hold_clipboard', prop: 'prop_biz_clipboard' },
  { id: 'document', label: 'RFP docs', kind: 'Business', hold: 'hold_document', prop: 'prop_biz_document_stack' },
  { id: 'pointer', label: 'Pointer', kind: 'Business', hold: 'hold_pointer', prop: 'prop_biz_pointer' },
  { id: 'coffee_mug', label: 'Coffee', kind: 'Business', hold: 'hold_coffee_mug', prop: 'prop_biz_coffee_mug' },
  { id: 'sunglasses', label: 'Shades', kind: 'Flair', hold: 'hold_sunglasses', prop: 'prop_flair_sunglasses' },
  { id: 'trophy', label: 'Trophy', kind: 'Flair', hold: 'hold_trophy', prop: 'prop_flair_trophy' },
  { id: 'confetti', label: 'Confetti', kind: 'Flair', hold: 'hold_confetti', prop: 'prop_flair_confetti' },
  // Stage looks — thumbnails are the poses themselves
  { id: 'stage_idle', label: 'Stage look', kind: 'Stage looks', hold: 'stage_idle', thumb: 'poses/matt_stage_idle.png',
    line: "Shirt's in the wash, {n}. Professionalism fully intact." },
  { id: 'stage_guitar', label: 'Guitar', kind: 'Stage looks', hold: 'stage_guitar', thumb: 'poses/matt_stage_guitar.png',
    line: 'Unplugged tonight. Well — the shirt is, anyway.' },
  { id: 'stage_solo', label: 'Solo', kind: 'Stage looks', hold: 'stage_solo', thumb: 'poses/matt_stage_solo.png',
    line: "One boot on the amp, {n} — that's just showbiz physics." },
  { id: 'stage_mic', label: 'Sing', kind: 'Stage looks', hold: 'stage_mic', thumb: 'poses/matt_stage_mic.png',
    line: 'This one goes out to the best closer in the room.' },
  { id: 'stage_horns', label: 'Rock horns', kind: 'Stage looks', hold: 'stage_horns', thumb: 'poses/matt_stage_horns.png',
    line: '🤘 For those about to prospect, {n} — I salute you.' },
  { id: 'stage_towel', label: 'Post-show', kind: 'Stage looks', hold: 'stage_towel', thumb: 'poses/matt_stage_towel.png',
    line: "Great show tonight, {n}. Encore's whenever you are." },
  { id: 'stage_bow', label: 'Take a bow', kind: 'Stage looks', hold: 'stage_bow', thumb: 'poses/matt_stage_bow.png',
    line: 'Take a bow with me — that pipeline of yours has earned it.' },
  { id: 'stage_wave', label: 'Wave', kind: 'Stage looks', hold: 'stage_wave', thumb: 'poses/matt_stage_wave.png',
    line: 'Hello Cleveland! And far more importantly — hello {n}.' },
  // Calendar shoot — campy 80s heartthrob tropes
  { id: 'cal_underwear', label: 'The Ad', kind: 'Calendar shoot', hold: 'cal_underwear', thumb: 'poses/matt_cal_underwear.png',
    line: '📅 Mr. January. The jeans are for dramatic effect, {n} — the savings sheets are still my best feature.' },
  { id: 'cal_chippendale', label: 'Bowtie', kind: 'Calendar shoot', hold: 'cal_chippendale', thumb: 'poses/matt_cal_chippendale.png',
    line: '📅 Mr. February. Bowtie, cuffs, no shirt — formalwear where it counts.' },
  { id: 'cal_firefighter', label: 'Firefighter', kind: 'Calendar shoot', hold: 'cal_firefighter', thumb: 'poses/matt_cal_firefighter.png',
    line: '📅 Mr. March. The hose is purely decorative, {n}. The dedication to your deals? Certified.' },
  { id: 'cal_cowboy', label: 'Cowboy', kind: 'Calendar shoot', hold: 'cal_cowboy', thumb: 'poses/matt_cal_cowboy.png',
    line: "📅 Mr. April. This town's plenty big enough for both of us and your pipeline." },
  { id: 'cal_lifeguard', label: 'Lifeguard', kind: 'Calendar shoot', hold: 'cal_lifeguard', thumb: 'poses/matt_cal_lifeguard.png',
    line: '📅 Mr. May. Fully qualified in rescuing drowning deals.' },
  { id: 'cal_mechanic', label: 'Mechanic', kind: 'Calendar shoot', hold: 'cal_mechanic', thumb: 'poses/matt_cal_mechanic.png',
    line: '📅 Mr. June. Checked under the hood, {n} — your funnel is running beautifully.' },
]

// Pack sections added as data: [pose key, label, Matt's one-liner].
const PACKS = {
  'The Band': [
    ['instrument_electric_guitar', 'Electric', 'Standard tuning: E-A-D-G-Deal-Closed.'],
    ['instrument_acoustic_guitar', 'Acoustic', 'Unplugged set. Requests welcome, {n}.'],
    ['instrument_bass', 'Bass', "Somebody's got to hold down the low end of this pipeline."],
    ['instrument_drums', 'Drums', 'I also do the cowbell, but you knew that.'],
    ['instrument_keytar', 'Keytar', 'The keytar is BACK, {n} — and so is your pipeline.'],
    ['instrument_saxophone', 'Sax', 'Careless Whisper mode engaged, {n}.'],
    ['instrument_trumpet', 'Trumpet', 'Taps, for the competition.'],
    ['instrument_trombone', 'Trombone', 'Big brass energy for big brass targets.'],
    ['instrument_violin', 'Violin', "The world's tiniest violin plays for the incumbent's renewal team."],
    ['instrument_cello', 'Cello', 'Classically trained. Self-taught. Same thing.'],
    ['instrument_harp', 'Harp', "The angel look. Don't get used to it, {n}."],
    ['instrument_banjo', 'Banjo', 'Duelling banjos: me versus your quota. You win.'],
    ['instrument_harmonica', 'Harmonica', "The blues — for every deal marked 'lost'."],
    ['instrument_accordion', 'Accordion', 'Nobody looks cool playing the accordion. Nobody but me.'],
    ['instrument_sitar', 'Sitar', 'A little something from my experimental phase.'],
  ],
  'Workout': [
    ['workout_dumbbells', 'Dumbbells', 'Curls for the closers, {n}.'],
    ['workout_kettlebell', 'Kettlebell', 'Swinging heavy — like your win rate.'],
    ['workout_jump_rope', 'Jump rope', 'Cardio day. The pipeline never skips.'],
    ['workout_heavy_bag', 'Heavy bag', "This one's got the incumbent's name on it."],
    ['workout_stretch', 'Stretch', 'Always stretch before reaching for big quotas.'],
  ],
  'Wildlife': [
    ['wildlife_falcon', 'Falcon', 'Trained to spot expiring contracts at 200 yards.'],
    ['wildlife_owl', 'Owl', 'The wise one says: follow up on Thursdays.'],
    ['wildlife_macaw', 'Macaw', 'He repeats everything, {n} — mind the trade secrets.'],
    ['wildlife_fox', 'Fox', 'A fox recognizes a fox, {n}.'],
    ['wildlife_iguana', 'Iguana', "This is Iggy. Director of cold-blooded negotiation."],
    ['wildlife_python', 'Python', "The only python in this app that isn't running the backend."],
    ['wildlife_mantis', 'Mantis', "She's praying for your prospects. Someone should."],
    ['wildlife_butterflies', 'Butterflies', "They flock to charisma. Can't be taught."],
  ],
  'Off duty': [
    ['postshower_towel_neck', 'Fresh', 'Fresh out the shower and straight back to your pipeline, {n}. Commitment.'],
    ['postshower_dry_hair', 'Towel dry', 'The hair takes twenty minutes. The savings sheet takes two.'],
    ['postshower_comb_hair', 'The comb', 'Eighty percent of this job is hair maintenance.'],
    ['wood_axe_swing', 'Chop wood', 'Chopping wood, splitting quotas.'],
    ['wood_log_carry', 'Haul logs', "Carrying the whole load — so you don't have to."],
  ],
}
Object.entries(PACKS).forEach(([kind, items]) =>
  items.forEach(([hold, label, line]) => CLOSET.push({
    id: hold, label, kind, hold, line,
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
