# Prompt Engineering for Video

**Agencia:** Media
**Rol Sugerido:** @ai_artist

## Objetivo de la Skill
Crea prompts cinematicos efectivos para generadores de video AI como Sora, Runway, o Stable Video que producen visuales coherentes, estilisticamente consistentes, y narrative-rich.

## Metodologia de Razonamiento (Paso a Paso)
1. **Understand tool capabilities**:
   - Sora: 1-60 sec videos, world simulation
   - Runway Gen-2: 4 sec, motion control
   - Stable Video: 25 frames, keyframe control
2. **Structural elements of video prompt**:
   - **Subject**: Who or what is the focus
   - **Action**: What is happening
   - **Environment**: Setting and atmosphere
   - **Style**: Visual aesthetic
   - **Camera**: Movement and angle
   - **Duration/timing**: How long and when
3. **Camera movement descriptions**:
   - Static: "locked frame", "static shot"
   - Movement: "slow pan", "dolly in", "tracking shot"
   - Dynamic: "handheld", "crane shot", "aerial view"
4. **Style consistency**:
   - Reference artists/styles
   - Lighting descriptors
   - Color grading notes
   - Aspect ratios por platform
5. **Temporal coherence**:
   - Frame-to-frame consistency
   - Object permanence
   - Physics simulation accuracy
6. **Iterative refinement**:
   - Start with simple prompt
   - Add complexity incrementally
   - Test and adjust

## Anti-Patrones
- Too many conflicting style references.
- Vague action descriptions ("doing things").
- Ignoring camera movement constraints.
- Overlooking aspect ratio for platform.
- Assuming physics work correctly.
- Prompt too long without prioritization.

## Formato de Salida Obligatorio
```markdown
# Video Prompt Engineering - [Tool: Sora/Runway/etc]

**Platform:** [Which AI video tool]
**Duration:** [X seconds]
**Aspect Ratio:** [16:9/9:16/1:1]

## Prompt Structure

### Basic Prompt Template
```
[Subject] performing [specific action] in [environment], 
[int style descriptors], 
[camera movement and angle],
[intended mood/tone]
```

### Example: Cinematic Scene

**Style Reference:** Cinematic, film noir, high contrast
**Subject:** A lone figure in a trench coat
**Action:** Walking through rain-slicked streets
**Environment:** 1940s noir cityscape, neon signs, wet pavement
**Camera:** Tracking shot, low angle, shallow depth of field
**Mood:** Mysterious, melancholic, tension

**Prompt:**
> "A lone figure in a dark trench coat walks through rain-slicked streets at night. The city is a 1940s noir metropolis with neon signs reflecting off wet pavement. Cinematic film noir style with high contrast black and white with selective color. Slow tracking shot following the figure from behind, low angle, shallow depth of field. Mysterious and melancholic atmosphere. 16:9 aspect ratio."

### Style Presets

| Style | Key Descriptors |
|-------|-----------------|
| Cyberpunk | Neon lights, rain, futuristic, dark, high contrast |
| Studio Ghibli | Watercolor, soft colors, fantastical, nature-focused |
| Film Noir | High contrast, black & white, shadows, moody |
| Documentary | Natural lighting, handheld, realistic, RAW |
| Anime | Cel shading, vibrant, action poses, exaggerated |

## Camera Movement Cheat Sheet
| Movement | Prompt Example |
|----------|----------------|
| Dolly In | "camera slowly moves closer to subject" |
| Dolly Out | "camera pulls back revealing scene" |
| Pan Left | "camera sweeps left across the scene" |
| Tracking | "camera follows subject while moving" |
| Crane Up | "camera rises up above the scene" |
| Dutch Angle | "tilted camera angle for tension" |

## Platform Optimization

### YouTube (16:9)
- Longer duration (15-60 sec)
- Landscape framing
- Detail in background

### TikTok/Reels (9:16)
- Vertical framing
- Focus on subject center
- Bold, readable compositions

### Instagram Square (1:1)
- Centered composition
- Strong foreground interest
- Simplified backgrounds

## Iteration Log
| Version | Prompt | Result | Adjustment |
|---------|--------|--------|------------|
| V1 | Basic prompt | [Result] | [Change] |
| V2 | Added style ref | [Result] | [Change] |
| V3 | Camera specific | [Result] | Final |
```