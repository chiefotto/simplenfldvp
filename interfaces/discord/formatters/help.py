from services.catalog import COMMANDS

from interfaces.discord.formatters.common import base_embed

NOTES = """A higher positive score means the defense allows more than the league average. A negative score means a stronger defense. Scores use all 32 defenses. The schedule only decides which offense faces that defense.

HOT is a major defensive weakness. WARM is above-average weakness. NEUTRAL is near the league average. COOL is above-average strength. COLD is a major strength.

Defensive rank is the league rank for one position and metric. Rank 1 is the weakest defense. Weekly rank only orders this week's offenses."""

SLASH_EXAMPLES = {
    "matchup best": "/matchup opportunities",
    "matchup best position": "/matchup best position:WR",
    "matchup best metric": "/matchup metric position:WR metric:receptions",
    "matchup defense": "/matchup defense team:DET position:WR",
    "matchup offense": "/matchup offense team:MIA position:WR",
    "fantasy best": "/fantasy best",
    "fantasy worst": "/fantasy worst",
    "fantasy position": "/fantasy position position:WR",
    "fantasy offense": "/fantasy offense team:DET position:WR",
    "touchdown best": "/touchdown best",
    "touchdown offense": "/touchdown offense team:MIA",
    "touchdown passing": "/touchdown passing",
    "admin update": "/admin update",
}

GROUPS = (
    ("Matchup", "matchup", NOTES + "\n\n/system ping — Check that the bot is online."),
    ("Fantasy", "fantasy", "Fantasy commands are not player start or sit advice."),
    ("Touchdown", "touchdown", "Touchdown commands are not a player touchdown probability."),
    ("Admin", "admin", "Admin commands require the configured admin role."),
)


def _lines(prefix, extra=()):
    lines = []
    for command in COMMANDS:
        if not command["name"].startswith(prefix):
            continue
        lines.append(f"{SLASH_EXAMPLES[command['name']]} — {command['description']}")
    lines.extend(extra)
    return "\n".join(lines)


def format_help():
    embeds = []
    for title, prefix, intro in GROUPS:
        extra = []
        if prefix == "admin":
            extra.append("/admin status — Show the stored season, current game week, and defense snapshot week.")
        description = intro
        body = _lines(prefix, extra)
        if body:
            description = f"{intro}\n\n{body}"
        embeds.append(base_embed(title, description))
    return embeds
