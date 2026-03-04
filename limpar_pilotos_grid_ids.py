import argparse
from typing import Set

from run import app
from app.models import db, Season, GridConfig, PilotProfile


def parse_ids(text: str) -> Set[int]:
    res: Set[int] = set()
    if not text:
        return res
    for tok in [x.strip() for x in text.split(',') if x.strip()]:
        if tok.isdigit():
            try:
                res.add(int(tok))
            except ValueError:
                pass
    return res


def format_ids(ids: Set[int]) -> str:
    if not ids:
        return 'SEM_GRID'
    return ",".join(str(x) for x in sorted(ids))


def main():
    parser = argparse.ArgumentParser(description='Limpa PilotProfile.grid, mantendo apenas IDs válidos para as temporadas alvo.')
    parser.add_argument('--season', type=int, action='append', help='ID(s) de temporada(s) alvo. Se omitido, usa temporadas ativas.')
    parser.add_argument('--all-seasons', action='store_true', help='Considerar também temporadas inativas como alvo (com --season omitido busca todas).')
    parser.add_argument('--dry-run', action='store_true', help='Não grava no banco; apenas imprime mudanças.')

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
            print('[INFO] Nenhuma temporada encontrada com os filtros informados.')
            return

        # Conjunto de IDs de grids válidos considerados como alvo
        valid_grid_ids: Set[int] = set()
        for s in seasons:
            for cfg in GridConfig.query.filter_by(season_id=s.id).all():
                valid_grid_ids.add(int(cfg.id))
        if not valid_grid_ids:
            print('[ALERTA] Nenhum GridConfig encontrado nas temporadas alvo. Nada a fazer.')
            return

        changed = 0
        pilots = PilotProfile.query.all()
        for p in pilots:
            current = parse_ids(p.grid)
            cleaned = set(x for x in current if x in valid_grid_ids)
            new_text = format_ids(cleaned)
            if new_text != (p.grid or ''):
                print(f"[CLEAN] Pilot {p.id:>4} - {p.nickname:<20} :: '{p.grid}' -> '{new_text}'")
                if not args.dry_run:
                    p.grid = new_text
                    changed += 1
        if not args.dry_run:
            db.session.commit()
        print(f"\n[RESUMO] Perfis alterados: {changed} {'(dry-run)' if args.dry_run else ''}")


if __name__ == '__main__':
    main()
