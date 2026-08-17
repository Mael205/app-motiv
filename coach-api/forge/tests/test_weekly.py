"""Tests du bilan hebdomadaire envoyé à un ami (SPEC §4.7).

C'est le seul point d'appui **externe** du produit : tout le reste est un cadre
que l'utilisateur s'impose et peut donc se lever. Ce qui se teste ici est
exactement ce qui le rendrait inutile :

* **ce qui ne doit pas sortir.** Une fuite de temps envoyée à un tiers
  transforme du bruit en jugement social, et le §4.7 dit ce qu'elle coûterait :
  une bonne raison de couper le bilan ;
* **le délai de 24 heures**, seul mécanisme volontairement difficile à désarmer
  du produit ;
* **l'accusé de lecture**, sans lequel on se croit surveillé alors qu'on ne
  l'est plus.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from forge import links, triggers, weekly
from forge.llm import set_provider
from forge.llm.fake import ScriptedProvider, UnavailableProvider
from forge.models import (
    ActionLink,
    Commitment,
    DayWindow,
    Profile,
    Project,
    RoadmapStep,
    Session,
    Track,
    WeeklyReport,
)

PARIS = ZoneInfo("Europe/Paris")
LUNDI = date(2026, 3, 2)
DIMANCHE = date(2026, 3, 8)


def paris(h: int, m: int = 0, day: date = DIMANCHE) -> datetime:
    return datetime(day.year, day.month, day.day, h, m, tzinfo=PARIS)


@pytest.fixture
def user(db):
    User = get_user_model()
    user = User.objects.create_user(username="test", password="test")
    Profile.objects.create(
        user=user,
        buddy_channel="https://discord.example/webhook",
        public_base_url="https://coach.example",
    )
    atelier = Track.objects.create(user=user, kind=Track.ATELIER)
    projet = Project.objects.create(
        user=user, track=atelier, name="Bestiaire", slot=1, weekly_commitment=3
    )
    etape = RoadmapStep.objects.create(
        project=projet, order=0, label="Écran de fiche d'espèce", state=RoadmapStep.DONE
    )
    RoadmapStep.objects.filter(pk=etape.pk).update(done_at=paris(19, 0, date(2026, 3, 4)))
    Commitment.objects.create(
        project=projet, week_start=LUNDI, planned_sessions=3, done_sessions=2
    )
    for jour in (0, 2, 4):
        Session.objects.create(
            user=user,
            project=projet,
            coach_day=LUNDI + timedelta(days=jour),
            started_at=paris(19, 0, LUNDI + timedelta(days=jour)),
            ended_at=paris(19, 25, LUNDI + timedelta(days=jour)),
            actual_minutes=25,
            status=Session.DONE,
        )
    return user


@pytest.fixture
def poste(monkeypatch):
    """Capture ce qui part vers le canal de l'ami, sans réseau."""
    envois = []

    def capter(canal: str, message: str) -> str:
        envois.append((canal, message))
        return "discord"

    monkeypatch.setattr(weekly, "_poster", capter)
    return envois


class TestContenu:
    def test_rassemble_ce_que_le_quatre_sept_demande(self, user):
        faits = weekly.collecter(user, semaine=LUNDI)
        texte = weekly.rediger(faits)

        assert "Bestiaire" in texte
        assert "1 h 15" in texte, "trois sessions de 25 minutes"
        assert "2/3" in texte, "engagements tenus contre pris"
        assert "Écran de fiche d'espèce" in texte

    def test_ne_dit_jamais_le_temps_d_ecran(self, user):
        """Le §4.7 les exclut nommément : ces signaux sont bruités."""
        texte = weekly.rediger(weekly.collecter(user, semaine=LUNDI))
        assert not weekly.contient_un_interdit(texte)

    def test_le_filet_attrape_une_phrase_qui_derape(self):
        assert weekly.contient_un_interdit("Deux heures de scroll cette semaine.") == "scroll"
        assert weekly.contient_un_interdit("Trois sessions, un jalon fermé.") == ""

    def test_la_phrase_du_modele_est_ajoutee(self, user):
        faits = weekly.collecter(user, semaine=LUNDI)
        texte = weekly.rediger(faits, synthese="Trois soirs sur cinq, le même projet.")
        assert texte.rstrip().endswith("Trois soirs sur cinq, le même projet.")

    def test_sans_modele_le_bilan_part_quand_meme(self, user, poste):
        set_provider(UnavailableProvider())
        rapport = weekly.envoyer(user, now=paris(20, 0))
        assert rapport is not None and rapport.body


class TestEnvoi:
    def test_part_avec_son_lien_de_lecture(self, user, poste):
        rapport = weekly.envoyer(user, now=paris(20, 0))
        _, message = poste[0]

        assert rapport.sent_at is not None
        assert "https://coach.example/l/" in message
        assert ActionLink.objects.filter(user=user, kind=ActionLink.VU).exists()

    def test_un_seul_bilan_par_semaine(self, user, poste):
        weekly.envoyer(user, now=paris(20, 0))
        assert weekly.envoyer(user, now=paris(20, 30)) is None
        assert WeeklyReport.objects.count() == 1

    def test_couvre_la_semaine_qui_se_termine(self, user, poste):
        """Le dimanche soir décrit la semaine du jour même, pas la précédente."""
        rapport = weekly.envoyer(user, now=paris(20, 0))
        assert rapport.week_start == LUNDI

    def test_sans_destinataire_rien_ne_part(self, db, poste):
        User = get_user_model()
        seul = User.objects.create_user(username="seul", password="x")
        Profile.objects.create(user=seul)
        Track.objects.create(user=seul, kind=Track.ATELIER)
        assert weekly.envoyer(seul, now=paris(20, 0)) is None

    def test_sans_adresse_publique_le_bilan_part_sans_lien(self, user, poste):
        """Un lien vers 127.0.0.1 ne mène nulle part chez l'ami : mieux vaut rien."""
        user.profile.public_base_url = ""
        user.profile.save(update_fields=["public_base_url"])
        weekly.envoyer(user, now=paris(20, 0))
        assert "/l/" not in poste[0][1]

    def test_un_envoi_rate_ne_laisse_pas_de_lien_vivant(self, user, monkeypatch):
        monkeypatch.setattr(weekly, "_poster", lambda canal, message: "")
        rapport = weekly.envoyer(user, now=paris(20, 0))
        assert rapport.sent_at is None
        assert not ActionLink.objects.exists(), "un secret émis pour rien traînerait"


class TestAccuseDeLecture:
    def test_le_lien_marque_le_bilan_comme_lu(self, user, poste):
        rapport = weekly.envoyer(user, now=paris(20, 0))
        lien = ActionLink.objects.get(kind=ActionLink.VU)

        links.consommer(lien)
        rapport.refresh_from_db()
        assert rapport.read_at is not None

    def test_compte_les_bilans_non_lus_consecutifs(self, user, poste):
        for semaines in range(3):
            WeeklyReport.objects.create(
                user=user,
                week_start=LUNDI - timedelta(days=7 * semaines),
                body="…",
                sent_at=timezone.now(),
            )
        assert weekly.non_lus(user) == 3

    def test_une_lecture_recente_remet_le_compteur_a_zero(self, user, poste):
        WeeklyReport.objects.create(
            user=user, week_start=LUNDI, body="…", sent_at=timezone.now(), read_at=timezone.now()
        )
        assert weekly.non_lus(user) == 0


class TestDesarmement:
    def test_la_demande_ne_coupe_rien_tout_de_suite(self, user):
        profile = user.profile
        maintenant = timezone.now()
        effective = weekly.demander_desactivation(profile, now=maintenant)

        assert effective == maintenant + weekly.DELAI_DESARMEMENT
        assert weekly.destinataire_actif(profile, now=maintenant + timedelta(hours=23))

    def test_elle_prend_effet_au_bout_de_vingt_quatre_heures(self, user):
        profile = user.profile
        maintenant = timezone.now()
        weekly.demander_desactivation(profile, now=maintenant)
        assert not weekly.destinataire_actif(profile, now=maintenant + timedelta(hours=25))

    def test_le_bilan_part_encore_pendant_le_delai(self, user, poste):
        weekly.demander_desactivation(user.profile, now=timezone.now())
        assert weekly.envoyer(user, now=paris(20, 0)) is not None

    def test_annuler_est_immediat(self, user):
        profile = user.profile
        weekly.demander_desactivation(profile, now=timezone.now() - timedelta(days=3))
        assert not weekly.destinataire_actif(profile)

        weekly.annuler_desactivation(profile)
        assert weekly.destinataire_actif(profile)

    def test_une_seconde_demande_ne_repousse_pas_l_echeance(self, user):
        profile = user.profile
        premiere = weekly.demander_desactivation(profile, now=timezone.now() - timedelta(hours=20))
        seconde = weekly.demander_desactivation(profile)
        assert premiere == seconde


class TestDeclencheur:
    @pytest.fixture(autouse=True)
    def fenetres(self, user):
        for weekday in range(7):
            DayWindow.objects.create(profile=user.profile, weekday=weekday)

    def test_part_le_dimanche_soir(self, user, poste):
        fired = triggers.check_weekly_report(user.profile, paris(20, 0))
        assert fired and fired[0]["kind"] == triggers.BILAN

    def test_ne_part_pas_un_mardi(self, user, poste):
        assert triggers.check_weekly_report(user.profile, paris(20, 0, date(2026, 3, 3))) == []

    def test_ne_part_pas_deux_fois(self, user, poste):
        triggers.check_weekly_report(user.profile, paris(20, 0))
        assert triggers.check_weekly_report(user.profile, paris(20, 3)) == []

    def test_signale_trois_bilans_sans_lecture(self, user, poste):
        from forge.models import NotificationLog

        for semaines in range(1, 4):
            WeeklyReport.objects.create(
                user=user,
                week_start=LUNDI - timedelta(days=7 * semaines),
                body="…",
                sent_at=timezone.now(),
            )
        triggers.check_weekly_report(user.profile, paris(20, 0))
        assert NotificationLog.objects.filter(kind=triggers.BILAN_NON_LU).exists()


class TestPorteDeLaPhrase:
    def test_une_phrase_factuelle_passe(self, user, poste):
        set_provider(ScriptedProvider([{"phrase": "Trois soirs travaillés, un jalon fermé."}]))
        rapport = weekly.envoyer(user, now=paris(20, 0))
        assert "Trois soirs travaillés" in rapport.body

    def test_une_felicitation_est_refusee(self, user, poste):
        set_provider(ScriptedProvider([{"phrase": "Bravo, une semaine impressionnante."}]))
        rapport = weekly.envoyer(user, now=paris(20, 0))
        assert "Bravo" not in rapport.body

    def test_une_phrase_qui_parle_de_scroll_est_ecartee(self, user, poste):
        """Dernier filet : la porte juge le registre, weekly juge le contenu."""
        set_provider(ScriptedProvider([{"phrase": "Deux heures de moins sur TikTok."}]))
        rapport = weekly.envoyer(user, now=paris(20, 0))
        assert "TikTok" not in rapport.body
