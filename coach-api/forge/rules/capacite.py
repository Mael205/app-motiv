"""Le troisième axe : ce que tu sais faire, et non combien tu as travaillé.

**Le manque auquel ce module répond.** Tout ce que le système comptait jusqu'ici
mesure du **volume** — l'XP, les minutes, les heures par branche — ou de la
**régularité** — le rang, les semaines tenues, le streak. Deux axes déjà séparés
avec soin par le §4.4, pour une bonne raison : débloquer sur l'XP
récompenserait ce qui fait décrocher.

Mais ni l'un ni l'autre ne dit qu'on est devenu **meilleur**. Quarante heures de
mauvaise pratique donnent exactement le même titre d'arbre que quarante heures
de bonne, parce que le titre se calcule sur les heures. Un système qui veut
mener quelqu'un jusqu'au niveau professionnel ne peut pas s'arrêter là : la
pratique délibérée demande une difficulté qui monte et un retour sur la qualité,
et aucun compteur de temps ne les porte.

D'où deux mécaniques ici, et une seule idée derrière.

**La preuve.** Un fait daté, binaire, et vérifiable par quelqu'un d'autre que
soi : « les 100 % de labs Apprentice validés », « l'enchaînement A tenu sur huit
temps, filmé ». Elle ne se décrète pas, elle se constate — et c'est exactement
ce que le critère de sortie d'un bloc de parcours écrit déjà à la création du
projet (§4.5). Une preuve **paie en Éclats et jamais en XP** : l'XP mesure le
volume par construction, et une capacité n'est pas un volume.

**La difficulté ressentie.** Un tap à la fin d'une session : trop facile, juste,
trop dur. Trois sessions de suite « trop facile » ne veulent pas dire qu'on
travaille mal — ça veut dire qu'on a cessé d'apprendre, ce qui est invisible sur
tous les autres compteurs et se voit même comme une bonne série. C'est le seul
endroit du système où une bonne nouvelle apparente est traitée comme un signal.

**Ce que ce module ne fait pas.** Il ne note rien, ne compare à personne, et ne
retire jamais une preuve acquise (§17). Une capacité constatée reste constatée,
même si elle rouille — le contraire demanderait au système de juger un niveau,
ce qu'il ne sait pas faire et ne doit pas prétendre.
"""

from __future__ import annotations

from dataclasses import dataclass

# Une preuve vaut plus qu'une semaine entière de routines (3 Éclats par coche,
# 10 de bonus). C'est voulu : c'est le seul geste du système qui atteste d'un
# niveau, et la Forge doit rester atteignable par ce chemin-là autant que par
# l'accumulation.
SHARDS_PAR_PREUVE = 40

# En dessous de trois, ce n'est pas une tendance : une séance facile arrive, et
# deux d'affilée peuvent être deux bonnes soirées.
SESSIONS_TROP_FACILES = 3

TROP_FACILE, JUSTE, TROP_DUR = 1, 2, 3

DIFFICULTE_LABELS = {
    TROP_FACILE: "trop facile",
    JUSTE: "juste",
    TROP_DUR: "trop dur",
}

PALIER_TROP_FACILE = "palier_trop_facile"


@dataclass(frozen=True)
class Preuve:
    """Une capacité constatée, réduite à ce dont la règle a besoin."""

    projet: str
    critere: str

    @property
    def valide(self) -> bool:
        """Une preuve sans critère écrit n'en est pas une.

        C'est la seule règle de validité, et elle est dure : « j'ai progressé »
        n'est pas un critère, « les 100 % de labs Apprentice validés » en est
        un. Sans cette borne, la mécanique redevient de l'auto-évaluation, et
        l'auto-évaluation est précisément ce que le §6 refuse partout ailleurs.
        """
        return bool(self.critere.strip()) and len(self.critere.strip()) >= 12


def shards_pour_preuve(deja_acquises: int) -> int:
    """Ce que rapporte une preuve. Constant, et volontairement non dégressif.

    L'XP est dégressive parce qu'elle mesure un volume, et qu'un volume se force
    (§4.4). Une capacité ne se force pas : la dixième preuve d'un parcours est
    plus dure que la première, pas moins. La faire rapporter moins serait
    exactement le mauvais signal.
    """
    return SHARDS_PAR_PREUVE


def palier_trop_facile(difficultes: list[int]) -> dict | None:
    """Trois sessions d'affilée « trop facile » : la barre ne monte plus.

    ``difficultes`` va de la plus récente à la plus ancienne, et ne contient que
    les sessions où quelque chose a été déclaré — un silence n'est pas un avis.

    Rien n'est retiré, rien n'est imposé : le §17 interdit qu'un système décide
    seul, et ici il ne saurait pas quoi décider — monter la barre peut vouloir
    dire changer de ressource, passer au bloc suivant, ou arrêter de refaire ce
    qu'on sait déjà. Le constat est chiffré, la proposition est une question.
    """
    recentes = difficultes[:SESSIONS_TROP_FACILES]
    if len(recentes) < SESSIONS_TROP_FACILES:
        return None
    if any(d != TROP_FACILE for d in recentes):
        return None
    return {
        "kind": PALIER_TROP_FACILE,
        "constat": f"{SESSIONS_TROP_FACILES} sessions d'affilée déclarées trop faciles.",
        "proposition": (
            "Rien ne s'apprend à ce niveau-là. Passer au bloc suivant du parcours, "
            "ou remplacer la ressource par une plus dure."
        ),
        "donnees": {"sessions": SESSIONS_TROP_FACILES},
    }


def etat(preuves: int, minutes: int) -> dict:
    """Les deux nombres, côte à côte, jamais fusionnés en un score.

    Même geste que le §11.4 pour les pistes et le §4.4 pour les deux axes : les
    additionner produirait un chiffre unique qui monterait en ne faisant que des
    heures, et qui aurait donc exactement le défaut qu'on cherche à corriger.
    """
    heures = round(minutes / 60)
    return {
        "preuves": preuves,
        "heures": heures,
        # Le rapport n'est pas une note. Il sert à une seule question, celle
        # qu'on ne se pose jamais tout seul : combien d'heures pour la dernière
        # chose que je sais faire ?
        "heures_par_preuve": round(heures / preuves) if preuves else None,
    }
