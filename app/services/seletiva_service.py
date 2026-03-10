from datetime import datetime
from app.models import db, SeletivaEntry, Season, GridConfig

class SeletivaService:
    @staticmethod
    def parse_time_to_ms(tempo_input):
        """
        Converte string de tempo (ex: 1:35.800) para milissegundos.
        """
        # Remove tudo que não é dígito
        digits = "".join(filter(str.isdigit, tempo_input))
        # Assume formato M:SS.mmm (6 ou 7 dígitos). Ex: 135800
        if len(digits) < 4:
            raise ValueError("Tempo muito curto")
        
        ms = int(digits[-3:])
        sec = int(digits[-5:-3])
        min = int(digits[:-5]) if len(digits) > 5 else 0
        
        total_ms = (min * 60 * 1000) + (sec * 1000) + ms
        return total_ms

    @staticmethod
    def register_time(pilot_id, tempo_input):
        """
        Registra ou atualiza o tempo de um piloto na seletiva.
        Retorna a entrada criada/atualizada.
        """
        total_ms = SeletivaService.parse_time_to_ms(tempo_input)
        
        entry = SeletivaEntry.query.filter_by(pilot_id=pilot_id).first()
        if not entry:
            entry = SeletivaEntry(pilot_id=pilot_id)
            db.session.add(entry)
        
        entry.tempo_str = tempo_input
        entry.tempo_ms = total_ms
        entry.data_registro = datetime.utcnow()
        
        db.session.commit()
        return entry

    @staticmethod
    def close_seletiva(season_name):
        """
        Encerra a seletiva, cria a temporada e distribui os pilotos nos grids.
        Retorna o número de pilotos alocados.
        """
        # 1. Criar a nova temporada
        nova_season = Season(
            nome=season_name, 
            ativa=True, 
            data_inicio=datetime.utcnow().date()
        )
        db.session.add(nova_season)
        
        # 2. Buscar entradas e configs
        entradas = SeletivaEntry.query.order_by(SeletivaEntry.tempo_ms.asc()).all()
        configs = GridConfig.query.filter_by(season_id=None).order_by(GridConfig.ordem).all()
        
        count_alocados = len(entradas)

        # Lógica de distribuição
        for i, entry in enumerate(entradas):
            pos = i + 1
            alocado = False
            vagas_acumuladas = 0
            
            # Preserva grids anteriores, separando IDs de marcadores de texto (RESERVA, etc)
            current_grid_ids = set()
            current_markers = set()
            if entry.piloto.grid and entry.piloto.grid != 'SEM_GRID':
                for g in entry.piloto.grid.split(','):
                    token = g.strip()
                    if token.isdigit():
                        current_grid_ids.add(int(token))
                    elif token:
                        current_markers.add(token)

            # Distribui conforme as vagas configuradas
            for config in configs:
                vagas_acumuladas += config.vagas
                if pos <= vagas_acumuladas:
                    current_grid_ids.add(config.id)
                    alocado = True
                    break
            if not alocado:
                current_markers.add('RESERVA')
            
            # Junta os IDs ordenados numericamente com os marcadores de texto
            final_parts = [str(gid) for gid in sorted(list(current_grid_ids))] + sorted(list(current_markers))
            entry.piloto.grid = ",".join(final_parts) if final_parts else 'SEM_GRID'

        # 3. Vincular as configs de grid à nova temporada
        for config in configs:
            config.season_id = nova_season.id

        # 4. Limpar a tabela de seletiva
        SeletivaEntry.query.delete()
        db.session.commit()
        
        return count_alocados