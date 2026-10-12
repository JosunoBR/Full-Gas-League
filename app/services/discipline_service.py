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
        Verifica se o piloto deve cumprir Quali Ban na próxima etapa
        com base na escolha manual realizada no julgamento do protesto.
        """
        ultimo_p = Protesto.query.filter_by(acusado_id=pilot_id, grid_id=grid_id, status='CONCLUIDO')\
            .filter(Protesto.tipo_ban.in_(['QUALI_BAN', 'AMBOS']))\
            .order_by(Protesto.data_fechamento.desc()).first()
            
        if not ultimo_p:
            return False
            
        ultima_res = RaceResult.query.join(Race).filter(
            RaceResult.pilot_id == pilot_id, Race.grid_id == grid_id,
            Race.status == 'Concluida', RaceResult.status_presenca == 'OK'
        ).order_by(Race.data_corrida.desc()).first()
        
        if not ultima_res or not ultima_res.race or not ultima_res.race.data_corrida:
            return True
            
        etapa_dt = ultimo_p.etapa.data_corrida if (ultimo_p.etapa and ultimo_p.etapa.data_corrida) else None
        fechamento_dt = ultimo_p.data_fechamento.date() if ultimo_p.data_fechamento else None
        ref_dt = max(etapa_dt or fechamento_dt, fechamento_dt or etapa_dt)
        if not ref_dt:
            return True

        # O ban é cumprido somente após o piloto concluir com presença OK uma prova com data POSTERIOR à punição
        return ultima_res.race.data_corrida <= ref_dt

    @staticmethod
    def is_race_banned(pilot_id, grid_id):
        """
        Verifica se o piloto deve cumprir Race Ban na próxima etapa
        (seja por CNH zerada ou por escolha manual do tribunal).
        """
        from app.models import PilotProfile
        piloto = db.session.get(PilotProfile, pilot_id)
        if piloto and piloto.pontos_cnh <= 0:
            return True

        ultimo_p = Protesto.query.filter_by(acusado_id=pilot_id, grid_id=grid_id, status='CONCLUIDO')\
            .filter(Protesto.tipo_ban.in_(['RACE_BAN', 'AMBOS']))\
            .order_by(Protesto.data_fechamento.desc()).first()
            
        if not ultimo_p:
            return False
            
        ultima_res = RaceResult.query.join(Race).filter(
            RaceResult.pilot_id == pilot_id, Race.grid_id == grid_id,
            Race.status == 'Concluida', RaceResult.status_presenca == 'OK'
        ).order_by(Race.data_corrida.desc()).first()
        
        if not ultima_res or not ultima_res.race or not ultima_res.race.data_corrida:
            return True

        etapa_dt = ultimo_p.etapa.data_corrida if (ultimo_p.etapa and ultimo_p.etapa.data_corrida) else None
        fechamento_dt = ultimo_p.data_fechamento.date() if ultimo_p.data_fechamento else None
        ref_dt = max(etapa_dt or fechamento_dt, fechamento_dt or etapa_dt)
        if not ref_dt:
            return True

        return ultima_res.race.data_corrida <= ref_dt

    @staticmethod
    def preload_quali_bans(season_id):
        """
        Retorna um conjunto de tuplas (pilot_id, grid_id) com Quali Ban ativo na temporada.
        """
        protestos = (
            Protesto.query.join(Race, Protesto.etapa_id == Race.id)
            .filter(
                Race.season_id == season_id,
                Protesto.status == 'CONCLUIDO',
                Protesto.tipo_ban.in_(['QUALI_BAN', 'AMBOS'])
            )
            .order_by(Protesto.data_fechamento.desc())
            .all()
        )
        if not protestos:
            return set()

        last_protest_date = {}
        for p in protestos:
            key = (p.acusado_id, p.grid_id)
            if key not in last_protest_date:
                etapa_dt = p.etapa.data_corrida if (p.etapa and p.etapa.data_corrida) else None
                fechamento_dt = p.data_fechamento.date() if p.data_fechamento else None
                ref_dt = max(etapa_dt or fechamento_dt, fechamento_dt or etapa_dt)
                if ref_dt:
                    last_protest_date[key] = ref_dt

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
        for key, protest_ref_dt in last_protest_date.items():
            race_dt = last_race_date.get(key)
            if not race_dt or race_dt <= protest_ref_dt:
                banned_set.add(key)

        return banned_set

    @staticmethod
    def preload_race_bans(season_id):
        """
        Retorna um conjunto de tuplas (pilot_id, grid_id) com Race Ban ativo na temporada
        por decisão do tribunal (excluindo checagem puramente individual de CNH).
        """
        protestos = (
            Protesto.query.join(Race, Protesto.etapa_id == Race.id)
            .filter(
                Race.season_id == season_id,
                Protesto.status == 'CONCLUIDO',
                Protesto.tipo_ban.in_(['RACE_BAN', 'AMBOS'])
            )
            .order_by(Protesto.data_fechamento.desc())
            .all()
        )
        if not protestos:
            return set()

        last_protest_date = {}
        for p in protestos:
            key = (p.acusado_id, p.grid_id)
            if key not in last_protest_date:
                etapa_dt = p.etapa.data_corrida if (p.etapa and p.etapa.data_corrida) else None
                fechamento_dt = p.data_fechamento.date() if p.data_fechamento else None
                ref_dt = max(etapa_dt or fechamento_dt, fechamento_dt or etapa_dt)
                if ref_dt:
                    last_protest_date[key] = ref_dt

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
        for key, protest_ref_dt in last_protest_date.items():
            race_dt = last_race_date.get(key)
            if not race_dt or race_dt <= protest_ref_dt:
                banned_set.add(key)

        return banned_set