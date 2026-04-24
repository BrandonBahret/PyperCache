# Atlas Docs Format — Directory Specification

A structured directory format for generating rich, single-page documentation sites from plain Markdown source files. A generator reads this directory and emits a self-contained HTML file with sidebar navigation, section-based routing, cross-section linking, themed typography, and optional interactive blocks.

---

## Directory Layout

```
my-docs/
├── metadata.md        # Project identity, theme, typography
├── navigation.md      # Sidebar structure and section wiring
├── assets.md          # SVG icons, image paths, external graphical assets
└── content/           # One .md file per section
    ├── introduction.md
    ├── quickstart.md
    └── api-reference.md
```

The generator processes the four control files first, then compiles each content file in the order navigation.md declares them.

---

## `metadata.md`

Defines the identity and visual system for the entire site. All fields live in YAML frontmatter; there is no prose body in this file.

```md
---
# ── Identity ──────────────────────────────────────────────
name: PyperCache
version: v0.1.6
tagline: Durable cache for JSON-like data

# ── Theme ─────────────────────────────────────────────────
# accent is the shared fallback brand color — used for active nav items,
# callout borders, card titles, interactive highlights, and the
# version pill badge. Accepts any CSS color value.
accent: "#c8f060"

# Optional mode-specific overrides. When present, these replace `accent`
# for the matching color scheme while preserving `accent` as the fallback.
accent_dark: "#c8f060"
accent_light: "#7d9f20"

# Dark mode is the default. Set to "light" to invert the palette.
color_scheme: dark

# ── Typography ────────────────────────────────────────────
# display_font appears in the logo name, page titles (h1), and
# section headers (h2). Choose a serif or display face for contrast.
display_font: "Fraunces"

# body_font is used for all prose paragraphs and UI chrome.
body_font: "DM Sans"

# mono_font is used for code blocks, nav group labels, badges,
# API signatures, table headers, and inline metadata chips.
mono_font: "IBM Plex Mono"

# Google Fonts is the assumed CDN. Provide the full embed URL if
# you need custom weights or a non-Google source.
font_source: "https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:ital,wght@0,400;0,500;0,600;1,400&family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,400;0,9..144,600;1,9..144,300&family=DM+Sans:wght@300;400;500&display=swap"

# ── External links ─────────────────────────────────────────
# search_trigger_label is the compact hint shown in the topbar search button.
search_trigger_label: "docs, guides, examples..."

# search_placeholder appears inside the search input once the modal opens.
search_placeholder: "Search local docs..."

# search_secondary_hint is the empty-state hint shown under the search input.
search_secondary_hint: "Search the local docs. Try docs, guides, examples."

features:
  search: true
---
```

### Visual semantics of each field

`accent` flows throughout the generated site as `--accent` in CSS: the sidebar active-link indicator, left border on callout blocks, card hover states, the version badge background, and focus ring on interactive elements. Use it as the shared fallback when both modes can use the same color.

`accent_dark` and `accent_light` let you tune that same semantic accent independently for each palette. If one is missing, Atlas falls back to `accent` for that mode.

`display_font` sets the editorial voice. It appears large on page titles and rendered with `font-weight: 300` for an elegant, lightweight feel. The logo name uses the same face at `font-weight: 600`.

`mono_font` carries all structured metadata: nav group labels, table `th` cells, API method signatures, badge pills, and code fence content. It should be a legible monospace with clear number-letter distinction.

---

## `navigation.md`

Defines the sidebar structure. Each nav group becomes a labeled section in the left rail. Each entry within a group maps a human-readable label to a content file and optionally to an external URL. An optional `footer` block controls the sidebar footer; when `footer` is omitted, Atlas renders nothing there.

```md
---
# Groups appear in order. Each entry becomes a sidebar nav link.
# Format per entry:
#   label | path | [external]
#
# `path` is relative to content/ and without the .md extension.
# Use `external: true` for links that open in a new tab (e.g. GitHub).
groups:
  - label: Overview
    entries:
      - Introduction | introduction
      - Changelog | changelog

  - label: Tutorials
    entries:
      - JSONPlaceholder walkthrough | tutorial-jsonplaceholder

  - label: Using the Cache
    entries:
      - Store & retrieve data | cache-basics
      - Storage backends | storage-backends

  - label: API Clients
    entries:
      - ApiWrapper | api-wrapper
      - Lower-level pieces | building-blocks
      - Typed models | typed-models

  - label: Query Layer
    entries:
      - JsonInjester | json-injester
      - Selector syntax | selector-guide

  - label: Reference
    entries:
      - Cache API | ref-cache
      - ApiWrapper API | ref-apiwrapper
      - "@apimodel API" | ref-apimodel
      - Storage & logging | ref-storage

footer:
  label: Project
  entries:
    - GitHub | https://github.com/yourname/yourproject | external
    - PyPI | https://pypi.org/project/pypercache/ | external
---
```

If you do not want a footer, omit the `footer` block entirely.

### Rendering behavior

Each group label renders as a small-caps uppercase mono label above its set of links (e.g. `USING THE CACHE`). Each entry renders as a dot + label row. The dot and left border both adopt the accent color when the entry is active. External entries get `target="_blank"` and do not participate in section routing.

Footer entries use the same pipe syntax and rendering rules as main navigation entries, but render inside `.sidebar-footer` instead of the primary nav stack. Atlas does not infer footer links from `metadata.md`.

The first non-external entry in the first group is the default visible section on load.

### Cross-section links in content

In any content file you can link to another section by its content file slug using the `[doc:slug]` shorthand:

```md
See [doc:api-wrapper] for the full request() signature.
```

The generator expands this into a styled inline link that triggers section navigation without a page reload. The link text defaults to the label defined in navigation.md for that slug. You can override the text:

```md
See [the wrapper docs | doc:api-wrapper] for details.
```

To link to a specific subsection inside a page, append `#anchor` to the slug:

```md
See [request caching rules | doc:ref-apiwrapper#request] for the exact behavior.
```

---

## `assets.md`

A catalog of graphical assets that content files can reference by a short name, keeping raw SVG and long image paths out of prose. The generator embeds or links each asset at build time.

```md
---
# Inline SVGs are embedded directly into the HTML. Prefer this for
# icons and small decorative marks where HTTP round-trips add latency.
# Format: name | svg_path
svgs:
  - logo-mark | ./assets/logo-mark.svg
  - cache-icon | ./assets/cache-icon.svg
  - arrow-right | ./assets/arrow-right.svg

# Images are copied into the output bundle and referenced by URL.
# Format: name | file_path | [alt text]
images:
  - architecture-diagram | ./assets/arch.png | System architecture overview
  - cache-flow | ./assets/cache-flow.png | Cache read/write flow

# External image URLs are referenced as-is (not bundled).
# Format: name | url | [alt text]
remote_images:
  - pypi-badge | https://img.shields.io/pypi/v/pypercache | PyPI version
---
```

### Referencing assets in content

In any content file, insert an asset by name using the `@asset` directive:

```md
@asset[logo-mark]
@asset[architecture-diagram]
```

SVGs render inline. Images render as `<img>` with the declared alt text. This keeps content files free of raw HTML while still allowing custom graphics.

---

## `content/` — Section Files

Each `.md` file in `content/` maps to exactly one sidebar entry and one navigable section in the generated HTML. The slug used in navigation.md must match the filename (without `.md`).

### Frontmatter

```md
---
# tag appears above the page title in small accent-colored mono type.
# Use it as a category hint, e.g. "Getting started", "Reference", "Tutorials".
tag: Getting started

# title is the large display-font page heading (h1).
title: PyperCache

# title_em optionally italicizes a portion of the title in the accent color.
# It appends to `title` as styled text.
title_em: "."

# lead is the subtitle paragraph rendered below the title in a lighter weight.
lead: |
  A durable, file-backed cache for JSON-like Python data — with optional
  typed hydration, a query layer for navigating nested payloads, and an
  `ApiWrapper` base class for building HTTP clients.

# breadcrumb overrides the topbar path label for this section.
# Defaults to: project_name / section_label
breadcrumb: "pypercache / introduction"
---
```

### Prose and headings

Plain Markdown is rendered as expected. Headings follow a deliberate visual hierarchy:

| Heading | Rendered as | Style purpose |
|---------|-------------|---------------|
| `## Section name` | `<h2>` — display font, 26px | Major topic within a page |
| `### Subsection` | `<h3>` — mono font, 13px, uppercase, accent2 color | API subgroup or named subcategory |
| `#### Detail` | `<h4>` — body font, 15px, medium weight | Inline detail heading |

Do not use `# H1` in content files — the generator synthesizes the `<h1>` from the frontmatter `title` field.

Atlas assigns stable IDs to `##`, `###`, and `####` headings using the pattern `section-slug-anchor`. You can override the anchor token explicitly by suffixing the heading with `{id=...}`:

```md
## Request options {id=request}
#### get_object {id=get-object}
```

Those headings can then be targeted from cross-section links or inline refs with `#request` or `#get-object`.

### Code blocks

Fenced code blocks with a language tag render with syntax token classes and a copy button:

````md
```python
cache.store("user:1", {"name": "Alice"}, expiry=3600)
```
````

The language label appears in the top-right corner of the block and fades out when the copy button appears on hover.

For inline code references that should link on `Ctrl`/`Cmd`+click, suffix the backtick span with `{ref=slug}`:

```md
Call `cache.store(){ref=ref-cache}` to persist a record.
```

When the useful context is a specific subsection rather than the page top, target an anchor directly:

```md
Call `cache.store(){ref=ref-cache#store}` to jump straight to the `store` reference.
Use `Alias{ref=ref-apimodel#alias}` when the upstream payload uses a different key name.
```

---

## Custom Layout Blocks

Beyond prose and code, content files support a set of `:::` directive blocks. Each block opens with `:::block_type [attributes]` and closes with `:::`. Blocks can contain Markdown prose, sub-items delimited by `###`, or nested code fences.

---

### `:::hero`

Renders the page header (tag, title, lead). The generator synthesizes this automatically from frontmatter — you do not need to write it manually. It is documented here for completeness in case you want to suppress auto-generation with `hero: false` in frontmatter and write a custom hero block inline.

---

### `:::feature_grid`

A two-column icon-and-text grid for summarizing capabilities. Rendered with a surface background and subtle border. Items use `###` headings with an `icon` attribute.

```md
:::feature_grid
### Persistent storage {icon=💾}
Pickle, JSON, SQLite, or chunked backends.

### TTL freshness {icon=⏱}
Per-record expiry with `is_data_fresh()`.
:::
```

**Visual:** Each cell is a small card with the icon in an accented square badge and the body text in dimmed small type below the bolded title. The grid collapses to a single column on narrow viewports.

---

### `:::cards`

A two-column grid of clickable navigation cards, typically used to offer the reader branching paths into different sections. Each card links to another section via its slug.

```md
:::cards
### Just the cache {link=cache-basics}
Persist data between runs, check staleness, optionally hydrate into typed objects.

### Building an API client {link=api-wrapper}
Subclass `ApiWrapper` for HTTP clients with automatic GET caching.
:::
```

**Visual:** Each card has the title in accent-colored mono type and the body in smaller dimmed text. The card border adopts the accent color on hover with a faint accent background wash.

---

### `:::callout [variant]`

An aside block for tips, warnings, and cross-references. Variants: `default` (accent left border), `info` (accent2 blue), `warn` (red).

```md
:::callout info
**Tip:** Always call `cache.close()` when using SQLite to flush pending writes.
:::

:::callout warn
**Note:** `update()` raises `KeyError` if the key doesn't exist.
:::
```

**Visual:** A horizontally bordered block with a colored left stripe and a faint tinted background matching the variant. Bold text renders in the primary text color; body is in dimmed text.

---

### `:::method`

An API method signature block. Renders in monospace with color-coded tokens for method names, parameters, types, and defaults.

```md
:::method
cache.store(key, data, expiry=None, cast=None)
:::
```

Within a method block you can annotate tokens:

```md
:::method
cache.{fn:store}({param:key}: {type:str}, {param:data}: {type:Any}, expiry: {type:float} = {default:None})
:::
```

**Visual:** A dark code-background panel. Method name renders in blue, parameters in dim text, types in accent, defaults in dimmer text.

---

### `:::selector_list`

A structured list of selector syntax entries, used for reference tables of a selector language or pattern grammar.

```md
:::selector_list
### `field`
Access a top-level key.

### `parent.child`
Dot-path into nested dicts.

### `list[0]`
Integer index into a list.
:::
```

**Visual:** Each entry renders as a two-column row: the syntax in accent-colored mono on the left (`min-width: 180px`), the description in dimmed prose on the right. Rows are separated by subtle horizontal rules.

---

### `:::two_column`

Splits content into two side-by-side prose columns. Accepts optional `left` and `right` subblocks or splits at `---` within the block.

```md
:::two_column
Left side prose goes here. Explain the concept or motivation.

---

Right side has the counterpoint, an example, or a code snippet.
:::
```

**Visual:** Equal-width flex columns with a gap. Both columns inherit normal prose styles.

---

### `:::table`

A styled API reference table. The first column renders in mono accent2 color; subsequent columns use dimmed body text.

```md
:::table
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `key` | `str` | — | Cache record identifier |
| `expiry` | `float` | `None` | Seconds before the record is considered stale |
:::
```

**Visual:** Monospace uppercase headers in dimmer text, first-column cells in accent2 blue mono, alternating subtle row separators.

---

### `:::tabs`

A tabbed content switcher. Each tab requires a stable `id` attribute.

```md
:::tabs
### Pickle {id=pkl}
Default backend. Compact, opaque, fast. No external dependencies.

### JSON {id=json}
Human-readable. Useful for debugging stored payloads.

### SQLite {id=sqlite}
Best for large caches. Atomic writes; requires `cache.close()`.
:::
```

**Visual:** A row of pill-style tab buttons above a content pane. The active tab label is highlighted in accent. Tab state is preserved during the session.

---

### `:::depth [level=N]`

A collapsible depth block for progressive disclosure. Higher levels represent more advanced or detailed content.

```md
:::depth level=2
More detailed implementation notes go here for readers who want to go deeper.
:::
```

**Visual:** Rendered with a `data-depth` attribute used by the generator's JS to show/hide based on a global reading-depth slider (if enabled in metadata). At level 1, content is always visible.

---

### `:::quick_links`

A set of pill-style reference links rendered inside the section. Accepts internal slugs or external hrefs.

```md
:::quick_links
- [doc:ref-cache] — Full Cache API
- [QUERY.md](../QUERY.md) — Selector syntax reference
:::
```

**Visual:** A horizontal or wrapped row of rounded pill links using accent2 color.

---

### `:::reference_list`

A compact list of linked references, rendered at the bottom of a section as a "see also" block.

```md
:::reference_list
- [doc:ref-apiwrapper] — ApiWrapper API
- [doc:typed-models] — @apimodel and Alias
- [https://jsonplaceholder.typicode.com](JSONPlaceholder API)
:::
```

**Visual:** Small mono-type links with a subtle separator, styled as a footer row.

---

## Generator Responsibilities

A conforming generator that reads this directory structure must:

1. Parse `metadata.md` for CSS variable values, font imports, identity fields, and search UI copy.
2. Parse `navigation.md` to determine section order, group labels, sidebar link text, optional footer entries, and slug-to-file mapping.
3. Parse `assets.md` to build a name-to-asset registry. Inline SVGs are embedded at build time; images are copied or referenced.
4. For each section declared in navigation.md, compile the corresponding `content/*.md` file: frontmatter → hero block, prose → HTML, `:::` directives → structured components, `[doc:slug]` → wired navigation links, `` `token{ref=slug}` `` → interactive code references.
5. Emit a single self-contained HTML file with all sections present in the DOM (one active at a time), the sidebar pre-wired to activate them, and inter-section link handlers registered.
6. Exclude search widgets and any other runtime-only features from the compiled output unless explicitly declared in `metadata.md`.

---

## Minimal Working Example

```
my-project-docs/
├── metadata.md
├── navigation.md
├── assets.md
└── content/
    └── introduction.md
```

**`metadata.md`**
```md
---
name: MyProject
version: v1.0.0
tagline: Does one thing well
accent: "#7dd3fc"
accent_light: "#1d4ed8"
color_scheme: dark
display_font: Fraunces
body_font: DM Sans
mono_font: IBM Plex Mono
font_source: "https://fonts.googleapis.com/css2?family=..."
search_trigger_label: "docs, guides, examples..."
search_placeholder: "Search local docs..."
search_secondary_hint: "Search the local docs. Try docs, guides, examples."
features:
  search: true
---
```

**`navigation.md`**
```md
---
groups:
  - label: Overview
    entries:
      - Introduction | introduction
footer:
  label: Project
  entries:
    - GitHub | https://github.com/yourname/yourproject | external
---
```

**`assets.md`**
```md
---
svgs: []
images: []
---
```

**`content/introduction.md`**
```md
---
tag: Getting started
title: MyProject
lead: |
  A minimal example of the Atlas Docs format.
---

## Overview

Plain prose goes here. Use `:::callout`, `:::cards`, and other blocks as needed.
```
