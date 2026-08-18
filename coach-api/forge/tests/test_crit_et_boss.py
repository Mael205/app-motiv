"""Le coup critique, les phases de boss, le butin d'étape et le dernier round.

Quatre ajouts du 17 août 2026 qui partagent une contrainte : ils ajoutent du
jeu **sans toucher à la mesure**. Le §17 pose la règle — le cosmétique ne
devient jamais du pouvoir — et chaque test ci-dessous vérifie qu'un de ces
quatre ne l'a pas franchie.

Ce qui se teste, dans l'ordre : que le critique double l'XP et rien d'autre,
que les phases ne changent aucune règle et ne se rejouent pas, que l'étape
terminée ne se paie qu'une fois, et que le dernier round n'accorde rien.
"""

import random
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from forge import services
from forge.models import (
    DayWindow,
    LootCard,
    LootDraw,
    Profile,
    Project,
    RoadmapStep,
    Season,
    Session,
    Track,
)
from forge.rules import bossphases as phases
from forge.rules import crit as crit_rules
from forge.rules import achievements as achievement_rules
from forge.rules import seasons as season_rules

PARIS = ZoneInfo("Europe/Paris")
LUNDI = date(2026, 3, 2)


class DesPipes(random.Random):
    """Des dés qui rendent ce qu'on leur demande, dans l'ordre."""

    def __init__(self, tirages):
        super().__init__()
        self._tirages = list(tirages)

    def random(self):
        return self._tirages.pop(0) if self._tirages else 1.0


# --------------------------------------------------------------------------
# Le coup critique
# --------------------------------------------------------------------------

class TestLeCritique:
    def test_il_double_l_xp(self):
        coup = crit_rules.roll(xp=100, draws_since_crit=0, rng=DesPipes([0.01]))
        assert coup.hit and coup.xp_after == 200 and coup.bonus == 100

    def test_il_ne_tombe_pas_a_chaque_fois(self):
        coup = crit_rules.roll(xp=100, draws_since_crit=0, rng=DesPipes([0.99]))
        assert not coup.hit and coup.xp_after == 100

    def test_une_session_a_zero_xp_ne_tire_pas(self):
        """Le double de rien est rien, et l'annoncer serait un mensonge visible."""
        coup = crit_rules.roll(xp=0, draws_since_crit=99, rng=DesPipes([0.0]))
        assert not coup.hit and coup.xp_after == 0

    def test_la_pitie_finit_par_le_donner(self):
        coup = crit_rules.roll(
            xp=40, draws_since_crit=crit_rules.PITY, rng=DesPipes([0.99])
        )
        assert coup.hit and coup.forced

    def test_la_pitie_le_dit(self):
        coup = crit_rules.roll(xp=40, draws_since_crit=crit_rules.PITY, rng=DesPipes([0.99]))
        assert "attendre" in coup.line


@pytest.mark.django_db
class TestLeCritiqueEnSession:
    def test_il_ne_touche_ni_les_minutes_ni_le_boss(self, user, monkeypatch):
        """La comparaison au fantôme se fait en minutes (§12.7) : un tirage ne
        doit pas pouvoir gagner une course."""
        monkeypatch.setattr(
            crit_rules, "roll",
            lambda **kw: crit_rules.Crit(
                hit=True, multiplier=2, forced=False,
                xp_before=kw["xp"], xp_after=kw["xp"] * 2,
            ),
        )
        avant = Season.objects.get(user=user).boss.damage_taken
        resultat = cloturer(user, minutes=25)

        assert resultat["crit"]["multiplier"] == 2
        assert resultat["minutes"] == 25
        assert resultat["boss_damage"] == season_rules.damage_of(minutes=25)
        apres = Season.objects.get(user=user).boss.damage_taken
        assert apres - avant == season_rules.damage_of(minutes=25)

    def test_le_tirage_est_grave_et_ne_se_rejoue_pas(self, user, monkeypatch):
        monkeypatch.setattr(
            crit_rules, "roll",
            lambda **kw: crit_rules.Crit(
                hit=True, multiplier=2, forced=False,
                xp_before=kw["xp"], xp_after=kw["xp"] * 2,
            ),
        )
        resultat = cloturer(user, minutes=25)
        session = Session.objects.get(id=resultat["session_id"])
        assert session.xp_breakdown["crit"] is True
        assert session.xp_awarded == session.xp_breakdown["base_total"] * 2

    def test_sans_critique_le_detail_le_dit_aussi(self, user, monkeypatch):
        monkeypatch.setattr(
            crit_rules, "roll",
            lambda **kw: crit_rules.Crit(
                hit=False, multiplier=1, forced=False,
                xp_before=kw["xp"], xp_after=kw["xp"],
            ),
        )
        resultat = cloturer(user, minutes=25)
        assert resultat["crit"] is None
        session = Session.objects.get(id=resultat["session_id"])
        assert session.xp_breakdown["crit"] is False
        assert session.xp_awarded == session.xp_breakdown["base_total"]


# --------------------------------------------------------------------------
# Les phases de boss
# --------------------------------------------------------------------------

class TestLesPhases:
    def test_trois_phases_aux_deux_seuils(self):
        assert phases.index_for(1.0) == 1
        assert phases.index_for(0.51) == 1
        assert phases.index_for(0.49) == 2
        assert phases.index_for(0.26) == 2
        assert phases.index_for(0.10) == 3

    def test_le_nom_change_a_chaque_phase(self):
        noms = {
            phases.phase_for("procrastin", "Procrastin", r).name
            for r in (0.9, 0.4, 0.1)
        }
        assert len(noms) == 3

    def test_un_boss_inconnu_retombe_sur_le_gabarit(self):
        phase = phases.phase_for("inconnu", "Le Machin", 0.1)
        assert "Le Machin" in phase.name

    def test_le_franchissement_ne_se_joue_qu_une_fois(self):
        assert phases.crossed("procrastin", "P", before=0.6, after=0.4) is not None
        assert phases.crossed("procrastin", "P", before=0.4, after=0.3) is None

    def test_un_boss_qui_remonte_ne_defranchit_rien(self):
        """La régénération des jours ratés (§14) ne reprend pas un palier en
        public : le §17 interdit au système d'ajouter une punition affichée."""
        assert phases.crossed("procrastin", "P", before=0.4, after=0.6) is None

    def test_aucune_phase_ne_porte_de_multiplicateur(self):
        for cle in phases.PHASES:
            for ratio in (0.9, 0.4, 0.1):
                phase = phases.phase_for(cle, "x", ratio)
                assert not hasattr(phase, "damage_multiplier")
                assert not hasattr(phase, "xp_multiplier")


@pytest.mark.django_db
class TestLesPhasesEnSession:
    def test_la_bascule_sort_a_la_cloture(self, user):
        boss = Season.objects.get(user=user).boss
        boss.damage_taken = boss.max_hp // 2 - 10
        boss.save()

        resultat = cloturer(user, minutes=25)
        assert resultat["boss_phase"]["index"] == 2
        assert resultat["boss_phase"]["name"] != resultat["boss_phase"]["previous_name"]

    def test_elle_ne_ressort_pas_a_la_session_suivante(self, user):
        boss = Season.objects.get(user=user).boss
        boss.damage_taken = boss.max_hp // 2 - 10
        boss.save()
        cloturer(user, minutes=25)
        assert cloturer(user, minutes=25, jour=LUNDI + timedelta(days=1))["boss_phase"] is None

    def test_la_mort_du_boss_prime_sur_la_phase(self, user):
        """Deux cérémonies sur le même clic s'annulent."""
        boss = Season.objects.get(user=user).boss
        boss.damage_taken = boss.max_hp - 5
        boss.save()
        resultat = cloturer(user, minutes=25)
        assert resultat["boss_killed"] is not None
        assert resultat["boss_phase"] is None


# --------------------------------------------------------------------------
# Le butin d'étape
# --------------------------------------------------------------------------

@pytest.mark.django_db
class TestLeButinDEtape:
    def test_terminer_une_etape_lache_une_carte(self, user):
        etape = RoadmapStep.objects.create(
            project=Project.objects.get(user=user), label="Brancher le raycast"
        )
        resultat = services.complete_step(user, etape, today=LUNDI)
        assert resultat["card"] is not None
        assert LootDraw.objects.filter(user=user, reason="etape").count() == 1

    def test_une_etape_deja_finie_ne_repaie_rien(self, user):
        """Un double-clic infligeait une heure de dégâts pour du travail
        qui n'avait pas eu lieu."""
        etape = RoadmapStep.objects.create(
            project=Project.objects.get(user=user), label="Brancher le raycast"
        )
        premier = services.complete_step(user, etape, today=LUNDI)
        second = services.complete_step(user, etape, today=LUNDI)

        assert second["already_done"] and second["boss_damage"] == 0
        assert second["card"] is None
        assert LootDraw.objects.count() == 1
        boss = Season.objects.get(user=user).boss
        assert boss.damage_taken == premier["boss_damage"]

    def test_dix_etapes_dans_la_saison_donnent_le_chirurgien(self, user):
        """Le haut fait était déclaré depuis le premier jour et n'avait jamais
        eu d'endroit où se déclencher."""
        # Les étapes se datent à l'horloge : la saison doit couvrir aujourd'hui.
        aujourdhui = timezone.localdate()
        saison = Season.objects.get(user=user)
        saison.starts_on = aujourdhui - timedelta(days=1)
        saison.ends_on = aujourdhui + timedelta(days=20)
        saison.save(update_fields=["starts_on", "ends_on"])

        projet = Project.objects.get(user=user)
        obtenus = []
        seuil = achievement_rules.PAR_CLE["chirurgien"].seuil
        for i in range(seuil):
            etape = RoadmapStep.objects.create(project=projet, label=f"Étape {i}", order=i)
            obtenus += services.complete_step(user, etape, today=aujourdhui)["achievements"]
        assert "chirurgien" in [a["key"] for a in obtenus]


# --------------------------------------------------------------------------
# Le dernier round
# --------------------------------------------------------------------------

class TestLeDernierRound:
    def test_il_ne_s_allume_que_les_trois_derniers_jours(self):
        assert not season_rules.final_round(days_left=8, current_hp=500).active
        assert season_rules.final_round(days_left=3, current_hp=500).active
        assert season_rules.final_round(days_left=0, current_hp=500).active

    def test_la_vie_se_lit_en_sessions(self):
        etat = season_rules.final_round(days_left=2, current_hp=100, session_minutes=25)
        assert etat.sessions_left == 4
        assert "4 sessions de 25 min" in etat.line

    def test_il_dit_quand_le_boss_tiendra(self):
        etat = season_rules.final_round(days_left=1, current_hp=100_000)
        assert not etat.reachable and "tiendra" in etat.line

    def test_il_n_accorde_aucun_bonus(self):
        """Un bonus de fin encouragerait le sur-régime du §0.2 au pire moment."""
        etat = season_rules.final_round(days_left=1, current_hp=100)
        for champ in ("multiplier", "bonus", "xp", "damage"):
            assert not hasattr(etat, champ)

    def test_un_boss_deja_mort_ne_demande_plus_rien(self):
        etat = season_rules.final_round(days_left=2, current_hp=0, is_dead=True)
        assert etat.sessions_left == 0 and "tombé" in etat.line


# --------------------------------------------------------------------------
# Décor commun
# --------------------------------------------------------------------------

@pytest.fixture
def user(db):
    User = get_user_model()
    user = User.objects.create_user(username="test", password="test")
    profile = Profile.objects.create(user=user)
    for weekday in range(7):
        DayWindow.objects.create(profile=profile, weekday=weekday)
    atelier = Track.objects.create(user=user, kind=Track.ATELIER)
    Project.objects.create(user=user, track=atelier, name="Bestiaire", slot=1, branch="ue5")
    services.open_season(user, starts_on=LUNDI, stake=100)
    return user


def cloturer(user, *, minutes: int, jour: date = LUNDI) -> dict:
    """Une session close, de bout en bout, comme le ferait l'API."""
    session = Session.objects.create(
        user=user,
        project=Project.objects.get(user=user),
        season=Season.objects.filter(user=user).first(),
        coach_day=jour,
        started_at=datetime(jour.year, jour.month, jour.day, 19, tzinfo=PARIS),
        planned_minutes=minutes,
        status=Session.RUNNING,
    )
    return services.end_session(
        session,
        now=datetime(jour.year, jour.month, jour.day, 19, tzinfo=PARIS)
        + timedelta(minutes=minutes),
    )
