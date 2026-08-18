"""Le fuseau horaire, le remplaçant de l'ami, et le gardien de secours local.

Les trois dernières situations que le système ne savait pas encaisser. Elles
n'ont rien en commun sauf leur forme : chacune est un cas où le produit
continuait de fonctionner **en silence** alors qu'il ne mesurait plus rien de
juste.

Voyager décale la fenêtre du soir sans le dire. Un ami qui n'ouvre plus les
bilans laisse croire à une surveillance qui n'existe pas. Un serveur
injoignable à 21h30 fait disparaître le gardien sans que personne ne le sache.
Dans les trois cas, le tort n'est pas la panne — c'est qu'elle ne se voie pas.
"""

from datetime import date, datetime, timedelta, timezone as tz
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone


def _charger_gardien():
    """Le module de l'agent, importé par son chemin.

    Il ne vit pas dans Django et n'est pas installable : l'agent tourne sur une
    machine Windows, seul, avec la bibliothèque standard. C'est justement ce qui
    lui permet de parler quand le serveur ne répond plus.
    """
    import importlib.util
    import sys
    from pathlib import Path

    chemin = Path(__file__).resolve().parents[3] / "coach-agent" / "gardien.py"
    spec = importlib.util.spec_from_file_location("gardien_agent", chemin)
    module = importlib.util.module_from_spec(spec)
    sys.modules["gardien_agent"] = module
    spec.loader.exec_module(module)
    return module


from forge import weekly
from forge.models import DayWindow, Profile, WeeklyReport
from forge.rules import timezones as regles

gardien = _charger_gardien()

PARIS = ZoneInfo("Europe/Paris")
HIVER = datetime(2026, 1, 15, 12, tzinfo=tz.utc)


class TestLeFuseau:
    def test_un_vrai_decalage_est_propose(self):
        p = regles.proposer("Europe/Paris", "America/Montreal", at=HIVER)
        assert p.valide and p.ecart_minutes == -360
        assert "6h" in p.line and "Montreal" in p.line

    def test_le_meme_fuseau_ne_propose_rien(self):
        assert not regles.proposer("Europe/Paris", "Europe/Paris", at=HIVER).valide

    def test_deux_noms_au_meme_decalage_ne_proposent_rien(self):
        """Proposer une bascule qui ne change rien ce soir serait du bruit, et
        le bruit apprend à ignorer les vraies."""
        p = regles.proposer("Europe/Paris", "Europe/Madrid", at=HIVER)
        assert not p.valide and "rien ne bouge" in p.line

    def test_un_fuseau_inconnu_est_refuse_sans_planter(self):
        p = regles.proposer("Europe/Paris", "Mars/Olympus", at=HIVER)
        assert not p.valide and "inconnu" in p.line

    def test_l_ecart_suit_l_heure_d_ete(self):
        """L'heure d'été ne bascule pas partout le même jour.

        New York passe à l'heure d'été le 8 mars 2026, Paris le 29. Entre les
        deux, l'écart n'est pas celui du reste de l'année — et un décalage figé
        dans une constante se tromperait de soixante minutes trois semaines
        par an, précisément sur la fenêtre du soir.
        """
        assert regles.ecart("Europe/Paris", "America/New_York", at=HIVER) == -360
        entre_deux = datetime(2026, 3, 15, 12, tzinfo=tz.utc)
        assert regles.ecart("Europe/Paris", "America/New_York", at=entre_deux) == -300
        apres = datetime(2026, 3, 30, 12, tzinfo=tz.utc)
        assert regles.ecart("Europe/Paris", "America/New_York", at=apres) == -360


@pytest.mark.django_db
class TestLeRemplacantDeLAmi:
    def test_le_changement_est_immediat(self, user, monkeypatch):
        """Remplacer n'est pas arrêter : le bilan continue de partir."""
        envois = _capturer(monkeypatch)
        profil = user.profile
        weekly.remplacer_destinataire(profil, "https://hooks.example/nouveau")

        profil.refresh_from_db()
        assert profil.buddy_channel == "https://hooks.example/nouveau"
        assert weekly.destinataire_actif(profil)
        assert profil.buddy_disable_requested_at is None
        assert len(envois) == 1  # l'ancien a été prévenu

    def test_l_ancien_destinataire_est_prevenu(self, user, monkeypatch):
        """C'est ce qui empêche le remplacement d'être un désarmement déguisé."""
        envois = _capturer(monkeypatch)
        weekly.remplacer_destinataire(user.profile, "https://hooks.example/nouveau")
        canal, message = envois[0]
        assert canal == "https://hooks.example/ancien"
        assert "quelqu'un d'autre" in message

    def test_un_canal_vide_est_refuse(self, user, monkeypatch):
        """Ça, c'est un arrêt — et l'arrêt a son chemin, à 24 heures."""
        _capturer(monkeypatch)
        with pytest.raises(ValueError, match="vingt-quatre heures"):
            weekly.remplacer_destinataire(user.profile, "  ")

    def test_il_annule_une_demande_d_arret_en_cours(self, user, monkeypatch):
        _capturer(monkeypatch)
        weekly.demander_desactivation(user.profile)
        weekly.remplacer_destinataire(user.profile, "https://hooks.example/nouveau")
        assert user.profile.buddy_disable_requested_at is None

    def test_trois_bilans_non_lus_proposent_enfin_quelque_chose(self, user):
        """Le constat existait ; c'est la suite qui manquait."""
        assert weekly.proposition_de_remplacement(user) is None
        for i in range(weekly.SEUIL_NON_LUS):
            WeeklyReport.objects.create(
                user=user,
                week_start=date(2026, 3, 2) - timedelta(days=7 * i),
                body="x",
                sent_at=timezone.now(),
            )
        proposition = weekly.proposition_de_remplacement(user)
        assert proposition["non_lus"] == weekly.SEUIL_NON_LUS
        assert "immédiat" in proposition["action"]


class TestLeGardienDeSecours:
    """L'agent tourne hors de Django : on teste son module comme du code pur."""

    def test_il_se_leve_quand_l_heure_est_passee(self, consigne):
        assert gardien.a_lever(
            consigne, now=consigne.at + timedelta(minutes=1),
            jour_du_coach=consigne.day, deja_leve=None,
        )

    def test_il_ne_se_leve_pas_avant_l_heure(self, consigne):
        assert not gardien.a_lever(
            consigne, now=consigne.at - timedelta(minutes=1),
            jour_du_coach=consigne.day, deja_leve=None,
        )

    def test_une_journee_deja_validee_ne_leve_rien(self, consigne):
        valide = gardien.Consigne(**{**consigne.__dict__, "validated": True})
        assert not gardien.a_lever(
            valide, now=valide.at + timedelta(hours=1),
            jour_du_coach=valide.day, deja_leve=None,
        )

    def test_une_consigne_d_hier_se_tait(self, consigne):
        """Mieux vaut un gardien manquant qu'un gardien qui parle du mauvais soir."""
        assert not gardien.a_lever(
            consigne, now=consigne.at + timedelta(days=1),
            jour_du_coach="2026-03-03", deja_leve=None,
        )

    def test_il_ne_se_leve_qu_une_fois_par_soir(self, consigne):
        assert not gardien.a_lever(
            consigne, now=consigne.at + timedelta(hours=1),
            jour_du_coach=consigne.day, deja_leve=consigne.day,
        )

    def test_le_message_dit_qu_il_est_hors_ligne(self, consigne):
        """Une notification qui ne ressemble pas à celle qu'on connaît, sans
        dire pourquoi, se lit comme un bug."""
        titre, corps = gardien.message(consigne)
        assert titre == "Rien de posé ce soir"
        assert "injoignable" in corps and "brancher le raycast" in corps

    def test_il_tombe_sur_le_plancher_sans_tache(self, consigne):
        muet = gardien.Consigne(**{**consigne.__dict__, "task": ""})
        _, corps = gardien.message(muet)
        assert "10 minutes" in corps

    def test_le_cache_fait_l_aller_retour(self, consigne, tmp_path):
        chemin = tmp_path / "gardien.local.json"
        etat = {
            "day": consigne.day,
            "guardian": {
                "day": consigne.day,
                "at": consigne.at.isoformat(),
                "task": consigne.task,
                "project": consigne.project,
                "validated": consigne.validated,
                "floor_minutes": consigne.floor_minutes,
            },
        }
        gardien.memoriser(etat, chemin=chemin)
        assert gardien.charger(chemin=chemin) == consigne

    def test_un_cache_absent_ne_plante_pas(self, tmp_path):
        assert gardien.charger(chemin=tmp_path / "rien.json") is None


@pytest.fixture
def consigne():
    return gardien.Consigne(
        day="2026-03-02",
        at=datetime(2026, 3, 2, 21, 30, tzinfo=PARIS),
        task="brancher le raycast",
        project="Bestiaire",
        validated=False,
        floor_minutes=10,
    )


def _capturer(monkeypatch) -> list[tuple[str, str]]:
    """Intercepte les envois : aucun test ne joint un webhook réel."""
    envois: list[tuple[str, str]] = []

    def faux(canal, message):
        envois.append((canal, message))
        return canal

    monkeypatch.setattr(weekly, "_poster", faux)
    return envois


@pytest.fixture
def user(db):
    User = get_user_model()
    user = User.objects.create_user(username="test", password="test")
    profile = Profile.objects.create(
        user=user, buddy_channel="https://hooks.example/ancien"
    )
    for weekday in range(7):
        DayWindow.objects.create(profile=profile, weekday=weekday)
    return user
