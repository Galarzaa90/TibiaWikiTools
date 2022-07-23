import asyncio
import functools
import os
import re

import click
import pywikibot
import tibiapy
import tibiawikisql.api
from tibiawikisql.models import Creature

from tibiawiki_family import TibiaWikiFamily

pywikibot.Family._families["tibiawiki"] = TibiaWikiFamily()


def make_sync(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))
    return wrapper

@click.group()
def cli():
    pass


async def get_boosted_creature_and_boss(client, *, tries=5):
    try:
        response = await client.fetch_boosted_creature_and_boss()
        return response.data
    except Exception:
        return await get_boosted_creature_and_boss(client, tries=tries - 1)


@cli.command()
@make_sync
async def check_headers():
    """Check for headers in articles that might be too high."""
    api = tibiawikisql.api.WikiClient()
    articles_names = list(api.get_category_members_titles("Tibia History"))
    articles = api.get_articles(articles_names)
    results = []
    pattern = re.compile(r"\s?={1,3}\s{0,5}[\w.\d\s]+\s\s{0,5}={1,3}")
    for article in articles:
        if pattern.search(article.content):
            results.append(f"- [{article.title}]({article.url}): Has header level 1,2, or 3")
    for result in results:
        print(result)


@cli.command(name="check-creatures")
@make_sync
async def check_library():
    """Check for creatures that have incorrect data according to Tibia.com's library."""
    api = tibiawikisql.api.WikiClient()
    client = tibiapy.Client()
    articles_names = list(api.get_category_members_titles("Creatures in Tibia.com's Creatures Section"))
    articles = api.get_articles(articles_names)
    response = await client.fetch_library_creatures()
    library_creatures = response.data if response else None
    races = [c.identifier for c in library_creatures.creatures]
    report = []
    for article in articles:
        creature = Creature.from_article(article)
        if creature.library_race:
            try:
                races.remove(creature.library_race)
            except ValueError:
                pass
            response = await client.fetch_creature(creature.library_race)
            click.echo(f"Checking {creature.title}...")
            lib_creature = response.data if response else None
            if lib_creature is None:
                report.append(f"`{creature.title}` - Tibia.com entry could not be found ({creature.library_race}).")
                click.echo(f"`{creature.title}` - Tibia.com entry could not be found ({creature.library_race}).")
                continue
            if lib_creature.hitpoints != creature.hitpoints:
                report.append(f"`{creature.title}` - Hitpoints do not match: {creature.hitpoints} -> {lib_creature.hitpoints}")
            if lib_creature.experience != creature.experience:
                report.append(f"`{creature.title}` - Experience do not match: {creature.experience} -> {lib_creature.experience}")
            if creature.paralysable != ("paralyze" not in lib_creature.immune_to):
                _not = "not " if "paralyze" not in lib_creature.immune_to else ""
                report.append(f"`{creature.title}` - Should {_not}be paralyzable.")
            if creature.sees_invisible != ("invisible" in lib_creature.immune_to):
                _not = "" if "invisible" in lib_creature.immune_to else "not "
                report.append(f"`{creature.title}` - Should {_not}see invisible.")
            if bool(creature.convince_cost) != lib_creature.convinceable:
                _not = "" if lib_creature.convinceable else "not "
                report.append(f"`{creature.title}` - Should {_not}be convinceable.")
            if bool(creature.summon_cost) != lib_creature.summonable:
                _not = "" if lib_creature.summonable else "not "
                report.append(f"`{creature.title}` - Should {_not}be summonable.")
            cost = creature.summon_cost or creature.convince_cost
            if cost and lib_creature.mana_cost != cost:
                report.append(f"`{creature.title}` - Mana cost do not match: {cost} -> {lib_creature.mana_cost}")
    click.echo("\n".join(f"- {r}" for r in report))
    click.echo("------")
    missing_races = '\n'.join(f"- {r}" for r in races)
    click.echo(f"Could not find these races in creature articles: {missing_races}")


@cli.command()
@make_sync
async def boosted_creature():
    """Updates the boosted creature template."""
    click.echo("Fetching boosted creature…")
    client = tibiapy.Client()
    boosted_creatures = await get_boosted_creature_and_boss(client)
    click.echo(f"Boosted Creature: {boosted_creatures.creature.name}")
    creature_name = boosted_creatures.name.replace(" Of ", " of ").replace(" The ", " the ")
    # The article on TibiaWiki has (Basic) at the end.
    if creature_name == "Nomad":
        creature_name = "Nomad (Basic)"
    click.echo(f"Formatting name: {boosted_creature.name!r} -> {creature_name!r}")

    boss_name = boosted_creatures.boss.name
    click.echo(f"Boosted Boss: {boss_name}")

    click.echo("Logging on to TibiaWiki...")
    site = pywikibot.Site(fam="tibiawiki", code="en", user=os.getenv("WIKI_USER"))
    site.login()

    click.echo("Updating template...")
    page = pywikibot.Page(site, "Template:Boosted Creature")
    page.text = creature_name
    # Set edit summary to creature's name
    page.save(creature_name)

    boss_page = pywikibot.Page(site, "Template:Boosted Boss")
    boss_page.text = boss_name
    boss_page.save(boss_name)
    await client.session.close()


if __name__ == "__main__":
    cli()
