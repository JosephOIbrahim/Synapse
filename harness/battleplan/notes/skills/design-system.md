<!-- Shipped 2026-09-03 for wave BP4 from the claude.ai plugin skill `design:design-system` (audit + document sections;
     the `extend` template and connector notes were not shipped - out of BP4-PANELFONT scope).
     Role: the AUDIT SHAPE the panel typography pass must produce. Numbers in the audit come from grep with file:line,
     never from memory. "No smaller than the Houdini default" is a MEASURED predicate - see the mission. -->

# /design-system

Manage your design system - audit for consistency, document components, or design new patterns.

## Components of a Design System

### Design Tokens
Atomic values that define the visual language:
- Colors (brand, semantic, neutral)
- Typography (scale, weights, line heights)
- Spacing (scale, component padding)
- Borders (radius, width)
- Shadows (elevation levels)
- Motion (durations, easings)

### Components
Reusable UI elements with defined:
- Variants (primary, secondary, ghost)
- States (default, hover, active, disabled, loading, error)
- Sizes (sm, md, lg)
- Behavior (interactions, animations)
- Accessibility (ARIA, keyboard)

### Patterns
Common UI solutions combining components:
- Forms (input groups, validation, submission)
- Navigation (sidebar, tabs, breadcrumbs)
- Data display (tables, cards, lists)
- Feedback (toasts, modals, inline messages)

## Principles

1. **Consistency over creativity** - The system exists so teams don't reinvent the wheel
2. **Flexibility within constraints** - Components should be composable, not rigid
3. **Document everything** - If it's not documented, it doesn't exist
4. **Version and migrate** - Breaking changes need migration paths

## Output - Audit

```markdown
## Design System Audit

### Summary
**Components reviewed:** [X] | **Issues found:** [X] | **Score:** [X/100]

### Naming Consistency
| Issue | Components | Recommendation |
|-------|------------|----------------|
| [Inconsistent naming] | [List] | [Standard to adopt] |

### Token Coverage
| Category | Defined | Hardcoded Values Found |
|----------|---------|----------------------|
| Colors | [X] | [X] instances of hardcoded hex |
| Spacing | [X] | [X] instances of arbitrary values |
| Typography | [X] | [X] instances of custom fonts/sizes |

### Component Completeness
| Component | States | Variants | Docs | Score |
|-----------|--------|----------|------|-------|
| Button | yes | yes | partial | 8/10 |
| Input | yes | partial | no | 5/10 |

### Priority Actions
1. [Most impactful improvement]
2. [Second priority]
3. [Third priority]
```

## Output - Document

```markdown
## Component: [Name]

### Description
[What this component is and when to use it]

### Variants
| Variant | Use When |
|---------|----------|
| [Primary] | [Main actions] |
| [Secondary] | [Supporting actions] |

### Props / Properties
| Property | Type | Default | Description |
|----------|------|---------|-------------|
| [prop] | [type] | [default] | [description] |

### States
| State | Visual | Behavior |
|-------|--------|----------|
| Default | [description] | - |
| Hover | [description] | [interaction] |
| Active | [description] | [interaction] |
| Disabled | [description] | Non-interactive |
| Loading | [description] | [animation] |

### Accessibility
- **Role**: [ARIA role]
- **Keyboard**: [Tab, Enter, Escape behavior]
- **Screen reader**: [Announced as...]

### Do's and Don'ts
| Do | Don't |
|----|-------|
| [Best practice] | [Anti-pattern] |

### Code Example
[Framework-appropriate code snippet]
```

## Tips

1. **Start with an audit** - Know where you are before deciding where to go.
2. **Document as you build** - It's easier to document a component while designing it.
3. **Prioritize coverage over perfection** - 80% of components documented beats 100% of 10 components.
