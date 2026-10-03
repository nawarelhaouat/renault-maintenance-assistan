from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

OUT = Path(__file__).resolve().parent / "manuals"
OUT.mkdir(exist_ok=True)

MODELS = [
    ("KUKA", "KR 210 R2700", "Robot", "kuka_kr210.pdf"),
    ("FANUC", "R-2000iC/210F", "Robot", "fanuc_r2000ic.pdf"),
    ("ABB", "IRB 6700", "Robot", "abb_irb6700.pdf"),
    ("Schuler", "MSP 2000", "Presse", "schuler_msp2000.pdf"),
    ("Atlas Copco", "Tensor STR", "Visseuse", "atlas_tensor_str.pdf"),
    ("Siemens", "SIMATIC S7-1500", "Automate", "siemens_s7_1500.pdf"),
    ("Dürr", "EcoRP E043i", "Robot peinture", "durr_ecorp.pdf"),
]

INTRO = {
    "Robot": "Robot industriel articulé 6 axes pour manutention, soudage et assemblage. Charge utile nominale : 210 kg. Alimentation : 400 V triphasé. Température ambiante de service : 5 à 45 °C.",
    "Presse": "Presse hydraulique d'emboutissage de 2000 tonnes. Pression hydraulique nominale : 250 bar. Réservoir d'huile : 1200 litres. Alimentation : 400 V triphasé.",
    "Visseuse": "Visseuse de précision à contrôle de couple pour lignes de montage. Plage de couple : 5 à 50 Nm. Précision : plus ou moins 5 pour cent. Alimentation : 230 V.",
    "Automate": "Automate programmable (API) pour le pilotage des cellules de production. Communication Profinet. Alimentation : 24 V DC. Température de service : 0 à 55 °C.",
    "Robot peinture": "Robot de peinture à atomiseur rotatif pour cabines de peinture carrosserie. Zone classée ATEX. Débit de peinture : 100 à 600 ml/min. Alimentation : 24 V DC.",
}

PREVENTIVE = {
    "Robot": [
        "Graissage des axes 1 à 6 : tous les 90 jours (ou 4000 heures). Graisse au lithium NLGI 2, environ 30 g par axe. Nettoyer les graisseurs avant injection.",
        "Contrôle des câbles et des batteries de sauvegarde : tous les 180 jours. Remplacer la batterie de sauvegarde (réf. RF-BAT-002) tous les 18 mois ou dès l'alarme de tension faible.",
        "Contrôle du réducteur : vérifier le niveau et la couleur de l'huile tous les 6 mois. Une huile métallique ou noire indique une usure (voir code E401).",
    ],
    "Presse": [
        "Contrôle du niveau d'huile et du filtre hydraulique : tous les 60 jours. Remplacer le filtre (réf. RF-FIL-050) toutes les 1000 heures ou si l'indicateur de colmatage est rouge.",
        "Inspection des glissières et du graissage centralisé : tous les 120 jours. Vérifier l'absence de rayures sur les glissières.",
        "Contrôle des joints et flexibles : rechercher toute fuite à chaque inspection. Kit de joints : réf. RF-JNT-310.",
    ],
    "Visseuse": [
        "Étalonnage du couple : tous les 30 jours à l'aide d'un banc d'essai. Tolérance admise : plus ou moins 5 pour cent. Hors tolérance : retirer la visseuse de la ligne et contacter la maintenance.",
        "Contrôle du câble et du connecteur : mensuel. Remplacer tout câble endommagé.",
    ],
    "Automate": [
        "Sauvegarde du programme et test du réseau Profinet : tous les 180 jours. Conserver une copie du projet hors de l'automate.",
        "Contrôle des ventilateurs, de l'alimentation 24 V et du serrage des borniers : tous les 180 jours. Câble Profinet de rechange : réf. RF-CAB-330.",
    ],
    "Robot peinture": [
        "Nettoyage des atomiseurs : tous les 14 jours. Utiliser le solvant préconisé et ne jamais utiliser d'outil métallique sur la cloche.",
        "Contrôle des pompes de peinture et des électrovannes : tous les 90 jours. Électrovanne de rechange : réf. RF-VAL-205.",
        "Graissage des axes et contrôle des câbles : tous les 90 jours. Cartouche de graisse : réf. RF-GRS-010.",
    ],
}

SAFETY = [
    "1. Informer l'exploitation et arrêter la machine en fin de cycle.",
    "2. Mettre la machine hors tension au sectionneur principal.",
    "3. Verrouiller le sectionneur avec un cadenas personnel et apposer l'étiquette de consignation.",
    "4. Décharger les énergies résiduelles : purger l'air comprimé, relâcher la pression hydraulique, bloquer les axes soumis à la gravité.",
    "5. Vérifier l'absence de tension avec un VAT (vérificateur d'absence de tension).",
    "6. Seulement ensuite, commencer l'intervention. Équipements de protection obligatoires : gants, lunettes, chaussures de sécurité.",
    "Ne jamais court-circuiter un arrêt d'urgence ou un contacteur de porte.",
]

ERRORS = {
    "E101": ("Surchauffe moteur axe", "Température moteur supérieure à 80 °C (alarme) ou 90 °C (arrêt).",
             ["Arrêter la machine et laisser refroidir 30 minutes.", "Vérifier le ventilateur du moteur et dégager les entrées d'air.", "Contrôler la charge et la trajectoire du programme : cycle trop dense ?", "Mesurer la résistance de la sonde thermique. Si défectueuse, remplacer le moteur (réf. RF-MOT-210)."]),
    "E102": ("Défaut codeur", "Perte du signal du codeur absolu, positions incohérentes.",
             ["Consigner la machine.", "Contrôler le connecteur et le câble du codeur : broches pliées, câble écrasé.", "Remplacer le codeur (réf. RF-ENC-045) si le défaut persiste.", "Refaire le calage des axes (mastering) puis tester à vitesse réduite."]),
    "E201": ("Fuite hydraulique", "Perte de pression, traces d'huile sous la machine.",
             ["Arrêter la machine et purger la pression résiduelle.", "Repérer la fuite : raccords, flexibles, joints de vérin.", "Remplacer le joint ou le flexible concerné (kit réf. RF-JNT-310).", "Compléter le niveau d'huile et remplacer le filtre (réf. RF-FIL-050). Tester la montée en pression."]),
    "E202": ("Pression pneumatique insuffisante", "Pression d'air inférieure à 5 bar.",
             ["Vérifier la pression du réseau d'air à l'entrée de la machine.", "Contrôler le filtre régulateur et purger les condensats.", "Rechercher une fuite sur les tuyaux (eau savonneuse).", "Tester l'électrovanne et la remplacer si besoin (réf. RF-VAL-205)."]),
    "E301": ("Défaut de communication Profinet", "Perte de communication entre l'automate et la machine.",
             ["Vérifier les voyants LINK/ACT du port réseau.", "Contrôler le câble Profinet et le remplacer si besoin (réf. RF-CAB-330).", "Vérifier le nom de station et l'adresse IP de l'appareil.", "Redémarrer le switch puis la machine. Si le défaut revient, contacter l'automaticien."]),
    "E302": ("Erreur de couple de serrage", "Couple mesuré hors tolérance de plus ou moins 5 pour cent.",
             ["Arrêter la production sur ce poste et isoler les pièces concernées.", "Vérifier l'outil sur le banc d'étalonnage.", "Contrôler l'usure de l'embout et l'état du câble.", "Réétalonner l'outil. Si l'écart persiste, envoyer la visseuse en réparation."]),
    "E401": ("Usure du réducteur", "Bruit anormal, jeu excessif, particules métalliques dans l'huile.",
             ["Prélever un échantillon d'huile et rechercher des particules.", "Mesurer le jeu à l'axe concerné.", "Planifier le remplacement du réducteur (réf. RF-RED-120) : intervention lourde, prévoir 8 heures.", "Après remplacement, refaire le calage de l'axe."]),
    "E402": ("Défaut capteur de proximité", "Signal absent ou instable sur un capteur inductif.",
             ["Vérifier la distance de détection et la fixation du capteur.", "Contrôler le voyant du capteur et le câblage.", "Remplacer le capteur (réf. RF-SEN-077) si le voyant ne réagit plus.", "Tester le cycle à vide."]),
    "E501": ("Arrêt d'urgence déclenché", "Circuit de sécurité ouvert.",
             ["Identifier l'origine : bouton d'arrêt d'urgence, porte ouverte, barrière immatérielle.", "Rétablir la condition de sécurité puis réarmer le circuit.", "Si l'arrêt se répète sans cause visible, tester les relais de sécurité.", "Ne jamais shunter le circuit de sécurité."]),
    "E601": ("Défaut de graissage", "Alarme de niveau bas ou pression de graissage insuffisante.",
             ["Vérifier le niveau de graisse et remplacer la cartouche (réf. RF-GRS-010).", "Purger le circuit de graissage.", "Contrôler les distributeurs et les tuyaux d'alimentation.", "Effectuer un cycle de graissage manuel puis remettre en production."]),
}

styles = getSampleStyleSheet()
H1, H2, P = styles["Title"], styles["Heading2"], styles["BodyText"]


def build(manufacturer, model, category, filename):
    doc = SimpleDocTemplate(str(OUT / filename), pagesize=A4, title=f"{manufacturer} {model}")
    s = []
    s += [Paragraph(f"{manufacturer} {model}", H1),
          Paragraph("Manuel de maintenance", H2),
          Paragraph("Document de démonstration généré à des fins de test. Ne pas utiliser en production.", P),
          Spacer(1, 12), Paragraph("1. Présentation et caractéristiques", H2),
          Paragraph(INTRO[category], P), PageBreak()]

    s += [Paragraph("2. Consignes de sécurité et consignation (LOTO)", H2),
          Paragraph("Avant toute intervention de maintenance, appliquer la procédure de consignation :", P)]
    s += [Paragraph(x, P) for x in SAFETY] + [PageBreak()]

    s += [Paragraph("3. Maintenance préventive", H2)]
    s += [Paragraph(x, P) for x in PREVENTIVE[category]] + [PageBreak()]

    codes = list(ERRORS)
    s += [Paragraph("4. Codes d'erreur et dépannage", H2)]
    for i, code in enumerate(codes):
        title, symptom, steps = ERRORS[code]
        s += [Paragraph(f"Code {code} : {title}", styles["Heading3"]),
              Paragraph(f"Symptôme : {symptom}", P)]
        s += [Paragraph(f"Étape {n}. {t}", P) for n, t in enumerate(steps, 1)]
        s.append(Spacer(1, 8))
        if i == 4:
            s.append(PageBreak())
    doc.build(s)
    print("OK", filename)


if __name__ == "__main__":
    for m in MODELS:
        build(*m)