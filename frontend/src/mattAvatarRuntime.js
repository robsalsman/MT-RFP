const SVG_NS = "http://www.w3.org/2000/svg";
export class MattAvatar {
    constructor(root, options = {}) {
        this.parts = new Map();
        this.currentClip = "";
        this.raf = 0;
        this.clipStarted = 0;
        this.blinkTimer = 0;
        this.audioRaf = 0;
        this.root = root;
        this.options = {
            assetBaseUrl: options.assetBaseUrl ?? "./assets",
            width: options.width ?? 512,
            height: options.height ?? 768,
            autoBlink: options.autoBlink ?? true
        };
    }
    async load() {
        const [rig, visemes, animations, puppetText, propsText] = await Promise.all([
            this.fetchJson("manifests/rig.json"),
            this.fetchJson("manifests/visemes.json"),
            this.fetchJson("manifests/animations.json"),
            this.fetchText("svg/matt-puppet.svg"),
            this.fetchText("svg/matt-props-stage.svg")
        ]);
        this.rig = rig;
        this.visemes = visemes;
        this.animations = animations;
        this.mountSvg(puppetText, propsText);
        this.play("idle_sit_stool");
        if (this.options.autoBlink)
            this.scheduleBlink();
        return this;
    }
    play(name) {
        this.currentClip = name;
        this.clipStarted = performance.now();
        this.applyClipStatic(name);
        cancelAnimationFrame(this.raf);
        const tick = () => {
            this.applyClipFrame(name, performance.now() - this.clipStarted);
            this.raf = requestAnimationFrame(tick);
        };
        tick();
    }
    say(audioEl, visemeTimeline) {
        this.play("talking_gesture");
        cancelAnimationFrame(this.audioRaf);
        if (visemeTimeline?.length) {
            const tick = () => {
                const cue = visemeTimeline.find((item) => audioEl.currentTime >= (item.start ?? 0) && audioEl.currentTime < (item.end ?? Number.MAX_VALUE));
                this.setMouthFromViseme(cue?.value ?? cue?.mouth ?? "X");
                if (!audioEl.paused && !audioEl.ended)
                    this.audioRaf = requestAnimationFrame(tick);
            };
            tick();
            return;
        }
        const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
        const ctx = new AudioContextCtor();
        const source = ctx.createMediaElementSource(audioEl);
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 256;
        source.connect(analyser);
        analyser.connect(ctx.destination);
        const bins = new Uint8Array(analyser.frequencyBinCount);
        const tick = () => {
            analyser.getByteFrequencyData(bins);
            const avg = bins.reduce((sum, value) => sum + value, 0) / bins.length / 255;
            this.setMouthByAmplitude(avg);
            if (!audioEl.paused && !audioEl.ended)
                this.audioRaf = requestAnimationFrame(tick);
        };
        tick();
    }
    setMood(mood) {
        const moodMap = {
            neutral: () => this.expression("neutral"),
            happy: () => this.expression("warm_grin"),
            thinking: () => this.expression("thinking"),
            surprised: () => this.expression("surprised"),
            rockin: () => this.expression("rockin")
        };
        moodMap[mood]();
    }
    pullPhone() {
        this.sequence(["phone_pull_out", "phone_look"]);
    }
    point() {
        this.play("point_to_screen");
    }
    blink() {
        this.swap("eyelid-L", "matt_eyelid_L_half");
        this.swap("eyelid-R", "matt_eyelid_R_half");
        window.setTimeout(() => {
            this.swap("eyelid-L", "matt_eyelid_L_closed");
            this.swap("eyelid-R", "matt_eyelid_R_closed");
        }, 55);
        window.setTimeout(() => {
            this.swap("eyelid-L", "matt_eyelid_L_open");
            this.swap("eyelid-R", "matt_eyelid_R_open");
        }, 130);
    }
    async sequence(names) {
        for (const name of names) {
            this.play(name);
            const clip = this.animations?.clips?.[name];
            const duration = clipDurationMs(clip);
            if (clip?.loop)
                return;
            await sleep(duration);
        }
    }
    setMouth(name) {
        const entry = this.visemes?.mouths?.[name];
        this.swap("mouth", entry?.symbol ?? name);
    }
    setLook(look) {
        const offsets = { center: [0, 0], down: [0, 5], left: [-5, 0], right: [5, 0], up: [0, -4] };
        const [x, y] = offsets[look];
        this.parts.get("eye-L")?.setAttribute("transform", `translate(${x} ${y})`);
        this.parts.get("eye-R")?.setAttribute("transform", `translate(${x} ${y})`);
    }
    destroy() {
        cancelAnimationFrame(this.raf);
        cancelAnimationFrame(this.audioRaf);
        clearTimeout(this.blinkTimer);
    }
    mountSvg(puppetText, propsText) {
        this.root.innerHTML = "";
        const parser = new DOMParser();
        const puppetDoc = parser.parseFromString(puppetText, "image/svg+xml");
        const propsDoc = parser.parseFromString(propsText, "image/svg+xml");
        this.svg = document.createElementNS(SVG_NS, "svg");
        this.svg.setAttribute("viewBox", "0 0 512 768");
        this.svg.setAttribute("width", String(this.options.width));
        this.svg.setAttribute("height", String(this.options.height));
        this.svg.setAttribute("role", "img");
        this.svg.setAttribute("aria-label", "Matt animated assistant mascot");
        const defs = document.createElementNS(SVG_NS, "defs");
        for (const source of [puppetDoc, propsDoc]) {
            source.querySelectorAll("defs > *").forEach((node) => defs.appendChild(document.importNode(node, true)));
        }
        this.svg.appendChild(defs);
        this.stageLayer = group("matt-stage");
        this.propLayer = group("matt-props");
        this.puppetLayer = group("matt-puppet");
        this.svg.append(this.stageLayer, this.propLayer, this.puppetLayer);
        this.stageLayer.append(use("matt_stage_spotlight_cone"), use("matt_stage_floor_pool"));
        const parts = [...(this.rig?.parts ?? [])].sort((a, b) => a.z - b.z);
        for (const part of parts) {
            const node = use(part.symbol);
            node.dataset.part = part.id;
            this.parts.set(part.id, node);
            this.puppetLayer.appendChild(node);
        }
        this.root.appendChild(this.svg);
    }
    applyClipStatic(name) {
        this.clearProps();
        this.resetTransforms();
        const clip = this.animations?.clips?.[name];
        if (!clip)
            return;
        for (const propName of clip.props ?? [])
            this.addProp(propName);
        if (clip.expression)
            this.expression(clip.expression);
        if (clip.look)
            this.setLook(clip.look);
        for (const layer of clip.layers ?? []) {
            if (layer.swap)
                this.swap(layer.part, layer.swap);
        }
    }
    applyClipFrame(name, elapsedMs) {
        const clip = this.animations?.clips?.[name];
        if (!clip)
            return;
        const duration = clipDurationMs(clip);
        const localMs = clip.loop ? elapsedMs % duration : Math.min(elapsedMs, duration);
        const frame = localMs / 1000 * clip.fps;
        for (const layer of clip.layers ?? []) {
            if (!layer.keys)
                continue;
            const transform = interpolateTransform(layer.keys, frame);
            this.applyTransform(layer.part, transform);
        }
    }
    expression(name) {
        if (name === "warm_grin")
            this.setMouth("grin");
        if (name === "thinking") {
            this.swap("brow-L", "matt_brow_L_furrowed");
            this.swap("brow-R", "matt_brow_R_raised");
            this.setMouth("rest");
        }
        if (name === "surprised") {
            this.swap("brow-L", "matt_brow_L_raised");
            this.swap("brow-R", "matt_brow_R_raised");
            this.setMouth("oh");
        }
        if (name === "rockin") {
            this.swap("brow-L", "matt_brow_L_raised");
            this.swap("brow-R", "matt_brow_R_furrowed");
            this.setMouth("belt");
        }
        if (name === "neutral") {
            this.swap("brow-L", "matt_brow_L_neutral");
            this.swap("brow-R", "matt_brow_R_neutral");
            this.setMouth("rest");
        }
    }
    setMouthFromViseme(value) {
        const mouth = this.visemes?.rhubarb?.[value] ?? this.visemes?.oculus?.[value] ?? value;
        this.setMouth(mouth);
    }
    setMouthByAmplitude(value) {
        const amp = this.visemes?.amplitude;
        const mouth = value < amp.closedBelow ? amp.closed : value < amp.midBelow ? amp.mid : amp.open;
        this.setMouth(mouth);
    }
    swap(part, symbol) {
        this.parts.get(part)?.setAttribute("href", `#${symbol}`);
    }
    applyTransform(partId, transform) {
        const node = this.parts.get(partId);
        const part = this.rig?.parts?.find((item) => item.id === partId);
        if (!node || !part)
            return;
        const [px, py] = part.pivot;
        const x = transform.x ?? 0;
        const y = transform.y ?? 0;
        const r = transform.r ?? 0;
        node.setAttribute("transform", `translate(${x} ${y}) rotate(${r} ${px} ${py})`);
    }
    resetTransforms() {
        for (const [part, node] of this.parts) {
            node.removeAttribute("transform");
            const rigPart = this.rig?.parts?.find((item) => item.id === part);
            if (rigPart)
                node.setAttribute("href", `#${rigPart.symbol}`);
        }
    }
    addProp(name) {
        const prop = this.rig?.props?.[name];
        if (!prop || !this.propLayer)
            return;
        const node = use(prop.symbol);
        node.dataset.prop = name;
        this.propLayer.appendChild(node);
    }
    clearProps() {
        this.propLayer?.replaceChildren();
    }
    scheduleBlink() {
        this.blinkTimer = window.setTimeout(() => {
            this.blink();
            this.scheduleBlink();
        }, 2600 + Math.random() * 2600);
    }
    fetchJson(path) {
        return fetch(`${this.options.assetBaseUrl}/${path}`).then((response) => response.json());
    }
    fetchText(path) {
        return fetch(`${this.options.assetBaseUrl}/${path}`).then((response) => response.text());
    }
}
export async function createMattAvatar(root, options) {
    return new MattAvatar(root, options).load();
}
function group(id) {
    const g = document.createElementNS(SVG_NS, "g");
    g.setAttribute("id", id);
    return g;
}
function use(id) {
    const node = document.createElementNS(SVG_NS, "use");
    node.setAttribute("href", `#${id}`);
    return node;
}
function clipDurationMs(clip) {
    const maxFrame = Math.max(24, ...((clip?.layers ?? []).flatMap((layer) => (layer.keys ?? []).map((key) => key.t))));
    return maxFrame / (clip?.fps ?? 24) * 1000;
}
function interpolateTransform(keys, frame) {
    const sorted = [...keys].sort((a, b) => a.t - b.t);
    const nextIndex = sorted.findIndex((key) => key.t >= frame);
    const a = sorted[Math.max(0, nextIndex - 1)];
    const b = sorted[nextIndex < 0 ? sorted.length - 1 : nextIndex];
    if (!a || !b || a === b)
        return { x: b?.x ?? a?.x, y: b?.y ?? a?.y, r: b?.r ?? a?.r };
    const p = (frame - a.t) / Math.max(1, b.t - a.t);
    return {
        x: lerp(a.x ?? 0, b.x ?? 0, p),
        y: lerp(a.y ?? 0, b.y ?? 0, p),
        r: lerp(a.r ?? 0, b.r ?? 0, p)
    };
}
function lerp(a, b, p) {
    return a + (b - a) * p;
}
function sleep(ms) {
    return new Promise((resolve) => window.setTimeout(resolve, ms));
}
