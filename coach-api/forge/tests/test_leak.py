"""Tests du rapport de fuite de temps (SPEC §13.2, §4.7, §17).

Le §13.2 dit son but en une phrase : « trouver l'heure charnière, pas
culpabiliser sur un total ». Les tests portent donc sur la charnière, sur la
conversion du coût, et sur la ligne à ne pas franchir — ces chiffres ne sortent
jamais vers l'ami.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model

from forge import leak as leak_service
from forge import weekly
from forge.models import Profile, Project, Session, Signal, Track
from forge.rules import leak

PARIS = ZoneInfo("Europe/Paris")
LUNDI = date(2026, 3, 2)


def h(heure: int, minute: int = 0) -> int:
    return heure * 60 + minute


class TestRepartition:
    def test_une_fenetre_dans_une_seule_tranche(self):
        tranches = leak.repartir([(h(19), h(19, 25), 25)])
        assert [(t.debut, t.minutes) for t in tranches] == [(h(19), 25)]

    def test_une_fenetre_a_cheval_est_etalee_au_prorata(self):
        tranches = leak.repartir([(h(19, 15), h(20, 15), 60)])
        assert [(t.libelle, t.minutes) for t in tranches] == [
            ("19h00", 15),
            ("19h30", 30),
            ("20h00", 15),
        ]

    def test_les_miettes_ne_sont_pas_affichees(self):
        """Deux minutes à 3h du matin ne décrivent aucune habitude."""
        assert leak.repartir([(h(3), h(3, 2), 2)]) == []


class TestCharniere:
    def test_c_est_la_montee_et_pas_le_sommet(self):
        """Le sommet est au milieu du décrochage : il est déjà trop tard."""
        tranches = [
            leak.Tranche(h(19), 20),
            leak.Tranche(h(19, 30), 120),
            leak.Tranche(h(20), 150),
            leak.Tranche(h(20, 30), 160),
        ]
        assert leak.charniere(tranches).libelle == "19h30"

    def test_un_frissonnement_ne_fait_pas_une_charniere(self):
        tranches = [leak.Tranche(h(19), 12), leak.Tranche(h(19, 30), 20)]
        assert leak.charniere(tranches) is None

    def test_sans_donnees_il_n_y_a_pas_de_charniere(self):
        assert leak.charniere([]) is None


class TestCout:
    def test_il_convertit_en_sessions_et_en_points_de_vie(self):
        valeur = leak.cout(100, degats_par_session=25, pv_du_boss=800)
        assert valeur.sessions == 4
        assert "4 session(s) de 25 min" in valeur.phrase
        assert "12 % de la vie du boss" in valeur.phrase

    def test_sans_boss_il_s_arrete_aux_sessions(self):
        assert "boss" not in leak.cout(100).phrase

    def test_il_ne_juge_pas(self):
        """Le §17 interdit le score de productivité. Un taux de change n'en est pas un."""
        phrase = leak.cout(300, degats_par_session=25, pv_du_boss=800).phrase.lower()
        for mot in ("perdu", "gaspillé", "seulement", "trop", "mauvais"):
            assert mot not in phrase

    def test_la_part_du_boss_ne_depasse_jamais_tout(self):
        assert leak.cout(100000, degats_par_session=25, pv_du_boss=800).part_du_boss == 1.0


class TestDeclencheurs:
    def test_il_compte_sans_conclure(self):
        trouves = leak.declencheurs(["juste après une session"] * 3 + ["avant toute session"])
        assert trouves[0].quoi == "juste après une session"
        assert trouves[0].part == 0.75

    def test_sans_observation_il_ne_dit_rien(self):
        assert leak.declencheurs([]) == []


@pytest.mark.django_db
class TestRapportComplet:
    @pytest.fixture
    def user(self):
        User = get_user_model()
        user = User.objects.create_user(username="test", password="test")
        Profile.objects.create(user=user)
        Track.objects.create(user=user, kind=Track.ATELIER)
        return user

    def scroll(self, user, *, jour: date, debut: int, minutes: int, source: str = "agent"):
        depart = datetime(jour.year, jour.month, jour.day, debut // 60, debut % 60, tzinfo=PARIS)
        Signal.objects.create(
            user=user,
            source=source,
            category="scroll_passif",
            minutes=minutes,
            day=jour,
            started_at=depart,
            ended_at=depart + timedelta(minutes=minutes),
        )

    def test_il_trouve_l_heure_ou_ca_commence(self, user):
        for jour in range(10):
            self.scroll(user, jour=LUNDI + timedelta(days=jour), debut=h(19, 30), minutes=45)

        rapport = leak_service.rapport(user, today=LUNDI + timedelta(days=10))
        assert rapport["charniere"]["libelle"] == "19h30"

    def test_les_fenetres_sans_horodatage_comptent_dans_le_cout_pas_dans_l_heure(self, user):
        Signal.objects.create(
            user=user, source="mobile", category="scroll_passif", minutes=120, day=LUNDI
        )
        rapport = leak_service.rapport(user, today=LUNDI)

        assert rapport["tranches"] == []
        assert rapport["sans_horodatage"] == 120
        assert rapport["cout_total"]["minutes"] == 120

    def test_il_compare_le_pc_et_le_telephone(self, user):
        self.scroll(user, jour=LUNDI, debut=h(20), minutes=60, source="agent")
        self.scroll(user, jour=LUNDI + timedelta(days=20), debut=h(20), minutes=90, source="mobile")

        rapport = leak_service.rapport(user, today=LUNDI + timedelta(days=21))
        assert rapport["par_surface"]["mobile"]["semaine"] == 90
        assert rapport["par_surface"]["pc"]["avant"] == 60

    def test_il_dit_ce_qui_precede_le_decrochage(self, user):
        projet = Project.objects.create(
            user=user, track=Track.objects.get(user=user), name="Bestiaire", slot=1
        )
        Session.objects.create(
            user=user,
            project=projet,
            coach_day=LUNDI,
            started_at=datetime(2026, 3, 2, 19, tzinfo=PARIS),
            ended_at=datetime(2026, 3, 2, 19, 25, tzinfo=PARIS),
            actual_minutes=25,
            status=Session.DONE,
        )
        self.scroll(user, jour=LUNDI, debut=h(19, 40), minutes=40)

        rapport = leak_service.rapport(user, today=LUNDI)
        assert rapport["declencheurs"][0]["quoi"] == "juste après une session"

    def test_rien_de_tout_ca_ne_part_chez_l_ami(self, user):
        """§4.7 et §13.2 : ces signaux ne sortent pas. La garde est explicite."""
        self.scroll(user, jour=LUNDI, debut=h(20), minutes=120)
        faits = weekly.collecter(user, semaine=LUNDI)
        texte = weekly.rediger(faits)

        assert not weekly.contient_un_interdit(texte)
        assert "scroll" not in texte.lower()
        assert "120" not in texte
