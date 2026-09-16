"""Les cartes donnent des buffs, les hauts faits donnent l'apparence (16/09/2026).

L'ancienne règle du §17 — *le loot est de l'apparence, jamais du pouvoir* —
existait contre un mode de défaillance précis : récompenser la chance plutôt que
le travail. Elle est levée, donc ce qui la remplaçait doit être tenu **ici**,
sans quoi personne ne s'apercevra de sa disparition :

- une carte ne tombe jamais sans travail (le tirage est déjà payé) ;
- une carte est une **charge**, jamais un passif : la malchance coûte une
  occasion, pas une puissance qui manque tous les jours ;
- **aucune carte ne touche au cadre**, sauf le sas. C'est la frontière qui se
  perdra au premier effet ajouté à la va-vite.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from rest_framework.test import APIClient

from forge import progression, services
from forge.models import Garde, GardeDay, LootCard, Profile, Project, Session, Track
from forge.rules import buffs as buff_rules

PARIS = ZoneInfo("Europe/Paris")
LUNDI = date(2026, 9, 14)


@pytest.fixture
def user(db, django_user_model):
    user = django_user_model.objects.create_user(username="test", password="test")
    Profile.objects.create(user=user)
    Track.objects.create(user=user, kind=Track.ATELIER)
    return user


def carte(user, key: str, charges: int = 1) -> LootCard:
    buff = buff_rules.PAR_CLE[key]
    return LootCard.objects.create(
        user=user, key=key, rarity=buff.rarity, kind="buff", copies=charges
    )


class TestLaFrontiere:
    """Ce qu'aucune carte n'a le droit de faire."""

    def test_une_seule_carte_efface_une_soiree(self):
        """La limite haute du système. Au-delà, une carte remplacerait une séance."""
        effacent = [b for b in buff_rules.CATALOGUE if buff_rules.efface_une_soiree(b.effect)]

        assert len(effacent) == 1
        assert effacent[0].rarity == "legendaire", "la seule qui rende une soirée est la plus rare"

    def test_les_autres_deplacent_ou_allegent_mais_n_effacent_pas(self):
        """« Carte blanche » change le projet, « Report » le jour, « Petit pas » la barre."""
        for effect in (buff_rules.CARTE_BLANCHE, buff_rules.REPORT, buff_rules.PETIT_PAS):
            assert not buff_rules.efface_une_soiree(effect)

    def test_aucune_carte_ne_touche_au_streak_ni_au_rang(self):
        """Une carte qui rendrait un bouclier ferait du cœur du système un objet."""
        # « couvre » n'est pas dans la liste : « Plein ciel » nomme le couvre-feu
        # comme **borne**, ce qui est l'inverse d'y toucher.
        interdits = ("streak", "bouclier", "shield", "rang", "rank", "slot", "blocage")

        for buff in buff_rules.CATALOGUE:
            assert not any(mot in buff.effect for mot in interdits)

    def test_aucune_carte_ne_recule_le_blocage_ni_le_couvre_feu(self):
        """Les deux heures du régime (§11.12) sont hors d'atteinte, sans exception."""
        from forge.rules import regime as regime_rules

        heures = {"blocage", "couvre_feu", "sas_minutes"}
        for buff in buff_rules.CATALOGUE:
            assert buff.effect not in heures
        assert regime_rules.pour(1).blocage == regime_rules.pour_jour(1, 0).blocage

    def test_le_plancher_ne_descend_jamais_sous_quinze_minutes(self):
        """« Petit pas » allège la barre, il ne supprime pas le démarrage."""
        assert buff_rules.PETIT_PAS_MINUTES == 15

    def test_le_catalogue_n_invente_aucun_effet(self):
        for buff in buff_rules.CATALOGUE:
            assert buff.effect in buff_rules.EFFETS

    def test_chaque_carte_dit_ce_qu_elle_fait(self):
        for buff in buff_rules.CATALOGUE:
            assert buff.ligne and buff.lore


class TestLaRotation:
    def test_chaque_saison_a_son_lot(self):
        un, deux = buff_rules.lot_de_saison(1), buff_rules.lot_de_saison(2)

        assert un != deux
        assert len(un) == buff_rules.TAILLE_DU_LOT

    def test_le_lot_est_toujours_le_meme_pour_une_saison(self):
        """Un lot tiré au sort à chaque lecture ferait clignoter le catalogue."""
        assert buff_rules.lot_de_saison(3) == buff_rules.lot_de_saison(3)

    def test_deux_saisons_voisines_partagent_une_partie_du_lot(self):
        """Une carte manquée revient — plus tard, pas jamais."""
        commun = set(buff_rules.lot_de_saison(1)) & set(buff_rules.lot_de_saison(2))

        assert commun

    def test_tout_le_catalogue_finit_par_sortir(self):
        vus = set()
        for index in range(1, len(buff_rules.CATALOGUE) + 1):
            vus |= set(buff_rules.lot_de_saison(index))

        assert vus == set(buff_rules.CATALOGUE)


@pytest.mark.django_db
class TestDepenserUneCharge:
    def test_armer_consomme_une_charge(self, user):
        carte(user, "respiration", charges=2)

        progression.armer_buff(user, "respiration", today=LUNDI)

        assert LootCard.objects.get(user=user, key="respiration").copies == 1

    def test_sans_charge_rien_ne_s_arme(self, user):
        with pytest.raises(ValueError, match="Aucune charge"):
            progression.armer_buff(user, "respiration", today=LUNDI)

    def test_deux_rallonges_ne_s_empilent_pas(self, user):
        """Deux rallonges sur le même sas donneraient une durée que rien n'a calibrée."""
        carte(user, "respiration")
        carte(user, "longue_respiration")

        progression.armer_buff(user, "respiration", today=LUNDI)

        with pytest.raises(ValueError, match="doublon"):
            progression.armer_buff(user, "longue_respiration", today=LUNDI)

    def test_un_buff_arme_hier_ne_joue_pas_aujourd_hui(self, user):
        carte(user, "respiration")
        progression.armer_buff(user, "respiration", today=LUNDI - timedelta(days=1))

        assert progression.buff_arme(user, buff_rules.SAS_PLUS, day=LUNDI) is None


@pytest.mark.django_db
class TestLesCartesDeSas:
    def client(self, user):
        api = APIClient()
        api.force_authenticate(user=user)
        return api

    def test_la_rallonge_allonge_le_sas(self, user):
        carte(user, "longue_respiration")   # +20 min
        progression.armer_buff(user, "longue_respiration", today=_aujourdhui(user))

        reponse = self.client(user).post("/api/relax/start")

        assert reponse.json()["minutes"] == 40

    def test_le_blanc_seing_epargne_la_journee_de_reseaux(self, user):
        garde = Garde.objects.create(
            user=user, name="Réseaux", weekly_budget=2, auto_category="reseaux"
        )
        carte(user, "blanc_seing")
        progression.armer_buff(user, "blanc_seing", today=_aujourdhui(user))

        self.client(user).post("/api/relax/start")

        assert not GardeDay.objects.filter(garde=garde).exists()

    def test_sans_carte_le_sas_coute_sa_journee(self, user):
        garde = Garde.objects.create(
            user=user, name="Réseaux", weekly_budget=2, auto_category="reseaux"
        )

        self.client(user).post("/api/relax/start")

        assert GardeDay.objects.get(garde=garde).occurred is True

    def test_le_second_souffle_rouvre_un_sas_deja_pris(self, user):
        client = self.client(user)
        client.post("/api/relax/start")
        refus = client.post("/api/relax/start")
        assert refus.status_code == 409

        carte(user, "second_souffle")
        progression.armer_buff(user, "second_souffle", today=_aujourdhui(user))
        deuxieme = client.post("/api/relax/start")

        assert deuxieme.status_code == 201


@pytest.mark.django_db
class TestLesSkinsViennentDesHautsFaits:
    def test_un_haut_fait_donne_une_apparence(self, user):
        obtenus = progression.grant_skins_for(user, ["premier_sang"])

        assert obtenus and obtenus[0]["kind"] != "buff"
        assert LootCard.objects.filter(user=user, reason="haut_fait").count() == 1

    def test_le_meme_haut_fait_ne_donne_pas_deux_fois(self, user):
        progression.grant_skins_for(user, ["premier_sang"])
        progression.grant_skins_for(user, ["premier_sang"])

        assert LootCard.objects.filter(user=user, reason="haut_fait").count() == 1

    def test_deux_hauts_faits_donnent_deux_apparences_differentes(self, user):
        obtenus = progression.grant_skins_for(user, ["premier_sang", "premiere_etape"])

        assert len({c["key"] for c in obtenus}) == 2

    def test_une_apparence_n_est_jamais_une_carte_de_buff(self, user):
        """Sinon une apparence donnerait du pouvoir, et on aurait tout inversé pour rien."""
        progression.grant_skins_for(user, ["premier_sang", "premiere_etape"])

        for ligne in LootCard.objects.filter(user=user, reason="haut_fait"):
            assert ligne.key not in buff_rules.PAR_CLE


def _aujourdhui(user):
    from django.utils import timezone as dj

    from forge.rules.calendar import coach_day

    profile = user.profile
    return coach_day(dj.now(), profile.timezone_name, profile.day_rollover_hour)


@pytest.mark.django_db
class TestLesQuatreAutresCartes:
    """Ce que les cartes rendent, c'est du temps — jamais des chiffres."""

    def client(self, user):
        api = APIClient()
        api.force_authenticate(user=user)
        return api

    def test_la_bouffee_d_air_supprime_l_attente(self, user):
        carte(user, "bouffee_d_air")
        progression.armer_buff(user, "bouffee_d_air", today=_aujourdhui(user))

        reponse = self.client(user).post("/api/relax/start")

        assert reponse.json()["attente_secondes"] == 0

    def test_sans_carte_l_attente_reste(self, user):
        reponse = self.client(user).post("/api/relax/start")

        assert reponse.json()["attente_secondes"] == 60

    def test_plein_ciel_court_jusqu_au_couvre_feu_et_s_y_arrete(self, user):
        """La carte la plus généreuse du jeu n'ouvre toujours pas la nuit."""
        from forge.models import RelaxWindow

        carte(user, "plein_ciel")
        progression.armer_buff(user, "plein_ciel", today=_aujourdhui(user))

        self.client(user).post("/api/relax/start")

        fenetre = RelaxWindow.objects.get(user=user)
        fin = fenetre.ends_at.astimezone(PARIS)
        assert (fin.hour, fin.minute) <= (23, 0), "le couvre-feu tient"

    def test_la_reserve_arme_un_sas_pour_demain(self, user):
        jour = _aujourdhui(user)
        carte(user, "reserve")
        progression.armer_buff(user, "reserve", today=jour)

        self.client(user).post("/api/relax/start")

        demain = progression.buff_arme(user, buff_rules.SAS_SECOND, day=jour + timedelta(days=1))
        assert demain is not None

    def test_le_silence_fait_taire_les_notifications_pas_le_cadre(self, user):
        """Ce qui se tait est le rappel. Le blocage ne change pas d'un pouce."""
        from datetime import datetime as dt

        from forge import triggers
        from forge.models import NotificationLog
        from forge.notifications import Notification

        jour = _aujourdhui(user)
        carte(user, "silence")
        progression.armer_buff(user, "silence", today=jour)

        envoye = triggers._deliver(
            user, "test", jour, Notification(title="Gardien", body="20h30 est passé.")
        )

        assert envoye is False
        assert not NotificationLog.objects.filter(user=user).exists()
        # Le cadre, lui, est intact : le blocage s'arme toujours le soir venu.
        tard = datetime.combine(jour, time(22, 30), tzinfo=PARIS)
        assert "armed" in services.agent_state(user, now=tard)["block_scroll"]


@pytest.mark.django_db
class TestLesCartesDeSoiree:
    """Ce qui se déplace, ce qui s'allège, et la seule chose qui s'efface."""

    def prevu(self, user, nom="Bot STS2", jour_semaine=None):
        from forge.models import TimeSlot

        jour = _aujourdhui(user)
        projet = Project.objects.create(
            user=user, track=Track.objects.get(user=user), name=nom, slot=1
        )
        TimeSlot.objects.create(
            project=projet,
            weekday=jour.weekday() if jour_semaine is None else jour_semaine,
            start_time=time(20, 30),
        )
        return projet

    def poser(self, user, projet, minutes):
        from django.utils import timezone as dj

        debut = dj.now() - timedelta(minutes=minutes)
        return Session.objects.create(
            user=user,
            project=projet,
            planned_minutes=minutes,
            actual_minutes=minutes,
            status=Session.DONE,
            coach_day=_aujourdhui(user),
            started_at=debut,
            ended_at=dj.now(),
        )

    def test_carte_blanche_laisse_un_autre_projet_tenir_la_journee(self, user):
        jour = _aujourdhui(user)
        self.prevu(user)
        autre = Project.objects.create(
            user=user, track=Track.objects.get(user=user), name="Proto UE5", slot=2
        )
        self.poser(user, autre, 30)
        assert not services.projet_du_jour(user, today=jour).tenu

        carte(user, "carte_blanche")
        progression.armer_buff(user, "carte_blanche", today=jour)

        assert services.projet_du_jour(user, today=jour).tenu

    def test_carte_blanche_ne_dispense_pas_de_travailler(self, user):
        """Ce qui est rendu, c'est le choix du projet — jamais la soirée."""
        jour = _aujourdhui(user)
        self.prevu(user)
        carte(user, "carte_blanche")
        progression.armer_buff(user, "carte_blanche", today=jour)

        assert not services.projet_du_jour(user, today=jour).tenu

    def test_petit_pas_descend_la_barre_a_quinze(self, user):
        jour = _aujourdhui(user)
        projet = self.prevu(user)
        self.poser(user, projet, 15)
        assert not services.projet_du_jour(user, today=jour).tenu

        carte(user, "petit_pas")
        progression.armer_buff(user, "petit_pas", today=jour)

        etat = services.projet_du_jour(user, today=jour)
        assert etat.tenu and etat.attendus[0].requis == 15

    def test_le_report_libere_ce_soir_et_charge_demain(self, user):
        jour = _aujourdhui(user)
        self.prevu(user)
        carte(user, "report")
        progression.armer_buff(user, "report", today=jour)

        assert services.projet_du_jour(user, today=jour).libre

        demain = services.projet_du_jour(user, today=jour + timedelta(days=1))
        assert [a.name for a in demain.attendus] == ["Bot STS2"], "la dette se paie demain"

    def test_la_treve_pose_un_vrai_jour_off(self, user):
        """C'est le §11.5 qui rend la journée neutre, pas un cas particulier."""
        from forge.models import DayOff

        jour = _aujourdhui(user)
        self.prevu(user)
        carte(user, "treve")
        progression.armer_buff(user, "treve", today=jour)

        assert services.projet_du_jour(user, today=jour).libre
        assert DayOff.objects.filter(user=user, date=jour).exists()
