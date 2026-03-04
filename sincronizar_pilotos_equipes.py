import argparse
from typing import List, Set

from run import app
from app.models import db, Season, Team, PilotProfile


def parse_grid_ids(grid_text: str) -> Set[int]:
    ids: Set[int] = set()
    if not grid_text:
        return ids
    for tok in [x.strip() for x in grid_text.split(',') if x.strip()]:
        if tok.isdigit():
            try:
                ids.add(int(tok))
            except ValueError:
                pass
    return ids


def format_grid_ids(ids: Set[int]) -> str:
    if not ids:
        return 'SEM_GRID'
    return ",".join(str(x) for x in sorted(ids))


def sync_season(season: Season, dry_run: bool = False, strip_legacy_names: bool = True) -> int:
    """
    Sincroniza PilotProfile.grid com IDs de grid das equipes (titulares e reservas) 
    para a temporada fornecida. Mantém apenas IDs; remove nomes legados quando solicitado.

    Retorna o número de perfis modificados.
    """
    changed = 0

    teams = Team.query.filter_by(season_id=season.id).all()

    # Constrói um mapa pilot_id -> set(grid_ids) a partir das equipes
    pilot_to_ids: dict[int, Set[int]] = {}

    for team in teams:
        if not team.grid_id:
            continue
        g_id = int(team.grid_id)
        # Titulares
        for p in team.pilots:
            pilot_to_ids.setdefault(p.id, set()).add(g_id)
        # Reservas
        for p in team.reserves:
            pilot_to_ids.setdefault(p.id, set()).add(g_id)

    # Aplica ao campo PilotProfile.grid (IDs numéricos)
    for pilot_id, new_ids in pilot_to_ids.items():
        profile: PilotProfile = PilotProfile.query.get(pilot_id)
        if not profile:
            continue

        current_ids = parse_grid_ids(profile.grid)

        # Se solicitado, remover tokens não numéricos do grid textual legado
        if strip_legacy_names and profile.grid:
            # Caso existam nomes legados, serão perdidos; mantemos apenas IDs
            pass

        merged = set(current_ids)
        merged.update(new_ids)

        # Se havia 'SEM_GRID' e agora há IDs, removemos o marcador
        # (o format_grid_ids já trata quando o set fica vazio)
        new_text = format_grid_ids(merged)

        if new_text != (profile.grid or ''):
            print(f"[SYNC] Pilot {profile.id:>4} - {profile.nickname:<20} :: '{profile.grid}' -> '{new_text}'")
            if not dry_run:
                profile.grid = new_text
                changed += 1

    if not dry_run:
        db.session.commit()

    return changed


def main():
    parser = argparse.ArgumentParser(description="Sincroniza PilotProfile.grid com IDs de grids das equipes por temporada.")
    parser.add_argument('--season', type=int, action='append', help='ID(s) da temporada para sincronizar (pode repetir).')
    parser.add_argument('--all-seasons', action='store_true', help='Incluir também temporadas inativas (padrão: apenas ativas).')
    parser.add_argument('--dry-run', action='store_true', help='Executa sem gravar no banco, apenas imprime o que seria feito.')
    parser.add_argument('--keep-legacy', action='store_true', help='Não remover tokens não numéricos existentes no PilotProfile.grid (mantém legado).')

    args = parser.parse_args()

    with app.app_context():
        if args.season:
            seasons = Season.query.filter(Season.id.in_(args.season)).all()
        else:
            if args.all_seasons:
                seasons = Season.query.order_by(Season.id.asc()).all()
            else:
                seasons = Season.query.filter_by(ativa=True).order_by(Season.id.asc()).all()

        if not seasons:
            print("[INFO] Nenhuma temporada encontrada para sincronizar (verifique filtros).")
            return

        total_changed = 0
        for s in seasons:
            print(f"\n== Temporada {s.id} - {s.nome} (ativa={bool(s.ativa)}) ==")
            changed = sync_season(s, dry_run=args.dry_run, strip_legacy_names=(not args.keep_legacy))
            print(f"[OK] Perfis modificados nesta temporada: {changed}")
            total_changed += changed

        print(f"\n[RESUMO] Total de perfis modificados: {total_changed} {'(dry-run)' if args.dry_run else ''}")


if __name__ == '__main__':
    main()
