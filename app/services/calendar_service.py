from app.models import Race, RaceResult
from sqlalchemy.orm import joinedload
from app.models import db
from app.services.simhub_service import SimHubService

class CalendarService:
    @staticmethod
    def build_season_calendar(season_id, grid_configs):
        """
        Busca todas as corridas da temporada e as organiza por grid.
        OTIMIZAÇÃO: NÃO carrega os resultados (súmulas) aqui. Carrega apenas metadados da corrida.
        Retorna o calendário leve e a lista de objetos básicos.
        """
        # Query leve: Apenas dados da tabela Race
        all_races = Race.query.filter_by(season_id=season_id).order_by(Race.data_corrida).all()
        
        calendar = {g['id']: [] for g in grid_configs}
        
        for r in all_races:
            if r.grid_id in calendar:
                r_dict = r.to_dict()
                # FIX: Garante que a data esteja presente explicitamente no dicionário
                r_dict['data_corrida'] = r.data_corrida
                # Otimização: Não carrega 'results' aqui. O modal deve buscar via API /api/race/<id>/results

                calendar[r.grid_id].append(r_dict)
        
        return calendar, all_races

    @staticmethod
    def get_race_summary(race_id):
        """
        Busca os detalhes completos de UMA ÚNICA corrida.
        Usado para o modal de súmula e para os cards de 'Última Corrida'.
        """
        race = (
            Race.query.options(
                joinedload(Race.results).joinedload(RaceResult.pilot),
                joinedload(Race.results).joinedload(RaceResult.team_snapshot),
            )
            .filter_by(id=race_id)
            .first()
        )

        if not race:
            return None

        # Monta dicionário "leve" e totalmente serializável, sem usar Race.to_dict()
        r_dict = {
            "id": race.id,
            "nome_gp": race.nome_gp,
            "pista": race.pista,
            "grid": race.grid,
            "status": race.status,
            "tipo": race.tipo_etapa,
            # estes dois campos são tratados na camada de API
            "data_corrida": race.data_corrida,
            "data_formatada": race.data_corrida.strftime('%d/%m/%Y') if race.data_corrida else 'TBA',
        }

        if race.results:
            # Filtra apenas pilotos que efetivamente participaram da corrida (posicao > 0)
            valid_results = [
                r for r in race.results 
                if r.posicao and r.posicao > 0 and r.status_presenca not in ['AUSENTE', 'JUSTIFICADO', 'NC']
            ]
            
            if not valid_results:
                valid_results = [r for r in race.results if r.posicao and r.posicao > 0]

            # Ordena resultados estritamente da P1 em diante
            sorted_results = sorted(valid_results, key=lambda x: x.posicao)

            clean_results = []
            vencedor_info = None
            vr_info = None
            dotd_info = None
            maior_escalador_info = None
            maior_ganho = -999

            for res in sorted_results:
                pilot_obj = getattr(res, "pilot", None)
                team_obj = getattr(res, "team_snapshot", None)

                pilot_data = {
                    "id": pilot_obj.id if pilot_obj else None,
                    "nickname": pilot_obj.nickname if pilot_obj else "Piloto Removido",
                    "nome_real": pilot_obj.nome_real if pilot_obj else "Desconhecido",
                    "foto_url": pilot_obj.foto_url if pilot_obj else None
                }

                team_data = {
                    "id": res.team_id,
                    "nome": team_obj.nome if team_obj else "N/A",
                    "logo_url": team_obj.logo_url if team_obj else None
                }

                # Cálculo de Delta de Grid
                grid_start = getattr(res, "grid_largada", None)
                delta_grid = None
                if grid_start and res.posicao and res.posicao > 0 and not res.dsq:
                    delta_grid = grid_start - res.posicao
                    if delta_grid > maior_ganho and not res.dnf:
                        maior_ganho = delta_grid
                        maior_escalador_info = {
                            "nickname": pilot_data["nickname"],
                            "foto_url": pilot_data["foto_url"],
                            "largada": grid_start,
                            "chegada": res.posicao,
                            "ganho": delta_grid
                        }

                # Processamento de Pneus
                stints_raw = getattr(res, "pneus_stints", None) or ""
                pneus_list = [p.strip().upper() for p in stints_raw.split(',') if p.strip()]

                # Destaques Individuais
                if res.posicao == 1 and not res.dsq and not vencedor_info:
                    vencedor_info = {
                        "nickname": pilot_data["nickname"],
                        "foto_url": pilot_data["foto_url"],
                        "equipe": team_data["nome"],
                        "team_logo": team_data["logo_url"]
                    }

                if res.volta_rapida and not vr_info:
                    vr_info = {
                        "nickname": pilot_data["nickname"],
                        "foto_url": pilot_data["foto_url"],
                        "tempo": getattr(res, "melhor_volta", None) or "Sim"
                    }

                if res.piloto_do_dia and not dotd_info:
                    dotd_info = {
                        "nickname": pilot_data["nickname"],
                        "foto_url": pilot_data["foto_url"]
                    }

                clean_results.append(
                    {
                        "posicao": res.posicao,
                        "pontos": float(res.pontos_ganhos or 0),
                        "pilot": pilot_data,
                        "team": team_data,
                        "dnf": bool(res.dnf),
                        "dsq": bool(res.dsq),
                        "ausencia": bool(getattr(res, "ausencia", False)),
                        "vr": bool(res.volta_rapida),
                        "dotd": bool(res.piloto_do_dia),
                        "grid_largada": grid_start,
                        "delta_grid": delta_grid,
                        "tempo_total": getattr(res, "tempo_total", None),
                        "melhor_volta": getattr(res, "melhor_volta", None),
                        "tempo_qualy": getattr(res, "tempo_qualy", None),
                        "pit_stops": getattr(res, "pit_stops", 0) or 0,
                        "pneus": pneus_list,
                        "penalidades": getattr(res, "penalidades_texto", None)
                    }
                )

            # Construção da Seção QUALIFYING
            qualy_results = []
            pole_pilot_obj = race.pole_sitter
            pole_time_val = race.pole_time
            pole_sec = SimHubService.parse_time_to_seconds(pole_time_val) if pole_time_val else float('inf')

            # Filtra resultados que possuem posição no grid ou tempo de qualy
            qualy_sorted = sorted(
                [r for r in clean_results if r["grid_largada"] or r["tempo_qualy"]],
                key=lambda x: x["grid_largada"] if x["grid_largada"] else 999
            )

            for idx, q_res in enumerate(qualy_sorted):
                q_sec = SimHubService.parse_time_to_seconds(q_res["tempo_qualy"])
                gap_str = "-"
                if pole_sec < float('inf') and q_sec < float('inf') and q_sec > pole_sec:
                    diff = q_sec - pole_sec
                    gap_str = f"+{diff:.3f}s"
                elif q_res["grid_largada"] == 1:
                    gap_str = "POLE"

                qualy_results.append({
                    "qualy_pos": q_res["grid_largada"] or (idx + 1),
                    "pilot": q_res["pilot"],
                    "team": q_res["team"],
                    "tempo_qualy": q_res["tempo_qualy"] or "Sem Tempo",
                    "gap": gap_str
                })

            pole_sitter_data = None
            if pole_pilot_obj:
                pole_sitter_data = {
                    "nickname": pole_pilot_obj.nickname,
                    "foto_url": pole_pilot_obj.foto_url,
                    "tempo": pole_time_val or "N/A"
                }
            elif qualy_results and qualy_results[0]["qualy_pos"] == 1:
                pole_sitter_data = {
                    "nickname": qualy_results[0]["pilot"]["nickname"],
                    "foto_url": qualy_results[0]["pilot"]["foto_url"],
                    "tempo": qualy_results[0]["tempo_qualy"]
                }

            # Construção da Seção SPRINT
            sprint_results = []
            sprint_filtered = [res for res in race.results if getattr(res, 'posicao_sprint', None)]
            
            if sprint_filtered:
                sprint_sorted = sorted(sprint_filtered, key=lambda x: x.posicao_sprint)
                sprint_winner = sprint_sorted[0] if sprint_sorted else None
                
                for s_res in sprint_sorted:
                    s_pilot = getattr(s_res, "pilot", None)
                    s_team = getattr(s_res, "team_snapshot", None)
                    sprint_results.append({
                        "posicao_sprint": s_res.posicao_sprint,
                        "pontos_sprint": float(getattr(s_res, 'pontos_sprint', 0.0) or 0.0),
                        "pilot": {
                            "id": s_pilot.id if s_pilot else None,
                            "nickname": s_pilot.nickname if s_pilot else "Piloto Removido",
                            "foto_url": s_pilot.foto_url if s_pilot else None
                        },
                        "team": {
                            "id": s_res.team_id,
                            "nome": s_team.nome if s_team else "N/A",
                            "logo_url": s_team.logo_url if s_team else None
                        },
                        "tempo_sprint": getattr(s_res, 'tempo_sprint', None),
                        "melhor_volta_sprint": getattr(s_res, 'melhor_volta_sprint', None)
                    })

            r_dict["results"] = clean_results
            r_dict["qualifying"] = {
                "pole_sitter": pole_sitter_data,
                "results": qualy_results
            }
            r_dict["sprint"] = {
                "has_sprint": bool(sprint_results),
                "results": sprint_results
            } if sprint_results else None
            r_dict["highlights"] = {
                "vencedor": vencedor_info,
                "volta_rapida": vr_info,
                "maior_escalador": maior_escalador_info if (maior_escalador_info and maior_ganho > 0) else None,
                "dotd": dotd_info
            }
            import json
            lobby_data = None
            if getattr(race, 'lobby_settings_json', None):
                try:
                    lobby_data = json.loads(race.lobby_settings_json)
                except Exception:
                    lobby_data = None

            r_dict["race_metadata"] = {
                "nome_gp": race.nome_gp,
                "pista": race.pista,
                "sc_vsc_info": getattr(race, 'sc_vsc_info', None),
                "clima_temp": getattr(race, 'clima_temp', None),
                "total_voltas": getattr(race, 'total_voltas', None),
                "lobby_settings": lobby_data
            }
        else:
            r_dict["results"] = []
            r_dict["qualifying"] = {"pole_sitter": None, "results": []}
            r_dict["highlights"] = {}
            r_dict["race_metadata"] = {
                "nome_gp": race.nome_gp,
                "pista": race.pista,
                "sc_vsc_info": getattr(race, 'sc_vsc_info', None),
                "clima_temp": getattr(race, 'clima_temp', None),
                "total_voltas": getattr(race, 'total_voltas', None),
                "lobby_settings": None
            }

        return r_dict

    @staticmethod
    def find_last_races(calendar_data, grid_configs):
        """
        Identifica a última corrida concluída no calendário leve e busca seus detalhes completos
        apenas para exibição nos cards de destaque da Home.
        """
        last_races = {g['id']: None for g in grid_configs}
        
        for g_id in last_races:
            # Encontra o ID da última corrida concluída na lista leve
            concluidas = [r for r in calendar_data.get(g_id, []) if r['status'] == 'Concluida']
            if concluidas:
                last_race_light = concluidas[-1]
                # Busca o detalhe completo apenas desta corrida (Query pontual)
                full_details = CalendarService.get_race_summary(last_race_light['id'])
                last_races[g_id] = full_details
                
        return last_races