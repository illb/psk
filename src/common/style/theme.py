"""
Prompt theme — color palette for prompt components

PromptTheme defines the color scheme used across all interactive UI elements.
"""
from dataclasses import dataclass


@dataclass
class PromptTheme:
    """Color palette for prompt components"""
    primary: str = "cyan"
    secondary: str = "#FF9D00"
    muted: str = ""
    prefix: str = ""
    placeholder: str = "#555555"


# ── Custom presets (5) ────────────────────────────────────────

DEFAULT_THEME = PromptTheme(
    placeholder="#555555",
)

PINK_THEME = PromptTheme(
    primary="#FF6AC1",
    secondary="#ad58b4",
    muted="#666666",
    prefix="#5f819d",
    placeholder="#666666",
)

OCEAN_THEME = PromptTheme(
    primary="#4a90e2",
    secondary="#00bcd4",
    muted="#888888",
    prefix="#4a90e2",
    placeholder="#666666",
)

FOREST_THEME = PromptTheme(
    primary="#4caf50",
    secondary="#ffc107",
    muted="#888888",
    prefix="#4caf50",
    placeholder="#666666",
)

MONO_THEME = PromptTheme(
    primary="#aaaaaa",
    secondary="#ffffff",
    muted="#666666",
    prefix="#aaaaaa",
    placeholder="#444444",
)


# ── IDE / Editor themes (25) ──────────────────────────────────

DRACULA_THEME = PromptTheme(
    primary="#8be9fd",
    secondary="#ff79c6",
    muted="#6272a4",
    prefix="#bd93f9",
    placeholder="#6272a4",
)

NORD_THEME = PromptTheme(
    primary="#88c0d0",
    secondary="#81a1c1",
    muted="#4c566a",
    prefix="#5e81ac",
    placeholder="#4c566a",
)

SOLARIZED_DARK_THEME = PromptTheme(
    primary="#268bd2",
    secondary="#2aa198",
    muted="#657b83",
    prefix="#268bd2",
    placeholder="#586e75",
)

SOLARIZED_LIGHT_THEME = PromptTheme(
    primary="#268bd2",
    secondary="#2aa198",
    muted="#93a1a1",
    prefix="#268bd2",
    placeholder="#93a1a1",
)

GRUVBOX_DARK_THEME = PromptTheme(
    primary="#83a598",
    secondary="#fabd2f",
    muted="#928374",
    prefix="#d3869b",
    placeholder="#928374",
)

GRUVBOX_LIGHT_THEME = PromptTheme(
    primary="#076678",
    secondary="#d79921",
    muted="#a89984",
    prefix="#8f3f71",
    placeholder="#a89984",
)

CATPPUCCIN_MOCHA_THEME = PromptTheme(
    primary="#89dceb",
    secondary="#f5c2e7",
    muted="#585b70",
    prefix="#cba6f7",
    placeholder="#585b70",
)

CATPPUCCIN_LATTE_THEME = PromptTheme(
    primary="#04a5e5",
    secondary="#ea76cb",
    muted="#9ca0b0",
    prefix="#8839ef",
    placeholder="#9ca0b0",
)

CATPPUCCIN_FRAPPE_THEME = PromptTheme(
    primary="#99d1db",
    secondary="#f4b8e4",
    muted="#626880",
    prefix="#ca9ee6",
    placeholder="#626880",
)

CATPPUCCIN_MACCHIATO_THEME = PromptTheme(
    primary="#7dc4e4",
    secondary="#f5bde6",
    muted="#5b6078",
    prefix="#c6a0f6",
    placeholder="#5b6078",
)

TOKYO_NIGHT_THEME = PromptTheme(
    primary="#7aa2f7",
    secondary="#bb9af7",
    muted="#565f89",
    prefix="#7dcfff",
    placeholder="#565f89",
)

ONE_DARK_THEME = PromptTheme(
    primary="#61afef",
    secondary="#c678dd",
    muted="#5c6370",
    prefix="#98c379",
    placeholder="#5c6370",
)

MONOKAI_THEME = PromptTheme(
    primary="#66d9e8",
    secondary="#f92672",
    muted="#75715e",
    prefix="#a6e22e",
    placeholder="#75715e",
)

MATERIAL_THEME = PromptTheme(
    primary="#82aaff",
    secondary="#c3e88d",
    muted="#546e7a",
    prefix="#89ddff",
    placeholder="#546e7a",
)

AYU_DARK_THEME = PromptTheme(
    primary="#39bae6",
    secondary="#ffb454",
    muted="#626a73",
    prefix="#e6b673",
    placeholder="#626a73",
)

AYU_LIGHT_THEME = PromptTheme(
    primary="#399ee6",
    secondary="#fa8d3e",
    muted="#8a9099",
    prefix="#55b4d4",
    placeholder="#8a9099",
)

AYU_MIRAGE_THEME = PromptTheme(
    primary="#39bae6",
    secondary="#ffcc66",
    muted="#5c6773",
    prefix="#ffd580",
    placeholder="#5c6773",
)

SYNTHWAVE_THEME = PromptTheme(
    primary="#f92aad",
    secondary="#36f9f6",
    muted="#495495",
    prefix="#fede5d",
    placeholder="#495495",
)

CYBERPUNK_THEME = PromptTheme(
    primary="#00ff9f",
    secondary="#ff00c8",
    muted="#005f5f",
    prefix="#ffe600",
    placeholder="#005f5f",
)

ROSE_PINE_THEME = PromptTheme(
    primary="#c4a7e7",
    secondary="#ebbcba",
    muted="#6e6a86",
    prefix="#9ccfd8",
    placeholder="#6e6a86",
)

EVERFOREST_THEME = PromptTheme(
    primary="#83c092",
    secondary="#dbbc7f",
    muted="#859289",
    prefix="#a7c080",
    placeholder="#859289",
)

KANAGAWA_THEME = PromptTheme(
    primary="#7e9cd8",
    secondary="#957fb8",
    muted="#717c7c",
    prefix="#6a9589",
    placeholder="#717c7c",
)

GRUVBOX_MATERIAL_THEME = PromptTheme(
    primary="#89b482",
    secondary="#d8a657",
    muted="#928374",
    prefix="#7daea3",
    placeholder="#928374",
)

NIGHTFOX_THEME = PromptTheme(
    primary="#81a1c1",
    secondary="#bf616a",
    muted="#4c566a",
    prefix="#88c0d0",
    placeholder="#4c566a",
)

CARBONFOX_THEME = PromptTheme(
    primary="#78a9ff",
    secondary="#be95ff",
    muted="#3d3d3d",
    prefix="#42be65",
    placeholder="#3d3d3d",
)


# ── DaisyUI themes (27 new) ───────────────────────────────────
# primary: oklch → sRGB approximate conversion

DAISYUI_LIGHT_THEME = PromptTheme(
    primary="#570df8",
    secondary="#f000b8",
    muted="#f2f2f2",
    prefix="#1dafec",
    placeholder="#a8a8a8",
)

DAISYUI_DARK_THEME = PromptTheme(
    primary="#661ae6",
    secondary="#d926aa",
    muted="#2a2a2a",
    prefix="#1fb2a6",
    placeholder="#555555",
)

CUPCAKE_THEME = PromptTheme(
    primary="#65c3c8",
    secondary="#ef9fbc",
    muted="#f9f0da",
    prefix="#eeaf3a",
    placeholder="#b3b3b3",
)

BUMBLEBEE_THEME = PromptTheme(
    primary="#e0a82e",
    secondary="#f9d72f",
    muted="#f0f0f0",
    prefix="#f9d72f",
    placeholder="#a6a6a6",
)

EMERALD_THEME = PromptTheme(
    primary="#66cc8a",
    secondary="#377cfb",
    muted="#f0f0f0",
    prefix="#f9d72f",
    placeholder="#a6a6a6",
)

CORPORATE_THEME = PromptTheme(
    primary="#4b6bfb",
    secondary="#7b92b2",
    muted="#e5e7eb",
    prefix="#e74694",
    placeholder="#9ca3af",
)

RETRO_THEME = PromptTheme(
    primary="#ef9900",
    secondary="#a4cbb4",
    muted="#e8e0cc",
    prefix="#d1c1d7",
    placeholder="#b0a898",
)

VALENTINE_THEME = PromptTheme(
    primary="#e96d7b",
    secondary="#a991f7",
    muted="#fad6e8",
    prefix="#ff6793",
    placeholder="#c8b0c8",
)

HALLOWEEN_THEME = PromptTheme(
    primary="#f28c18",
    secondary="#6d3a9c",
    muted="#212121",
    prefix="#51a800",
    placeholder="#555555",
)

GARDEN_THEME = PromptTheme(
    primary="#5c7f67",
    secondary="#ecf4e7",
    muted="#e0eee0",
    prefix="#5c7f67",
    placeholder="#a0b0a0",
)

AQUA_THEME = PromptTheme(
    primary="#09ecf3",
    secondary="#966fb3",
    muted="#2d3748",
    prefix="#09ecf3",
    placeholder="#718096",
)

LOFI_THEME = PromptTheme(
    primary="#0d0d0d",
    secondary="#1a1a1a",
    muted="#d4d4d4",
    prefix="#808080",
    placeholder="#a0a0a0",
)

PASTEL_THEME = PromptTheme(
    primary="#d1c1d7",
    secondary="#f2bdbd",
    muted="#f5f0f0",
    prefix="#72befa",
    placeholder="#c4b8c4",
)

FANTASY_THEME = PromptTheme(
    primary="#6e0b75",
    secondary="#007ebd",
    muted="#1a0a1f",
    prefix="#007ebd",
    placeholder="#666666",
)

WIREFRAME_THEME = PromptTheme(
    primary="#b8b8b8",
    secondary="#b8b8b8",
    muted="#e0e0e0",
    prefix="#b8b8b8",
    placeholder="#c8c8c8",
)

BLACK_THEME = PromptTheme(
    primary="#343232",
    secondary="#343232",
    muted="#1a1a1a",
    prefix="#666666",
    placeholder="#444444",
)

LUXURY_THEME = PromptTheme(
    primary="#ffffff",
    secondary="#152747",
    muted="#1a1a2e",
    prefix="#a38f5f",
    placeholder="#555555",
)

CMYK_THEME = PromptTheme(
    primary="#45aaff",
    secondary="#ff0088",
    muted="#e8e8e8",
    prefix="#00b3ff",
    placeholder="#a6a6a6",
)

AUTUMN_THEME = PromptTheme(
    primary="#8c0327",
    secondary="#d85251",
    muted="#2d0a14",
    prefix="#d85251",
    placeholder="#666666",
)

BUSINESS_THEME = PromptTheme(
    primary="#1c4e80",
    secondary="#7c909a",
    muted="#1e2832",
    prefix="#e34d28",
    placeholder="#555555",
)

ACID_THEME = PromptTheme(
    primary="#ff00f4",
    secondary="#ff7400",
    muted="#f0f0f0",
    prefix="#ff7400",
    placeholder="#a6a6a6",
)

LEMONADE_THEME = PromptTheme(
    primary="#519903",
    secondary="#e9e92e",
    muted="#f0f4e8",
    prefix="#e9e92e",
    placeholder="#a6a6a6",
)

NIGHT_THEME = PromptTheme(
    primary="#38bdf8",
    secondary="#818cf8",
    muted="#1e293b",
    prefix="#f471b5",
    placeholder="#475569",
)

COFFEE_THEME = PromptTheme(
    primary="#db924b",
    secondary="#263e3f",
    muted="#1a1a1a",
    prefix="#db924b",
    placeholder="#555555",
)

WINTER_THEME = PromptTheme(
    primary="#3b5bdb",
    secondary="#463aa2",
    muted="#94a3b8",
    prefix="#c148ac",
    placeholder="#9fb2c8",
)

DIM_THEME = PromptTheme(
    primary="#9fe88d",
    secondary="#ff7d5c",
    muted="#2a303c",
    prefix="#ff7d5c",
    placeholder="#555555",
)

SUNSET_THEME = PromptTheme(
    primary="#ff865b",
    secondary="#fd6f9c",
    muted="#ffe8e8",
    prefix="#fd6f9c",
    placeholder="#b0a0a0",
)


# ── Textual built-in themes (6 new) ──────────────────────────

TEXTUAL_DARK_THEME = PromptTheme(
    primary="#0178d4",
    secondary="#004578",
    muted="#2b2b2b",
    prefix="#ffa62b",
    placeholder="#555555",
)

TEXTUAL_LIGHT_THEME = PromptTheme(
    primary="#004578",
    secondary="#0178d4",
    muted="#c0c0c0",
    prefix="#ffa62b",
    placeholder="#9fa6ad",
)

FLEXOKI_THEME = PromptTheme(
    primary="#205ea6",
    secondary="#24837b",
    muted="#1c1b1a",
    prefix="#9b76c8",
    placeholder="#555555",
)

ROSE_PINE_MOON_THEME = PromptTheme(
    primary="#c4a7e7",
    secondary="#3e8fb0",
    muted="#393552",
    prefix="#ea9a97",
    placeholder="#6e6a86",
)

ROSE_PINE_DAWN_THEME = PromptTheme(
    primary="#907aa9",
    secondary="#286983",
    muted="#dfdad9",
    prefix="#d7827e",
    placeholder="#9893a5",
)

ATOM_ONE_LIGHT_THEME = PromptTheme(
    primary="#4078f2",
    secondary="#a626a4",
    muted="#cccccc",
    prefix="#bf9232",
    placeholder="#9fa3a8",
)


# ── Theme registries ──────────────────────────────────────────

THEMES: dict[str, PromptTheme] = {
    # custom
    "default":             DEFAULT_THEME,
    "pink":                PINK_THEME,
    "ocean":               OCEAN_THEME,
    "forest":              FOREST_THEME,
    "mono":                MONO_THEME,
    # IDE / editor
    "dracula":             DRACULA_THEME,
    "nord":                NORD_THEME,
    "solarized_dark":      SOLARIZED_DARK_THEME,
    "solarized_light":     SOLARIZED_LIGHT_THEME,
    "gruvbox_dark":        GRUVBOX_DARK_THEME,
    "gruvbox_light":       GRUVBOX_LIGHT_THEME,
    "catppuccin_mocha":    CATPPUCCIN_MOCHA_THEME,
    "catppuccin_latte":    CATPPUCCIN_LATTE_THEME,
    "catppuccin_frappe":   CATPPUCCIN_FRAPPE_THEME,
    "catppuccin_macchiato": CATPPUCCIN_MACCHIATO_THEME,
    "tokyo_night":         TOKYO_NIGHT_THEME,
    "one_dark":            ONE_DARK_THEME,
    "monokai":             MONOKAI_THEME,
    "material":            MATERIAL_THEME,
    "ayu_dark":            AYU_DARK_THEME,
    "ayu_light":           AYU_LIGHT_THEME,
    "ayu_mirage":          AYU_MIRAGE_THEME,
    "synthwave":           SYNTHWAVE_THEME,
    "cyberpunk":           CYBERPUNK_THEME,
    "rose_pine":           ROSE_PINE_THEME,
    "everforest":          EVERFOREST_THEME,
    "kanagawa":            KANAGAWA_THEME,
    "gruvbox_material":    GRUVBOX_MATERIAL_THEME,
    "nightfox":            NIGHTFOX_THEME,
    "carbonfox":           CARBONFOX_THEME,
    # DaisyUI
    "light":               DAISYUI_LIGHT_THEME,
    "dark":                DAISYUI_DARK_THEME,
    "cupcake":             CUPCAKE_THEME,
    "bumblebee":           BUMBLEBEE_THEME,
    "emerald":             EMERALD_THEME,
    "corporate":           CORPORATE_THEME,
    "retro":               RETRO_THEME,
    "valentine":           VALENTINE_THEME,
    "halloween":           HALLOWEEN_THEME,
    "garden":              GARDEN_THEME,
    "aqua":                AQUA_THEME,
    "lofi":                LOFI_THEME,
    "pastel":              PASTEL_THEME,
    "fantasy":             FANTASY_THEME,
    "wireframe":           WIREFRAME_THEME,
    "black":               BLACK_THEME,
    "luxury":              LUXURY_THEME,
    "cmyk":                CMYK_THEME,
    "autumn":              AUTUMN_THEME,
    "business":            BUSINESS_THEME,
    "acid":                ACID_THEME,
    "lemonade":            LEMONADE_THEME,
    "night":               NIGHT_THEME,
    "coffee":              COFFEE_THEME,
    "winter":              WINTER_THEME,
    "dim":                 DIM_THEME,
    "sunset":              SUNSET_THEME,
    # Textual
    "textual_dark":        TEXTUAL_DARK_THEME,
    "textual_light":       TEXTUAL_LIGHT_THEME,
    "flexoki":             FLEXOKI_THEME,
    "rose_pine_moon":      ROSE_PINE_MOON_THEME,
    "rose_pine_dawn":      ROSE_PINE_DAWN_THEME,
    "atom_one_light":      ATOM_ONE_LIGHT_THEME,
}

THEMES_BY_GROUP: dict[str, dict[str, PromptTheme]] = {
    "Custom": {
        "default": DEFAULT_THEME,
        "pink":    PINK_THEME,
        "ocean":   OCEAN_THEME,
        "forest":  FOREST_THEME,
        "mono":    MONO_THEME,
    },
    "IDE / Editor": {
        "dracula":             DRACULA_THEME,
        "nord":                NORD_THEME,
        "solarized_dark":      SOLARIZED_DARK_THEME,
        "solarized_light":     SOLARIZED_LIGHT_THEME,
        "gruvbox_dark":        GRUVBOX_DARK_THEME,
        "gruvbox_light":       GRUVBOX_LIGHT_THEME,
        "catppuccin_mocha":    CATPPUCCIN_MOCHA_THEME,
        "catppuccin_latte":    CATPPUCCIN_LATTE_THEME,
        "catppuccin_frappe":   CATPPUCCIN_FRAPPE_THEME,
        "catppuccin_macchiato": CATPPUCCIN_MACCHIATO_THEME,
        "tokyo_night":         TOKYO_NIGHT_THEME,
        "one_dark":            ONE_DARK_THEME,
        "monokai":             MONOKAI_THEME,
        "material":            MATERIAL_THEME,
        "ayu_dark":            AYU_DARK_THEME,
        "ayu_light":           AYU_LIGHT_THEME,
        "ayu_mirage":          AYU_MIRAGE_THEME,
        "synthwave":           SYNTHWAVE_THEME,
        "cyberpunk":           CYBERPUNK_THEME,
        "rose_pine":           ROSE_PINE_THEME,
        "everforest":          EVERFOREST_THEME,
        "kanagawa":            KANAGAWA_THEME,
        "gruvbox_material":    GRUVBOX_MATERIAL_THEME,
        "nightfox":            NIGHTFOX_THEME,
        "carbonfox":           CARBONFOX_THEME,
    },
    "DaisyUI": {
        "light":     DAISYUI_LIGHT_THEME,
        "dark":      DAISYUI_DARK_THEME,
        "cupcake":   CUPCAKE_THEME,
        "bumblebee": BUMBLEBEE_THEME,
        "emerald":   EMERALD_THEME,
        "corporate": CORPORATE_THEME,
        "retro":     RETRO_THEME,
        "valentine": VALENTINE_THEME,
        "halloween": HALLOWEEN_THEME,
        "garden":    GARDEN_THEME,
        "aqua":      AQUA_THEME,
        "lofi":      LOFI_THEME,
        "pastel":    PASTEL_THEME,
        "fantasy":   FANTASY_THEME,
        "wireframe": WIREFRAME_THEME,
        "black":     BLACK_THEME,
        "luxury":    LUXURY_THEME,
        "cmyk":      CMYK_THEME,
        "autumn":    AUTUMN_THEME,
        "business":  BUSINESS_THEME,
        "acid":      ACID_THEME,
        "lemonade":  LEMONADE_THEME,
        "night":     NIGHT_THEME,
        "coffee":    COFFEE_THEME,
        "winter":    WINTER_THEME,
        "dim":       DIM_THEME,
        "sunset":    SUNSET_THEME,
    },
    "Textual": {
        "textual_dark":   TEXTUAL_DARK_THEME,
        "textual_light":  TEXTUAL_LIGHT_THEME,
        "flexoki":        FLEXOKI_THEME,
        "rose_pine_moon": ROSE_PINE_MOON_THEME,
        "rose_pine_dawn": ROSE_PINE_DAWN_THEME,
        "atom_one_light": ATOM_ONE_LIGHT_THEME,
    },
}
