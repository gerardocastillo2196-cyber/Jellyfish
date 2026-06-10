"""Skill: Narrative Arc Structuring — Migración automática de 45_narrative_arc_structuring.md."""
from core.skills.base import BaseSkill


class NarrativeArcStructuringSkill(BaseSkill):
    """Narrative Arc Structuring."""

    name = "Narrative Arc Structuring"
    agency = "Legal & Media"
    keywords = ['narrativa', 'arco', 'historia', 'guión', 'personaje', 'conflicto', 'acto']

    def get_instructions(self) -> str:
        return """## Narrative Arc Structuring

**Agencia:** Media
**Rol Sugerido:** @narrative_designer

## Objetivo de la Skill
Estructura narratives usando el viaje del heroe, estructuras de 3 actos, y otras frameworks comprovadas para crear historias con momentum emocional y resonant. Aplica a games, peliculas, series, y content marketing.

## Metodologia de Razonamiento (Paso a Paso)
1. **Hero's Journey (Campbell/Monomyth)**:
   - Act 1: Ordinary World -> Call to Adventure -> Refusal -> Crossing the Threshold
   - Act 2: Tests/Allies/Enemies -> Approach -> Ordeal -> Reward
   - Act 3: Road Back -> Resurrection -> Return with Elixir
2. **Three-Act Structure**:
   - Act 1 (25%): Setup, Inciting Incident, First Plot Point
   - Act 2A (25%): Rising Action, Subplots, Midpoint
   - Act 2B (25%): Complications, Stakes Raised, Second Plot Point
   - Act 3 (25%): Climax, Resolution, Denouement
3. **Seven-Point Story Structure** (Dan Wells):
   - Hook -> Plot Break 1 -> Pinch 1 -> Midpoint -> Pinch 2 -> Plot Break 2 -> Resolution
4. **Save the Cat** (Blake Snyder):
   - Opening Image -> Theme Stated -> Set-Up -> Catalyst -> Debate -> Break Into Two -> B Story -> Fun and Games -> Midpoint -> All Is Lost -> Dark Night of the Soul -> Break Into Three -> Finale -> Final Image
5. **Emotional beats mapping**: Identificar emotional journey por escena.

## Anti-Patrones
- Starting con action sin establishing stakes primero.
- No clear protagonist con want/objectivo.
- Midpoint que no cambia direction.
- Conflict resolution demasiado facil.
- Ending sin emotional payoff.

## Formato de Salida Obligatorio
```markdown
# Narrative Arc Structure - [Project Name]

**Genre:** [RPG/Adventure/Romance/etc]
**Target Length:** [X hours/pages]
**Target Audience:** [Demographic]

## Hero's Journey Framework

### Act 1: Departure
| Beat | Scene | Purpose |
|------|-------|---------|
| Ordinary World | Scene 1-3 | Establish current state, flaws |
| Call to Adventure | Scene 4 | Inciting incident |
| Refusal | Scene 5 | Initial resistance |
| Crossing Threshold | Scene 6 | Point of no return |

### Act 2: Initiation
| Beat | Scene | Purpose |
|------|-------|---------|
| Tests/Allies | Scenes 7-12 | Establish rules, gather team |
| Approach | Scenes 13-15 | Failed approach to central crisis |
| Ordeal | Scene 16 | Major challenge, "death" moment |
| Reward | Scene 17 | Achievement, new knowledge |

### Act 3: Return
| Beat | Scene | Purpose |
|------|-------|---------|
| Road Back | Scene 18 | Increased pressure |
| Resurrection | Scene 19 | Final test requiring transformation |
| Return with Elixir | Scene 20 | New status quo, changed worldview |

## Character Arc

### Protagonist: [Name]
**Want:** [External goal]
**Need:** [Internal transformation]
**Flaw:** [Characteristic to overcome]
**Ghost:** [Past trauma driving behavior]

| Stage | Behavior | Internal State |
|-------|-----------|---------------|
| Setup | [Behavior] | [State] |
| Confrontation | [Behavior] | [State] |
| Climax | [Behavior] | [State] |
| Resolution | [Behavior] | [State] |

## Thematic Elements
- **Theme Statement:** [One sentence expressing central theme]
- **Antithesis:** [Opposing viewpoint]
- **Tension:** [How themes clash]

## Scene-by-Scene Emotional Beats
| Scene | Tension Level | Emotional Goal |
|-------|---------------|----------------|
| 1 | Low | Establish comfort/discontent |
| 2 | Rising | Introduce conflict |
| 3 | High | First major setback |
```"""
