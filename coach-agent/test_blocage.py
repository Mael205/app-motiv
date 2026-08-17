"""Tests du blocage des domaines pleins (SPEC §8.5, §9.1, §17).

    coach-api/.venv/Scripts/python -m pytest coach-agent

Ce qui est vérifié ici n'est pas que le blocage marche — ça demande un service
élevé et une vraie machine. C'est **ce qu'il ne ferme pas**, et ce qu'il ne
casse pas :

* un chemin n'est pas un domaine, donc ``youtube.com/shorts`` ne doit jamais
  devenir ``youtube.com`` — l'écrire fermerait YouTube en entier, ce que le
  §9.1 interdit et ce que personne ne remarquerait avant d'en avoir besoin ;
* le fichier hosts appartient à l'utilisateur : tout ce qui est hors des
  marqueurs doit survivre à l'écriture ;
* un ordre inconnu ne s'exécute pas.
"""

from datetime import datetime, timedelta, timezone

import pytest

from blocage import (
    MARQUEUR_DEBUT,
    MARQUEUR_FIN,
    domaines_a_fermer,
    en_pause,
    envoyer,
    rendre,
    retirer,
    synchroniser,
)

CATEGORIES = {
    "scroll_passif": ["tiktok.com", "youtube.com/shorts", "reddit.com", "twitch.tv"],
    "reseaux": ["instagram.com", "x.com", "discord.com/channels"],
    "travail_projet": ["code.exe", "github.com", "localhost"],
    "jeu": ["steam.exe", "slippi"],
    "adulte": ["un-domaine-prive.example"],
}

HOSTS_UTILISATEUR = """\
127.0.0.1 localhost
192.168.1.42 nas.maison
"""


class TestListeDesDomaines:
    def test_ferme_le_scroll_et_les_reseaux(self):
        domaines = domaines_a_fermer(CATEGORIES)
        assert "tiktok.com" in domaines
        assert "instagram.com" in domaines

    def test_n_ecrase_jamais_un_chemin_en_domaine(self):
        """`youtube.com/shorts` fermerait YouTube en entier. Le §9.1 l'interdit."""
        domaines = domaines_a_fermer(CATEGORIES)
        assert "youtube.com" not in domaines
        assert not any("/" in d for d in domaines)

    def test_ignore_les_executables(self):
        assert "steam.exe" not in domaines_a_fermer(CATEGORIES)
        assert "slippi" not in domaines_a_fermer(CATEGORIES)

    def test_la_garde_n_est_pas_un_blocage(self):
        """Le §11.10 : une garde se tient à un budget, pas à un mur.

        Et une liste de gardes n'a rien à faire dans un fichier hosts, que
        n'importe qui peut lire sur la machine.
        """
        domaines = domaines_a_fermer(CATEGORIES)
        assert "un-domaine-prive.example" not in domaines

    def test_ne_ferme_pas_le_travail(self):
        """Le §17 refuse de bloquer les jeux ; fermer github.com serait pire."""
        domaines = domaines_a_fermer(CATEGORIES)
        assert "github.com" not in domaines
        assert "localhost" not in domaines


class TestFichierHosts:
    def test_ajoute_le_bloc_et_ses_marqueurs(self):
        rendu = rendre(HOSTS_UTILISATEUR, ["tiktok.com"])
        assert MARQUEUR_DEBUT in rendu and MARQUEUR_FIN in rendu
        assert "0.0.0.0 tiktok.com" in rendu
        assert "0.0.0.0 www.tiktok.com" in rendu

    def test_garde_ce_qui_n_est_pas_a_nous(self):
        rendu = rendre(HOSTS_UTILISATEUR, ["tiktok.com"])
        assert "192.168.1.42 nas.maison" in rendu
        assert "127.0.0.1 localhost" in rendu

    def test_appliquer_deux_fois_ne_change_rien(self):
        une = rendre(HOSTS_UTILISATEUR, ["tiktok.com", "reddit.com"])
        deux = rendre(une, ["tiktok.com", "reddit.com"])
        assert une == deux

    def test_retirer_rend_le_fichier_d_origine(self):
        bloque = rendre(HOSTS_UTILISATEUR, ["tiktok.com", "reddit.com"])
        assert retirer(bloque) == HOSTS_UTILISATEUR

    def test_une_liste_vide_ne_pose_pas_de_marqueur(self):
        assert rendre(HOSTS_UTILISATEUR, []) == HOSTS_UTILISATEUR

    def test_ne_double_pas_le_prefixe_www(self):
        rendu = rendre("", ["www.tiktok.com"])
        assert "www.www.tiktok.com" not in rendu


class TestOrdres:
    def test_un_ordre_inconnu_ne_part_pas(self):
        with pytest.raises(ValueError, match="ordre inconnu"):
            envoyer("rm -rf /")

    def test_sans_service_l_envoi_echoue_sans_lever(self, monkeypatch):
        """Le service absent est l'état normal tant qu'il n'a pas été installé."""
        import builtins

        def refuse(*_args, **_kwargs):
            raise OSError("le tube n'existe pas")

        monkeypatch.setattr(builtins, "open", refuse)
        assert envoyer("unblock") is False


class TestSynchronisation:
    def test_un_etat_sans_blocage_ne_declenche_rien(self):
        assert synchroniser({"running_session": None}) is None

    def test_la_pause_desarme(self, tmp_path, monkeypatch):
        import blocage

        pause = tmp_path / "pause.local"
        pause.write_text(
            (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(), encoding="utf-8"
        )
        monkeypatch.setattr(blocage, "PAUSE_PATH", pause)

        envoyes = []
        monkeypatch.setattr(blocage, "envoyer", lambda ordre: envoyes.append(ordre) or True)

        assert blocage.en_pause()
        blocage.synchroniser({"block_scroll": {"armed": True}})
        assert envoyes == ["unblock"], "une pause en cours lève le blocage, armé ou non"

    def test_arme_et_hors_pause_bloque(self, tmp_path, monkeypatch):
        import blocage

        monkeypatch.setattr(blocage, "PAUSE_PATH", tmp_path / "absent")
        envoyes = []
        monkeypatch.setattr(blocage, "envoyer", lambda ordre: envoyes.append(ordre) or True)

        blocage.synchroniser({"block_scroll": {"armed": True}})
        assert envoyes == ["block"]

    def test_une_pause_expiree_ne_compte_plus(self, tmp_path, monkeypatch):
        import blocage

        pause = tmp_path / "pause.local"
        pause.write_text(
            (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(), encoding="utf-8"
        )
        monkeypatch.setattr(blocage, "PAUSE_PATH", pause)
        assert not blocage.en_pause()

    def test_un_fichier_de_pause_illisible_n_ouvre_rien(self, tmp_path, monkeypatch):
        """Un fichier abîmé ne doit pas valoir levée : le doute ne lève pas."""
        import blocage

        pause = tmp_path / "pause.local"
        pause.write_text("pas une date", encoding="utf-8")
        monkeypatch.setattr(blocage, "PAUSE_PATH", pause)
        assert not blocage.en_pause()
