"""Une ligne par semaine, tirée du monde de la saison en cours (§12.2).

## Ce que ce fichier n'est pas

Ce ne sont pas des citations de motivation. Le §5.2 fixe le ton — « zéro
flatterie, zéro bravo champion » — et le §11.10 en fait une règle testée. Une
affiche « tu peux le faire » dans cette application serait la seule phrase qui
ment : le produit ne pense pas que le problème soit la motivation. Le §0.2 dit
l'inverse — trop de motivation, pas trop peu.

Ce sont des lignes du **décor**, dans le registre exact des baselines de
saison, qui existent déjà et qui ont trouvé leur voix : « Le feu ne demande pas
la permission », « Ils passeront par toi », « Le point le plus bas est un point
de départ comme un autre ». Elles nomment la situation, elles ne commentent
jamais celui qui la traverse. C'est la différence entre un décor qui porte et
un poster qui flatte.

## Quatre par saison, et pourquoi quatre

Une saison fait vingt-huit jours, donc quatre semaines. Une ligne par semaine
suit la courbe du mois autant que celle de la saison :

    semaine 1  ce qui s'ouvre
    semaine 2  ce qui s'installe
    semaine 3  le creux — la seule semaine où le mois pèse
    semaine 4  ce qui se ferme

La troisième est écrite en connaissance de cause. Le §0.2 situe l'abandon au
jour cinq ou sept d'un projet ; à l'échelle d'un mois, c'est la troisième
semaine qui use, quand l'ouverture est loin et la fin pas encore en vue.

## Aucun tirage

La ligne se **calcule** depuis la clé de saison et le jour : la même semaine
affiche toujours la même phrase. Un tirage aléatoire ferait de la ligne un
distributeur — on rouvrirait l'application pour voir la suivante, ce qui est
exactement le geste que le §11.1 refuse de récompenser.
"""

from __future__ import annotations

SEMAINES_PAR_SAISON = 4

# Les quatre lignes de chaque saison, dans l'ordre des semaines.
#
# La table couvre la trame courante. Une clé absente — une saison d'archive
# retirée depuis — ne rend rien du tout : mieux vaut pas de ligne qu'une ligne
# empruntée à une autre saison, qui dirait le contraire de son décor.
CITATIONS: dict[str, tuple[str, str, str, str]] = {
    # ---- VOIE DES CIMES : du réveil à l'Empyrée -------------------------
    "eveil": (
        "Ce qui se lève ne demande pas si le moment est bon.",
        "La deuxième semaine est celle où l'on découvre ce qui dormait.",
        "Rien ne se rendort d'un coup. Ça se laisse rendormir.",
        "Un mois d'éveil ne prouve rien. Il ouvre.",
    ),
    "aube_rouge": (
        "Sept levers derrière. Vingt et un devant.",
        "L'aube ne se répète pas : elle recommence.",
        "C'est la semaine où le ciel reste gris le plus longtemps.",
        "Compte les levers, pas les intentions.",
    ),
    "porte_ivoire": (
        "Deux portes. Une seule mène à ce qui arrive vraiment.",
        "Le songe et le fait ont la même forme au départ.",
        "On reconnaît la mauvaise porte à ce qu'elle ne coûte rien.",
        "Ce qui a franchi le seuil ne se rêve plus.",
    ),
    "sanctuaire": (
        "On défend un lieu, pas une humeur.",
        "Les murs tiennent parce qu'on les relève, pas parce qu'ils sont hauts.",
        "La troisième semaine est celle où l'on garde une place vide.",
        "Ce qui a été défendu quatre semaines est à toi.",
    ),
    "elysion": (
        "Le repos se gagne. Sinon c'est de l'oubli.",
        "Les champs ne poussent pas parce qu'on les regarde.",
        "La semaine où l'on croit avoir mérité de s'arrêter.",
        "Ce qu'on emporte d'ici, on l'a posé soi-même.",
    ),
    "ascension": (
        "Personne ne monte par accident.",
        "La pente ne change pas. Le pas, si.",
        "C'est ici qu'on cesse de compter les marches.",
        "On ne redescend pas ce qu'on a monté quatre semaines.",
    ),
    "valhalla": (
        "La salle est pleine de gens qui ont fini.",
        "On n'entre pas pour avoir essayé.",
        "La table est longue et la place se prend.",
        "Ce qui s'assied là a été terminé, pas commencé.",
    ),
    "ragnarok": (
        "Tout finit. La question est ce que tu auras bâti avant.",
        "Le compte à rebours ne se négocie pas.",
        "La semaine où le ciel se fend et où l'on continue.",
        "Ce qui reste debout après n'a pas été promis. Il a été fait.",
    ),
    "couronne_solaire": (
        "On ne la voit que pendant l'éclipse.",
        "La lumière la plus grande est cachée par la plus proche.",
        "Sept jours d'ombre. C'est là qu'elle apparaît.",
        "Ce qui brille au bord était là depuis le début.",
    ),
    "heavens_paradise": (
        "On monte, ou on regarde monter.",
        "La deuxième semaine sépare les deux.",
        "Il n'y a pas de place assise à mi-hauteur.",
        "Vingt-huit jours plus haut. C'est tout, et c'est beaucoup.",
    ),
    "apotheose": (
        "Le mois où l'on cesse d'être celui qui essaie.",
        "Rien ne change d'un coup. Tout change en quatre semaines.",
        "C'est la semaine où l'ancien revient frapper.",
        "Ce qui a été posé jour après jour ne se retire pas.",
    ),
    "empyree": (
        "Le ciel de feu. Il n'y a rien au-dessus.",
        "Arrivé en haut, la seule direction est de tenir.",
        "La hauteur ne protège de rien. Elle expose.",
        "Ce qui se termine ici ne se refera pas à l'identique.",
    ),
    # ---- VOIE DES BRAISES : la chute, le feu, la reforge ----------------
    "chute": (
        "Elle a déjà eu lieu. Reste à savoir jusqu'où.",
        "On ne remonte pas en niant qu'on est tombé.",
        "La semaine où le fond n'est toujours pas atteint.",
        "Ce qui touche le fond a de quoi pousser dessus.",
    ),
    "nadir": (
        "Le point le plus bas est un point de départ comme un autre.",
        "D'ici, toutes les directions montent.",
        "Le fond est plat. C'est ce qui le rend habitable.",
        "On repart d'où l'on est, pas d'où l'on aurait voulu être.",
    ),
    "styx": (
        "On ne traverse pas deux fois le même fleuve.",
        "L'autre rive ne se voit pas depuis celle-ci.",
        "La semaine où le courant paraît plus fort que la nage.",
        "Traversé une fois, il n'est plus devant.",
    ),
    "purgatoire": (
        "Ni en haut, ni en bas. Vingt-huit jours pour trancher.",
        "L'entre-deux est confortable. C'est son seul danger.",
        "La troisième semaine est celle où l'on voudrait y rester.",
        "On ne sort pas d'ici en attendant.",
    ),
    "solstice_noir": (
        "La nuit la plus longue se travaille.",
        "L'obscurité ne s'arrête pas parce qu'on la regarde.",
        "C'est la semaine la plus courte en lumière.",
        "Après la plus longue nuit, les jours rallongent. Pas avant.",
    ),
    "cendres": (
        "Ce qui a brûlé fertilise ou stérilise. Ça se décide maintenant.",
        "La cendre ne dit pas ce qu'elle deviendra.",
        "Sous le gris, quelque chose rougeoie encore.",
        "On sème dans ce qui reste, ou on balaie.",
    ),
    "hellfest": (
        "Quatre semaines. Le feu ne demande pas la permission.",
        "On n'éteint pas ça en fermant les yeux.",
        "La semaine où la chaleur devient une habitude.",
        "Ce qui a traversé le feu ne craint plus la chaleur.",
    ),
    "inferno": (
        "Ça chauffe à partir de maintenant.",
        "Les cercles se descendent un par un.",
        "Le plus chaud est au milieu. Toujours.",
        "La sortie est de l'autre côté, jamais en arrière.",
    ),
    "tonnerre": (
        "Le bruit arrive après. Toujours.",
        "Ce qui frappe est déjà passé quand on l'entend.",
        "La semaine où le ciel gronde sans tomber.",
        "On compte les secondes entre l'éclair et le bruit. Pas l'inverse.",
    ),
    "dernier_rempart": (
        "Ils passeront par toi.",
        "Un mur tient par ce qu'on remet dessus chaque jour.",
        "La troisième semaine est celle où la brèche s'ouvre.",
        "Ce qui n'est pas tombé en vingt-huit jours ne tombera pas ce soir.",
    ),
    "derniere_forge": (
        "Le feu s'éteint à la fin du mois. Pas avant.",
        "On ne forge pas à froid. On chauffe d'abord.",
        "La semaine où le métal résiste le plus.",
        "Ce qui sort de la forge a été frappé, pas trouvé.",
    ),
    "phenix": (
        "Il ne revient pas malgré le feu. Il revient par lui.",
        "Rien ne renaît sans avoir brûlé entièrement.",
        "La semaine où l'on n'est ni la cendre ni l'oiseau.",
        "Ce qui repart n'est pas ce qui était. C'est mieux.",
    ),
}


def semaine_de(jour_index: int) -> int:
    """La semaine de saison, de 1 à 4, depuis le nombre de jours écoulés.

    Bornée aux deux extrémités : un ``jour_index`` négatif — une saison
    engagée mais pas encore commencée, ce que le mode extra du §12.4 produit —
    doit rendre la première semaine, et le vingt-neuvième jour d'une saison
    prolongée la dernière, jamais une cinquième qui n'existe pas.
    """
    return max(1, min(SEMAINES_PAR_SAISON, jour_index // 7 + 1))


def citation_de(key: str, jour_index: int) -> str:
    """La ligne de cette semaine, pour cette saison. Vide si l'on ne sait pas.

    Le vide est un résultat valable et non un repli dégradé : une saison
    d'archive dont la clé a quitté la trame n'a pas de ligne, et lui en prêter
    une empruntée à une autre saison dirait le contraire de son décor.
    """
    lignes = CITATIONS.get(key)
    if not lignes:
        return ""
    return lignes[semaine_de(jour_index) - 1]
