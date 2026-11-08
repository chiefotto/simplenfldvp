from services.catalog import COMMANDS

from interfaces.discord.formatters.common import fit_message

NOTES = """How to read a result
A higher positive score means the opposing defense allows more than the league average, so the offensive matchup is more favorable. A negative score means that defense is stronger than average. Scores use all 32 defenses. The schedule only decides which offense faces that defense.

HOT is a major defensive weakness. WARM is above-average weakness. NEUTRAL is near the league average. COOL is above-average strength. COLD is a major strength.

Defensive rank compares that defense with the whole NFL for one position and metric. Rank 1 is the weakest defense for that stat. Weekly rank only orders the offenses on this week's slate.

Fantasy commands use fantasy points allowed by position. They are not player start or sit advice.

"""

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
    "admin update": "/admin update",
}


def format_help():
    lines = [NOTES.rstrip(), "", "/system ping — Check that the bot is online."]
    for command in COMMANDS:
        example = SLASH_EXAMPLES[command["name"]]
        lines.append(f"{example} — {command['description']}")
    lines.append("/admin status — Show the stored season, current game week, and defense snapshot week.")
    lines.append("Admin commands require the configured admin role.")
    return fit_message("\n".join(lines))
