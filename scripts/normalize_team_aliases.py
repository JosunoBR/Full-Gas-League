"""
Idempotent data migration script.

Normalizes duplicate team aliases within (season_id, grid_id, normalized_name):
  - Chooses canonical team by highest id.
  - Repoints race_result.team_id to canonical.
  - Moves pilot/team links from aliases to canonical.
  - Deactivates alias teams.
"""

from collections import defaultdict
import argparse

from run import app
from app.models import db, Team, RaceResult


def normalize_name(name):
    return (name or "").strip().upper()


def run_migration(season_id=None, dry_run=True):
    with app.app_context():
        query = Team.query
        if season_id is not None:
            query = query.filter(Team.season_id == season_id)
        teams = query.all()

        groups = defaultdict(list)
        for t in teams:
            if not t.grid_id:
                continue
            key = (t.season_id, t.grid_id, normalize_name(t.nome))
            groups[key].append(t)

        affected = 0
        for key, items in groups.items():
            if len(items) <= 1:
                continue
            items = sorted(items, key=lambda x: x.id)
            canonical = items[-1]
            aliases = items[:-1]

            for alias in aliases:
                # Move race results team snapshot to canonical.
                RaceResult.query.filter_by(team_id=alias.id).update({"team_id": canonical.id})

                # Move pilot links to canonical without duplicates.
                for p in alias.pilots:
                    if not any(cp.id == p.id for cp in canonical.pilots):
                        canonical.pilots.append(p)
                for p in alias.reserves:
                    if not any(cp.id == p.id for cp in canonical.reserves):
                        canonical.reserves.append(p)

                alias.ativa = False
                affected += 1

        if dry_run:
            db.session.rollback()
        else:
            db.session.commit()

        print(f"Alias groups: {sum(1 for v in groups.values() if len(v) > 1)}")
        print(f"Alias teams affected: {affected}")
        print(f"Dry run: {dry_run}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--season-id", type=int, default=None)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    run_migration(season_id=args.season_id, dry_run=not args.apply)

