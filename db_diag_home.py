import sqlite3
from pathlib import Path

db_path = Path(__file__).with_name('f1_league.db')
print(f"DB: {db_path} (exists={db_path.exists()})")

con = sqlite3.connect(str(db_path))
con.row_factory = sqlite3.Row
cur = con.cursor()

print("\n== Seasons (ordered ASC) ==")
seasons = cur.execute("SELECT id, nome, ativa FROM season ORDER BY id ASC").fetchall()
for r in seasons:
    print(dict(r))

active_asc = [r for r in seasons if r['ativa']]
season_ativa = active_asc[0] if active_asc else (seasons[0] if seasons else None)
print("\nSelected season for Home (oldest active or oldest overall):", dict(season_ativa) if season_ativa else None)

if not season_ativa:
    raise SystemExit(0)

print("\n== GridConfigs for selected season ==")
grids = cur.execute("SELECT id, nome, vagas, ordem, exibir_lastro FROM grid_config WHERE season_id = ? ORDER BY ordem", (season_ativa['id'],)).fetchall()
for r in grids:
    print(dict(r))

def find_grid_id_by_name(name):
    for r in grids:
        if (r['nome'] or '').strip().upper() == name:
            return r['id']
    return None

elite_id = find_grid_id_by_name('ELITE')
print(f"\nELITE grid_id in this season: {elite_id}")

print("\n== Teams in selected season that are ELITE (by grid_id or legacy name) ==")
params = {'sid': season_ativa['id']}
if elite_id is not None:
    teams = cur.execute(
        """
        SELECT id, nome, grid, grid_id, season_id, ativa
        FROM team
        WHERE season_id = :sid AND (
          grid_id = :gid OR UPPER(COALESCE(grid,'')) = 'ELITE'
        )
        ORDER BY nome
        """,
        {'sid': season_ativa['id'], 'gid': elite_id}
    ).fetchall()
else:
    teams = cur.execute(
        """
        SELECT id, nome, grid, grid_id, season_id, ativa
        FROM team
        WHERE season_id = :sid AND UPPER(COALESCE(grid,'')) = 'ELITE'
        ORDER BY nome
        """,
        {'sid': season_ativa['id']}
    ).fetchall()

for t in teams:
    print(dict(t))

print("\n== Pilots linked as TITULARES for these ELITE teams ==")
for t in teams:
    rows = cur.execute(
        """
        SELECT p.id, p.nickname, p.nome_real, p.grid AS profile_grids
        FROM pilot_profile p
        JOIN pilot_teams pt ON pt.pilot_id = p.id
        WHERE pt.team_id = ?
        ORDER BY p.nickname
        """,
        (t['id'],)
    ).fetchall()
    print(f"Team {t['id']} - {t['nome']}: {len(rows)} titulares")
    for r in rows:
        print("  ", dict(r))

print("\n== Pilots linked as RESERVAS for these ELITE teams ==")
for t in teams:
    rows = cur.execute(
        """
        SELECT p.id, p.nickname, p.nome_real, p.grid AS profile_grids
        FROM pilot_profile p
        JOIN pilot_reserves pr ON pr.pilot_id = p.id
        WHERE pr.team_id = ?
        ORDER BY p.nickname
        """,
        (t['id'],)
    ).fetchall()
    print(f"Team {t['id']} - {t['nome']}: {len(rows)} reservas")
    for r in rows:
        print("  ", dict(r))

print("\n== Pilots whose profile grid TEXT contains ELITE (profile fallback) ==")
profile_elite = cur.execute(
    """
    SELECT id, nickname, nome_real, grid AS profile_grids
    FROM pilot_profile
    WHERE UPPER(COALESCE(grid, '')) LIKE '%ELITE%'
    ORDER BY nickname
    """
).fetchall()
for r in profile_elite:
    print(dict(r))

print("\n== Sample standings inference check (who SHOULD appear by home logic) ==")
# who should appear in ELITE according to home logic for this season:
# - any pilot in teams (titulares or reservas) where team grid matches ELITE AND team.season_id == season_ativa.id
# - any pilot with profile grid containing this season's ELITE grid id (as string) or name
should_ids = set()
# by teams titulares
for t in teams:
    titulares = cur.execute("SELECT pilot_id FROM pilot_teams WHERE team_id = ?", (t['id'],)).fetchall()
    should_ids.update([row['pilot_id'] for row in titulares])
# by reservas
for t in teams:
    reservas = cur.execute("SELECT pilot_id FROM pilot_reserves WHERE team_id = ?", (t['id'],)).fetchall()
    should_ids.update([row['pilot_id'] for row in reservas])
# by profile text
if elite_id is not None:
    elite_name = next((r['nome'] for r in grids if r['id'] == elite_id), 'ELITE')
    profile_rows = cur.execute(
        """
        SELECT id AS pilot_id FROM pilot_profile
        WHERE (',' || UPPER(grid) || ',') LIKE ? OR (',' || UPPER(grid) || ',') LIKE ?
        """,
        (f'%,{elite_name.upper()}%', f'%,{str(elite_id)}%')
    ).fetchall()
else:
    elite_name = 'ELITE'
    profile_rows = cur.execute(
        """
        SELECT id AS pilot_id FROM pilot_profile
        WHERE (',' || UPPER(grid) || ',') LIKE ?
        """,
        (f'%,{elite_name.upper()}%',)
    ).fetchall()
should_ids.update([row['pilot_id'] for row in profile_rows])

should_list = sorted(list(should_ids))
print(f"Pilots that should be listed for ELITE (ids): {should_list}")
if should_list:
    details = cur.execute(
        f"SELECT id, nickname, nome_real, grid FROM pilot_profile WHERE id IN ({','.join('?'*len(should_list))}) ORDER BY nickname",
        should_list
    ).fetchall()
    for r in details:
        print("  ", dict(r))

con.close()
print("\nDone.")
