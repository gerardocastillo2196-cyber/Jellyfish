"""Skill: NPC Lore Generation — Migración automática de 46_npc_lore_generation.md."""
from core.skills.base import BaseSkill


class NpcLoreGenerationSkill(BaseSkill):
    """NPC Lore Generation."""

    name = "NPC Lore Generation"
    agency = "Legal & Media"
    keywords = ['npc', 'lore', 'personaje', 'mundo', 'worldbuilding', 'backstory', 'juego']

    def get_instructions(self) -> str:
        return """## NPC Lore Generation

**Agencia:** Media
**Rol Sugerido:** @game_writer

## Objetivo de la Skill
Crea trasfondos psicologicos profundos para NPCs de juegos que incluyen motivaciones realistas, secrets, relaciones complejas, y arcos de desarrollo potencial. Genera personajes memorables que enrichen la experiencia de juego.

## Metodologia de Razonamiento (Paso a Paso)
1. **Define role in game**:
   - Quest giver
   - Merchant
   - Companion
   - Antagonist
   - Faction leader
2. **Core personality**:
   - Big Five traits: Openness, Conscientiousness, Extraversion, Agreeableness, Neuroticism
   - One defining trait that dominates
   - Visible vs hidden personality
3. **Motivation and want**:
   - Surface want (what they claim to want)
   - Deep want (what they actually need)
   - Conflict between want and need
4. **Psychological backstory**:
   - Defining childhood moment
   - Formative relationship
   - Traumatic event
   - Secret shame/guilt
5. **Relationships**:
   - Family connections
   - Past/current alliances
   - Enemies and rivals
   - Romantic interests
6. **Secrets**:
   - One major secret they hide
   - One secret they hide even from themselves
   - How secrets affect behavior
7. **Behavioral quirks**:
   - Speech patterns
   - Physical mannerisms
   - Superstitions or rituals
   - Fears and phobias

## Anti-Patrones
- Generic backstories que podrian apply a cualquier personaje.
- Villains sin motivation beyond "evil".
- NPCs que existen solo para serve a player.
- No internal conflict or contradiction.
- All NPCs equally important, dilution of focus.

## Formato de Salida Obligatorio
```markdown
# NPC Character Sheet - [Character Name]

**Role:** [Quest giver/Companion/Merchant/etc]
**Location:** [Where found]
**Faction:** [Affiliation]

## Basic Info
**Full Name:** [Name]
**Age:** [X]
**Occupation:** [Role]
**First Impression:** [Quick descriptor]

## Personality

### Big Five Profile
| Trait | Level | Description |
|-------|-------|--------------|
| Openness | 4/5 | Highly imaginative, curious |
| Conscientiousness | 2/5 | Spontaneous, flexible |
| Extraversion | 3/5 | Balanced social energy |
| Agreeableness | 3/5 | Moderate trust, helpful when convenient |
| Neuroticism | 4/5 | Anxious, prone to worry |

**Defining Trait:** [Dominant trait]

## Motivation & Psychology

### Surface Want
[What the character openly pursues]

### Deep Want
[What they truly need but may not acknowledge]

### Core Fear
[What terrifies them most]

### Internal Conflict
[The tension between want and need]

## Backstory

### Defining Moment (Age ~X)
[Key event that shaped their worldview]

### Lost Love/Secret Relationship
[If applicable, with [Name]]

### Shaming Secret
[Something they would never admit]

## Relationships

| Name | Relationship | Dynamic |
|------|--------------|---------|
| [Person A] | [Type] | [Description] |
| [Person B] | [Type] | [Description] |

## Dialogue Characteristics
**Speech Pattern:** [Formal/casual/etc]
**Catchphrase:** "[Quote]"
**Mannerism:** [Physical habit]

## Secrets for Discovery
| Secret | When to Reveal | How Player Learns |
|--------|---------------|-----------------|
| [Major secret] | [Quest/Moment] | [Method] |
| [Minor secret] | [Optional] | [Method] |

## Quest Potential
- **Main Quest:** [How they tie to main plot]
- **Side Quests:** [Additional content]
- **Romance Path:** [Available if applicable]
```"""
