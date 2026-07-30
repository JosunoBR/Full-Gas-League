from datetime import datetime
from sqlalchemy import func
from app.models import db, Protesto, RaceResult, Race

class DisciplineService:
    @staticmethod
    def get_pilot_discipline_stats(pilot_id, season_id, grid_id):
        """
        Calcula CNH e Advertências para um contexto específico (Temporada + Grid).
        """
        cnh = 25
        adv_count = 0
        
        # 1. Protestos (Punições e Advertências)
        protestos = Protesto.query.join(Race).filter(
            Protesto.acusado_id == pilot_id,
            Protesto.status == 'CONCLUIDO',
            Race.season_id == season_id,
            Race.grid_id == grid_id
        ).all()
        
        for p in protestos:
            v = p.veredito_final
            if v == 'LEVE': cnh -= 3
            elif v == 'MEDIA': cnh -= 5
            elif v == 'GRAVE': cnh -= 10
            elif v == 'ADVERTENCIA': adv_count += 1
            
        # Regra de Advertência: A cada 3 acumuladas, perde 3 pontos
        cnh -= (adv_count // 3) * 3
        
        # 2. Descontos por W.O. (FNJ)
        fnjs = RaceResult.query.join(Race).filter(
            RaceResult.pilot_id == pilot_id,
            RaceResult.status_presenca == 'FNJ',
            Race.season_id == season_id,
            Race.grid_id == grid_id
        ).count()
        cnh -= (fnjs * 2)
        
        return {'cnh': cnh, 'advertencias': adv_count}

    @staticmethod
    def is_quali_banned(pilot_id, grid_id):
        """
        Verifica se o piloto deve cumprir Quali Ban na próxima etapa.
        """
        ultimo_p = Protesto.query.filter_by(acusado_id=pilot_id, grid_id=grid_id, status='CONCLUIDO')\
            .filter(Protesto.veredito_final.in_(['MEDIA', 'GRAVE']))\
            .order_by(Protesto.data_fechamento.desc()).first()
            
        if not ultimo_p:
            return False
            
        ultima_res = RaceResult.query.join(Race).filter(
            RaceResult.pilot_id == pilot_id, Race.grid_id == grid_id,
            Race.status == 'Concluida', RaceResult.status_presenca == 'OK'
        ).order_by(Race.data_corrida.desc()).first()
        
        return not ultima_res or (ultimo_p.data_fechamento and ultimo_p.data_fechamento.date() > ultima_res.race.data_corrida)

    @staticmethod
    def preload_quali_bans(season_id):
        """
        Retorna um conjunto de tuplas (pilot_id, grid_id) com Quali Ban ativo na temporada,
        usando apenas 2 consultas SQL agregadas em lote.
        """
        protestos = (
            Protesto.query.join(Race, Protesto.etapa_id == Race.id)
            .filter(
                Race.season_id == season_id,
                Protesto.status == 'CONCLUIDO',
                Protesto.veredito_final.in_(['MEDIA', 'GRAVE'])
            )
            .order_by(Protesto.data_fechamento.desc())
            .all()
        )
        if not protestos:
            return set()

        last_protest_date = {}
        for p in protestos:
            key = (p.acusado_id, p.grid_id)
            if key not in last_protest_date and p.data_fechamento:
                last_protest_date[key] = p.data_fechamento.date()

        if not last_protest_date:
            return set()

        last_race_subquery = (
            db.session.query(
                RaceResult.pilot_id,
                Race.grid_id,
                func.max(Race.data_corrida).label('max_date')
            )
            .join(Race, RaceResult.race_id == Race.id)
            .filter(
                Race.season_id == season_id,
                Race.status == 'Concluida',
                RaceResult.status_presenca == 'OK'
            )
            .group_by(RaceResult.pilot_id, Race.grid_id)
            .all()
        )
        last_race_date = {(r[0], r[1]): r[2] for r in last_race_subquery}

        banned_set = set()
        for key, protest_dt in last_protest_date.items():
            race_dt = last_race_date.get(key)
            if not race_dt or protest_dt > race_dt:
                banned_set.add(key)

        return banned_set